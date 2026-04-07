import yfinance as yf
from datetime import datetime, timedelta
from collections import defaultdict

from app.models.portfolio_mongo import PortfolioMongo
from app.models.portfolio_snapshot_mongo import PortfolioSnapshotMongo

# GOOG and GOOGL are both Alphabet — treat as same underlying for analysis
SYMBOL_ALIASES = {'GOOGL': 'GOOG', 'BRK.B': 'BRK-B'}

# Commodity / macro-hedge ETFs — no analyst price targets; classified by trailing return + allocation
COMMODITY_ETFS = {
    'GLD':  {'role': 'Gold ETF — inflation hedge & safe haven',       'alloc_min': 5,  'alloc_max': 15},
    'IAU':  {'role': 'Gold ETF (iShares) — inflation hedge',          'alloc_min': 5,  'alloc_max': 15},
    'SGOL': {'role': 'Gold ETF — physical gold backing',              'alloc_min': 5,  'alloc_max': 15},
    'SLV':  {'role': 'Silver ETF — precious metals diversifier',      'alloc_min': 2,  'alloc_max': 8},
    'GDX':  {'role': 'Gold Miners ETF — leveraged gold exposure',     'alloc_min': 2,  'alloc_max': 8},
    'USO':  {'role': 'Oil ETF — commodity hedge',                     'alloc_min': 2,  'alloc_max': 5},
}

# Symbols matching CASH_<CCY> pattern — quantity is treated as face value in that currency
# USD cash: price = 1.0 exactly. Other currencies: fetch <CCY>USD=X from yfinance.
def _parse_cash_symbol(symbol: str):
    """Return currency code if symbol is a cash position (e.g. CASH_USD → 'USD'), else None."""
    upper = symbol.upper()
    if upper.startswith('CASH_') and len(upper) > 5:
        return upper[5:]   # e.g. 'USD', 'EUR', 'GBP'
    if upper.endswith('_USD') and upper == 'CASH_USD':
        return 'USD'
    return None


class PortfolioService:
    def __init__(self):
        self.db       = PortfolioMongo()
        self.snapshots = PortfolioSnapshotMongo()
        self._price_cache    = {}   # per-run dedup (reset on every analyze call → always fresh)
        self._trailing_cache = {}   # commodity 1Y trailing return: longer-lived cache
        self._trailing_ttl   = 60   # minutes — trailing return doesn't need per-refresh fetch

    # ── CRUD ────────────────────────────────────────────────────────────────

    def upsert_position(self, portfolio, symbol, quantity, purchase_price=None):
        self.db.upsert_position(portfolio, symbol, quantity, purchase_price)

    def delete_position(self, portfolio, symbol):
        self.db.delete_position(portfolio, symbol)

    def get_positions_by_portfolio(self) -> dict:
        """Return {portfolio_name: [positions...]}"""
        all_pos = self.db.get_all_positions()
        grouped = defaultdict(list)
        for p in all_pos:
            grouped[p['portfolio_name']].append(p)
        return dict(grouped)

    def seed(self):
        return self.db.seed_initial_data()

    # ── Price / Analyst data ─────────────────────────────────────────────────

    def _fetch_fx_rate(self, ccy: str) -> float:
        """Return 1 USD worth of <ccy> as USD. E.g. EUR → 1.08."""
        if ccy == 'USD':
            return 1.0
        ticker = f'{ccy}USD=X'
        try:
            info = yf.Ticker(ticker).info or {}
            rate = info.get('regularMarketPrice') or info.get('previousClose') or 0
            return float(rate) if rate else 1.0
        except Exception as e:
            print(f"FX rate error for {ccy}: {e}")
            return 1.0

    def _fetch_market_data(self, symbol: str) -> dict:
        # Per-run dedup only — _price_cache is reset at the start of each analyze_portfolio()
        # so prices are always fresh on every analysis call.
        if symbol in self._price_cache:
            return self._price_cache[symbol]

        # ── Cash positions: CASH_USD, CASH_EUR, CASH_GBP, etc. ──
        ccy = _parse_cash_symbol(symbol)
        if ccy is not None:
            rate = self._fetch_fx_rate(ccy)
            data = {
                'price':          rate,
                'price_source':   'regular',
                'market_state':   '',
                'target_mean':    None,
                'target_high':    None,
                'target_low':     None,
                'rec_key':        'HOLD',
                'name':           f'Cash ({ccy})',
                'sector':         'Cash',
                'pe':             None,
                'revenue_growth': None,
                'is_cash':        True,
                'is_commodity':   False,
                'trailing_return_1y': None,
                'commodity_role': None,
                'currency':       ccy,
                'fx_rate':        rate,
            }
            self._price_cache[symbol] = data
            return data

        # ── Regular equity / ETF ──
        try:
            info = yf.Ticker(symbol).info or {}

            # Price selection: prefer extended-hours price when market is in that session
            mkt_state   = (info.get('marketState') or '').upper()
            reg_price   = float(info.get('currentPrice') or info.get('regularMarketPrice') or 0)
            pre_price   = float(info.get('preMarketPrice')  or 0)
            post_price  = float(info.get('postMarketPrice') or 0)

            if mkt_state == 'PRE' and pre_price > 0:
                price, price_source = pre_price, 'pre'
            elif mkt_state in ('POST', 'POSTPOST') and post_price > 0:
                price, price_source = post_price, 'post'
            else:
                price, price_source = reg_price, 'regular'

            prev_close = float(info.get('previousClose') or info.get('regularMarketPreviousClose') or 0)
            day_chg_pct = round((price / prev_close - 1) * 100, 2) if prev_close and price else None

            data = {
                'price':          price,
                'price_source':   price_source,
                'market_state':   mkt_state,
                'prev_close':     prev_close or None,
                'day_change_pct': day_chg_pct,
                'target_mean':    info.get('targetMeanPrice'),
                'target_high':    info.get('targetHighPrice'),
                'target_low':     info.get('targetLowPrice'),
                'rec_key':        (info.get('recommendationKey') or '').upper(),
                'name':           info.get('shortName') or info.get('longName') or symbol,
                'sector':         info.get('sector', ''),
                'pe':             info.get('trailingPE'),
                'revenue_growth': info.get('revenueGrowth'),
                'is_cash':        False,
                'is_commodity':   False,
                'trailing_return_1y': None,
                'commodity_role': None,
            }
        except Exception as e:
            print(f"Market data error for {symbol}: {e}")
            data = {'price': 0, 'price_source': 'regular', 'market_state': '',
                    'target_mean': None, 'target_high': None,
                    'target_low': None, 'rec_key': '', 'name': symbol,
                    'sector': '', 'pe': None, 'revenue_growth': None,
                    'is_cash': False, 'is_commodity': False,
                    'trailing_return_1y': None, 'commodity_role': None}

        # ── Commodity ETF: 1Y trailing return (cached separately — no need to refetch each refresh) ──
        if symbol in COMMODITY_ETFS:
            tc = self._trailing_cache.get(symbol)
            if tc and (datetime.now() - tc['ts']) < timedelta(minutes=self._trailing_ttl):
                trailing_1y = tc['trailing_1y']
            else:
                try:
                    hist = yf.Ticker(symbol).history(period='1y')
                    if len(hist) >= 2:
                        trailing_1y = round(
                            (float(hist['Close'].iloc[-1]) / float(hist['Close'].iloc[0]) - 1) * 100, 1
                        )
                    else:
                        trailing_1y = None
                except Exception as ex:
                    print(f"Trailing return error for {symbol}: {ex}")
                    trailing_1y = None
                self._trailing_cache[symbol] = {'trailing_1y': trailing_1y, 'ts': datetime.now()}
            data['is_commodity']       = True
            data['trailing_return_1y'] = trailing_1y
            data['commodity_role']     = COMMODITY_ETFS[symbol]['role']
            data['target_mean']        = None

        self._price_cache[symbol] = data
        return data

    @staticmethod
    def _expected_return(price, target_mean):
        if price and price > 0 and target_mean and target_mean > 0:
            return round((target_mean / price - 1) * 100, 1)
        return None

    @staticmethod
    def _classify_commodity_action(trailing_ret, alloc_pct, alloc_min, alloc_max, role):
        """Returns (action, rationale) for a commodity/hedge ETF based on trailing return + allocation."""
        role_short = role.split('—')[0].strip()
        alloc_str  = f"{alloc_pct:.1f}% of portfolio"
        range_str  = f"recommended {alloc_min}–{alloc_max}%"

        if trailing_ret is None:
            return 'HOLD', (
                f"{role}. No analyst price target — held for diversification and risk reduction. "
                f"Current allocation: {alloc_str} ({range_str})."
            )

        ret_str = f"{trailing_ret:+.1f}% trailing 12-month"

        if alloc_pct > alloc_max:            # over-allocated
            if trailing_ret >= 15:
                return 'TRIM', (
                    f"{role_short} has returned {ret_str} — a strong gain. "
                    f"With allocation at {alloc_str} above the {range_str}, "
                    f"consider trimming to lock in profits and redeploy into higher-growth equities."
                )
            elif trailing_ret >= 0:
                return 'TRIM', (
                    f"{role_short} is over-allocated at {alloc_str} ({range_str}) "
                    f"with a modest {ret_str} return. "
                    f"Reducing exposure could free capital for better-returning assets."
                )
            else:
                return 'TRIM', (
                    f"{role_short} is declining ({ret_str}) and over-allocated at {alloc_str} ({range_str}). "
                    f"Recommend reducing position to limit drag on portfolio performance."
                )

        elif alloc_pct < alloc_min:          # under-allocated
            if trailing_ret >= 10:
                return 'ADD', (
                    f"{role_short} is performing well at {ret_str} yet under-allocated "
                    f"at {alloc_str} (below {range_str}). "
                    f"Consider adding to strengthen your inflation and volatility hedge."
                )
            else:
                return 'HOLD', (
                    f"{role_short} at {alloc_str} (below {range_str}). {ret_str.capitalize()}. "
                    f"Provides portfolio diversification — maintain or modestly increase if concerned about macro risk."
                )

        else:                                # within recommended range
            if trailing_ret >= 20:
                return 'HOLD', (
                    f"{role_short} is performing strongly ({ret_str}). "
                    f"Allocation at {alloc_str} is within the {range_str}. "
                    f"Retain as a well-performing inflation hedge and portfolio stabiliser."
                )
            elif trailing_ret >= 5:
                return 'HOLD', (
                    f"{role_short} returning {ret_str}. Allocation at {alloc_str} ({range_str}). "
                    f"Fulfilling its hedging role effectively — no action required."
                )
            elif trailing_ret >= 0:
                return 'HOLD', (
                    f"{role_short} is flat at {ret_str}. Allocation at {alloc_str} ({range_str}). "
                    f"Continues to provide diversification benefit — no action needed."
                )
            else:
                return 'REVIEW', (
                    f"{role_short} is down {ret_str}. Allocation at {alloc_str} ({range_str}). "
                    f"Hedge underperforming — review whether current macro conditions "
                    f"(e.g. rising rates, strong USD, risk-on sentiment) justify maintaining full exposure."
                )

    @staticmethod
    def _classify_action(exp_ret, rec_key) -> str:
        if exp_ret is None:
            return 'REVIEW'
        if exp_ret >= 30:
            return 'STRONG_BUY'
        if exp_ret >= 20:
            return 'BUY'
        if exp_ret >= 10:
            return 'HOLD'
        if exp_ret >= 0:
            return 'REVIEW'
        if rec_key in ('STRONG_SELL', 'SELL', 'UNDERPERFORM'):
            return 'SELL'
        return 'SELL'

    # ── Main analysis ────────────────────────────────────────────────────────

    def analyze_portfolio(self, selected_portfolios=None) -> dict:
        # Reset per-run price cache → guarantees fresh prices on every analysis call
        self._price_cache = {}

        all_pos = self.db.get_all_positions()
        if not all_pos:
            return {'error': 'No positions found.'}

        # ── Filter by selected portfolios ─────────────────────────────────
        if selected_portfolios:
            sel = set(s.upper() for s in selected_portfolios)
            all_pos = [p for p in all_pos if p['portfolio_name'] in sel]
        if not all_pos:
            return {'error': 'No positions found for the selected portfolios.'}

        # ── Consolidate quantities ────────────────────────────────────────
        consolidated_qty = defaultdict(float)
        for p in all_pos:
            analysis_sym = SYMBOL_ALIASES.get(p['symbol'], p['symbol'])
            consolidated_qty[analysis_sym] += p['quantity']

        # ── Fetch market data ─────────────────────────────────────────────
        market = {}
        for sym in consolidated_qty:
            market[sym] = self._fetch_market_data(sym)

        # ── Build consolidated holdings ────────────────────────────────────
        consolidated = []
        total_value = 0.0
        for sym, qty in sorted(consolidated_qty.items()):
            m = market[sym]
            price = m['price']
            value = qty * price
            total_value += value
            is_cash = m.get('is_cash', False)
            exp_ret = None if is_cash else self._expected_return(price, m['target_mean'])
            action  = 'HOLD' if is_cash else self._classify_action(exp_ret, m['rec_key'])
            consolidated.append({
                'symbol':            sym,
                'total_qty':         qty,
                'price':             round(price, 4) if is_cash else round(price, 2),
                'value':             round(value, 0),
                'target_mean':       m['target_mean'],
                'target_high':       m['target_high'],
                'expected_return':   exp_ret,
                'action':            action,
                'rec_key':           m['rec_key'],
                'name':              m['name'],
                'sector':            m['sector'],
                'is_cash':           is_cash,
                'is_commodity':      m.get('is_commodity', False),
                'trailing_return_1y': m.get('trailing_return_1y'),
                'commodity_role':    m.get('commodity_role'),
                'price_source':      m.get('price_source', 'regular'),
                'day_change_pct':    m.get('day_change_pct'),
                'currency':          m.get('currency'),
                'fx_rate':           m.get('fx_rate'),
            })

        consolidated.sort(key=lambda x: x['value'], reverse=True)
        for c in consolidated:
            c['allocation_pct'] = round(c['value'] / total_value * 100, 1) if total_value else 0

        # ── Second pass: classify commodity ETFs using allocation context ────
        for c in consolidated:
            if c.get('is_commodity'):
                sym = c['symbol']
                role_info = COMMODITY_ETFS[sym]
                action, rationale = self._classify_commodity_action(
                    c['trailing_return_1y'], c['allocation_pct'],
                    role_info['alloc_min'], role_info['alloc_max'], role_info['role'],
                )
                c['action']              = action
                c['commodity_rationale'] = rationale

        # ── Portfolio cash (from CASH_* positions inside portfolios) ──────
        portfolio_cash = sum(
            c['value'] for c in consolidated if c.get('is_cash')
        )
        equity_value = total_value - portfolio_cash

        # ── MTM (Mark-to-Market) — equities only, needs purchase_price ────
        # Aggregate cost basis per analysis symbol across all filtered positions
        cost_map = defaultdict(lambda: {'total_cost': 0.0, 'total_qty': 0.0, 'has_cost': False})
        for p in all_pos:
            asym = SYMBOL_ALIASES.get(p['symbol'], p['symbol'])
            if _parse_cash_symbol(asym):
                continue
            if p.get('purchase_price'):
                cost_map[asym]['total_cost'] += p['quantity'] * p['purchase_price']
                cost_map[asym]['total_qty']  += p['quantity']
                cost_map[asym]['has_cost'] = True

        mtm = []
        for c in consolidated:
            if c.get('is_cash'):
                continue
            sym  = c['symbol']
            mv   = c['value']
            cm   = cost_map.get(sym, {})
            if cm.get('has_cost') and cm['total_qty'] > 0:
                cost_basis   = round(cm['total_cost'], 0)
                avg_cost     = round(cm['total_cost'] / cm['total_qty'], 2)
                unreal_pnl   = round(mv - cost_basis, 0)
                unreal_pnl_pct = round((mv / cost_basis - 1) * 100, 1) if cost_basis else None
            else:
                cost_basis = avg_cost = unreal_pnl = unreal_pnl_pct = None
            mtm.append({
                'symbol':           sym,
                'total_qty':        c['total_qty'],
                'avg_cost':         avg_cost,
                'current_price':    c['price'],
                'cost_basis':       cost_basis,
                'market_value':     mv,
                'unrealized_pnl':   unreal_pnl,
                'unrealized_pnl_pct': unreal_pnl_pct,
            })

        # ── Fetch YTD baseline snapshot (used for fixed target + YTD P&L) ──
        # Done here — before summary — so target_25 is based on the immutable
        # first-run value, not the live price that changes every refresh.
        ytd_snap_pre = None
        try:
            ytd_snap_pre = self.snapshots.get_ytd_start_snapshot()
        except Exception as e:
            print(f'YTD pre-fetch error: {e}')

        # ── Portfolio summary ─────────────────────────────────────────────
        total_investable = total_value  # cash already inside total_value
        if ytd_snap_pre:
            pv_snap = ytd_snap_pre.get('portfolio_values', {})
            if selected_portfolios and pv_snap:
                # Sum only the selected portfolios' baseline values
                baseline_total = sum(
                    pv_snap.get(p, {}).get('total_value', 0)
                    for p in selected_portfolios
                ) or total_value
            else:
                baseline_total = ytd_snap_pre['total_value']
        else:
            baseline_total = total_value
        target_25 = baseline_total * 1.25
        weighted_ret = sum(
            (c['expected_return'] or 0) * c['value'] / equity_value
            for c in consolidated if not c.get('is_cash')
        ) if equity_value > 0 else 0

        # ── Advice engine — equities only (exclude cash & commodity ETFs) ──
        equities    = [c for c in consolidated if not c.get('is_cash') and not c.get('is_commodity')]
        commodities = [c for c in consolidated if c.get('is_commodity')]
        top_performers  = [c for c in equities if (c['expected_return'] or 0) >= 20]
        underperformers = [c for c in equities if (c['expected_return'] or 0) < 5
                           and c['action'] in ('REVIEW', 'SELL')]
        cash_deployment = self._cash_plan(equities, portfolio_cash)
        rebalancing     = self._rebalancing_plan(equities, underperformers, top_performers)

        # ── Positions by portfolio (with live prices) ─────────────────────
        positions_by_portfolio = defaultdict(list)
        for p in all_pos:
            asym  = SYMBOL_ALIASES.get(p['symbol'], p['symbol'])
            m     = market.get(asym, {})
            price = m.get('price', 0)
            is_cash = m.get('is_cash', False)
            exp_ret = None if is_cash else self._expected_return(price, m.get('target_mean'))
            action  = 'HOLD' if is_cash else self._classify_action(exp_ret, m.get('rec_key', ''))
            positions_by_portfolio[p['portfolio_name']].append({
                **p,
                'price':           round(price, 4) if is_cash else round(price, 2),
                'value':           round(p['quantity'] * price, 0),
                'expected_return': exp_ret,
                'action':          action,
                'is_cash':         is_cash,
            })

        # ── Market state (from first equity symbol) ───────────────────────────
        market_state_val = next(
            (market[sym].get('market_state', '')
             for sym in market
             if not _parse_cash_symbol(sym) and sym not in COMMODITY_ETFS),
            ''
        )

        # ── Save daily snapshot (all-portfolios, unfiltered) ─────────────────
        # Only snapshot when viewing all portfolios (avoids partial snapshots skewing YTD).
        # Captures both consolidated symbol values AND per-portfolio totals.
        all_pos_full = self.db.get_all_positions()
        portfolio_snap_vals = {}   # populated below when saving
        try:
            if not selected_portfolios:
                symbol_values = {
                    c['symbol']: {
                        'market_value': c['value'],
                        'price':        c['price'],
                        'total_qty':    c['total_qty'],
                    }
                    for c in consolidated
                }
                # Per-portfolio breakdown: total_value, equity_value, portfolio_cash
                pv_acc = defaultdict(lambda: {'total_value': 0.0, 'equity_value': 0.0,
                                              'portfolio_cash': 0.0})
                for p in all_pos:
                    asym  = SYMBOL_ALIASES.get(p['symbol'], p['symbol'])
                    price = market.get(asym, {}).get('price', 0)
                    val   = p['quantity'] * price
                    pname = p['portfolio_name']
                    pv_acc[pname]['total_value'] += val
                    if market.get(asym, {}).get('is_cash'):
                        pv_acc[pname]['portfolio_cash'] += val
                    else:
                        pv_acc[pname]['equity_value']   += val
                portfolio_snap_vals = {k: {fk: round(fv, 0) for fk, fv in v.items()}
                                       for k, v in pv_acc.items()}
                self.snapshots.save_snapshot(
                    total_value      = total_value,
                    equity_value     = equity_value,
                    portfolio_cash   = portfolio_cash,
                    symbol_values    = symbol_values,
                    portfolio_values = portfolio_snap_vals,
                )
        except Exception as e:
            print(f'Snapshot save error: {e}')

        # ── YTD P&L ───────────────────────────────────────────────────────────
        ytd = None
        try:
            ytd_snap = ytd_snap_pre  # use the snapshot fetched BEFORE today's save
            if ytd_snap:
                sv = ytd_snap.get('symbol_values', {})
                pv = ytd_snap.get('portfolio_values', {})

                # Total YTD: compare current filtered value vs filtered baseline
                ytd_pnl_total = round(total_value - baseline_total, 0)
                ytd_pnl_pct   = round((total_value / baseline_total - 1) * 100, 3) \
                                 if baseline_total else None

                # Per-symbol YTD: use snapshot price × current filtered qty
                # (avoids polluting filtered view with full-portfolio snapshot qty)
                symbol_ytd = {}
                for sym in consolidated_qty:
                    cur_val    = next((c['value'] for c in consolidated if c['symbol'] == sym), 0)
                    snap_price = sv.get(sym, {}).get('price', 0)
                    if snap_price:
                        start_val = snap_price * consolidated_qty[sym]
                        symbol_ytd[sym] = {
                            'value_at_start': round(start_val, 0),
                            'ytd_pnl':        round(cur_val - start_val, 0),
                            'ytd_pnl_pct':    round((cur_val / start_val - 1) * 100, 3)
                                              if start_val else None,
                        }

                # Per-portfolio YTD: compute for all visible portfolios
                portfolio_ytd = {}
                if pv:
                    # Current per-portfolio values from live positions
                    cur_pv_acc = defaultdict(float)
                    for p in all_pos:
                        asym  = SYMBOL_ALIASES.get(p['symbol'], p['symbol'])
                        price = market.get(asym, {}).get('price', 0)
                        cur_pv_acc[p['portfolio_name']] += p['quantity'] * price

                    visible = selected_portfolios if selected_portfolios else list(pv.keys())
                    for pname in visible:
                        if pname in pv:
                            start_val = pv[pname].get('total_value', 0)
                            cur_val   = cur_pv_acc.get(pname, 0)
                            if start_val:
                                portfolio_ytd[pname] = {
                                    'value_at_start': round(start_val, 0),
                                    'ytd_pnl':        round(cur_val - start_val, 0),
                                    'ytd_pnl_pct':    round((cur_val / start_val - 1) * 100, 3),
                                }

                ytd = {
                    'snapshot_date':        ytd_snap['date'],
                    'total_value_at_start': round(baseline_total, 0),
                    'ytd_pnl':              ytd_pnl_total,
                    'ytd_pnl_pct':          ytd_pnl_pct,
                    'symbol_ytd':           symbol_ytd,
                    'portfolio_ytd':        portfolio_ytd,
                }
        except Exception as e:
            print(f'YTD computation error: {e}')

        return {
            'positions_by_portfolio': dict(positions_by_portfolio),
            'consolidated': consolidated,
            'mtm': mtm,
            'ytd': ytd,
            'summary': {
                'total_portfolio_value': round(total_value, 0),
                'portfolio_cash':        round(portfolio_cash, 0),
                'equity_value':          round(equity_value, 0),
                'total_investable':      round(total_investable, 0),
                'target_25pct':          round(target_25, 0),
                'baseline_total':        round(baseline_total, 0),
                'weighted_expected_return_pct': round(weighted_ret, 1),
                'on_track':              weighted_ret >= 25.0,
                'gap_to_target_pct':     round(25.0 - weighted_ret, 1),
                'position_count':        len(consolidated),
                'portfolio_count':       len(set(p['portfolio_name'] for p in all_pos_full)),
                'selected_portfolios':   sorted(set(p['portfolio_name'] for p in all_pos)),
            },
            'advice': {
                'top_performers':  top_performers,
                'underperformers': underperformers,
                'cash_deployment': cash_deployment,
                'rebalancing':     rebalancing,
                'hedges': [
                    {
                        'symbol':            c['symbol'],
                        'name':              c['name'],
                        'action':            c['action'],
                        'value':             c['value'],
                        'allocation_pct':    c['allocation_pct'],
                        'trailing_return_1y': c['trailing_return_1y'],
                        'commodity_role':    c['commodity_role'],
                        'commodity_rationale': c.get('commodity_rationale'),
                    }
                    for c in commodities
                ],
            },
            'market_state': market_state_val,
            'generated_at': datetime.now().isoformat(),
        }

    def _cash_plan(self, consolidated: list, cash: float) -> list:
        """Allocate available cash among top expected-return symbols."""
        buys = sorted(
            [c for c in consolidated if (c['expected_return'] or 0) >= 15 and c['price'] > 0],
            key=lambda x: x['expected_return'],
            reverse=True
        )
        if not buys:
            return [{'note': 'No clear buy candidates found. Consider holding cash or diversifying.'}]

        plan = []
        remaining = cash
        # Weights: top pick 40%, 2nd 30%, 3rd 20%, rest 10% spread
        weights = [0.40, 0.30, 0.20] + [0.10 / max(len(buys) - 3, 1)] * max(len(buys) - 3, 0)
        weights = weights[:len(buys)]
        # Normalize
        total_w = sum(weights)
        weights = [w / total_w for w in weights]

        for i, candidate in enumerate(buys[:6]):
            alloc = round(remaining * weights[i], 0) if i < len(weights) else 0
            if alloc < candidate['price']:
                continue
            shares = int(alloc // candidate['price'])
            cost = round(shares * candidate['price'], 0)
            plan.append({
                'symbol':          candidate['symbol'],
                'name':            candidate['name'],
                'shares_to_buy':   shares,
                'cost':            cost,
                'price':           candidate['price'],
                'expected_return': candidate['expected_return'],
                'rationale': (
                    f"Analyst target ${candidate['target_mean']} implies "
                    f"{candidate['expected_return']}% upside. "
                    f"Buy {shares} shares @ ${candidate['price']} = ${cost:,.0f}."
                ),
            })

        return plan

    def _rebalancing_plan(self, consolidated, underperformers, top_performers) -> list:
        """Suggest sell + buy pairs to improve overall portfolio return."""
        plan = []
        for u in underperformers:
            if u['value'] < 500:  # Skip tiny positions
                continue
            rationale = (
                f"Expected return only {u['expected_return']}%. "
                f"Selling {int(u['total_qty'])} shares (${u['value']:,.0f}) "
                f"would free capital for higher-conviction names."
            )
            plan.append({
                'action':  'REDUCE',
                'symbol':  u['symbol'],
                'name':    u['name'],
                'value':   u['value'],
                'expected_return': u['expected_return'],
                'rationale': rationale,
            })

        if top_performers and plan:
            best = top_performers[0]
            plan.append({
                'action':   'REDIRECT',
                'symbol':   best['symbol'],
                'name':     best['name'],
                'expected_return': best['expected_return'],
                'rationale': (
                    f"Proceeds from reduces above could be redeployed into "
                    f"{best['symbol']} ({best['expected_return']}% expected return)."
                ),
            })
        return plan
