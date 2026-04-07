import yfinance as yf
from datetime import datetime, timedelta


class FundamentalsService:
    """Fetch company fundamentals from yfinance with in-memory caching."""

    def __init__(self):
        self._cache = {}          # symbol -> {'data': dict, 'ts': datetime}
        self._cache_ttl = 240     # minutes (4 hours)

    def _cached(self, symbol):
        entry = self._cache.get(symbol)
        if entry and (datetime.now() - entry['ts']) < timedelta(minutes=self._cache_ttl):
            return entry['data']
        return None

    def get_fundamentals(self, symbol: str) -> dict:
        cached = self._cached(symbol)
        if cached:
            print(f"⚡ {symbol}: serving cached fundamentals")
            return cached

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}

            result = {
                'symbol': symbol,
                'key_stats': self._key_stats(info),
                'analyst': self._analyst(ticker, info),
                'income': self._income(ticker),
                'balance_sheet': self._balance_sheet(ticker),
                'cash_flow': self._cash_flow(ticker),
                'fetched_at': datetime.now().isoformat(),
            }

            self._cache[symbol] = {'data': result, 'ts': datetime.now()}
            return result

        except Exception as e:
            print(f"Error fetching fundamentals for {symbol}: {e}")
            return {'symbol': symbol, 'error': str(e)}

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_large(v):
        """Format large dollar amounts as $X.XXB / $X.XXT / $X.XXM."""
        if v is None:
            return None
        v = float(v)
        if abs(v) >= 1e12:
            return f'${v/1e12:.2f}T'
        if abs(v) >= 1e9:
            return f'${v/1e9:.2f}B'
        if abs(v) >= 1e6:
            return f'${v/1e6:.2f}M'
        return f'${v:,.0f}'

    @staticmethod
    def _pct(v):
        if v is None:
            return None
        return round(float(v) * 100, 2)

    @staticmethod
    def _round(v, n=2):
        if v is None:
            return None
        try:
            return round(float(v), n)
        except Exception:
            return None

    # ── sections ─────────────────────────────────────────────────────────────

    def _key_stats(self, info):
        return {
            'market_cap':       self._fmt_large(info.get('marketCap')),
            'market_cap_raw':   info.get('marketCap'),
            'pe_trailing':      self._round(info.get('trailingPE')),
            'pe_forward':       self._round(info.get('forwardPE')),
            'eps_trailing':     self._round(info.get('trailingEps')),
            'eps_forward':      self._round(info.get('forwardEps')),
            'beta':             self._round(info.get('beta')),
            'week52_high':      self._round(info.get('fiftyTwoWeekHigh')),
            'week52_low':       self._round(info.get('fiftyTwoWeekLow')),
            'dividend_yield':   self._pct(info.get('dividendYield')),
            'payout_ratio':     self._pct(info.get('payoutRatio')),
            'profit_margin':    self._pct(info.get('profitMargins')),
            'operating_margin': self._pct(info.get('operatingMargins')),
            'roe':              self._pct(info.get('returnOnEquity')),
            'roa':              self._pct(info.get('returnOnAssets')),
            'revenue_growth':   self._pct(info.get('revenueGrowth')),
            'earnings_growth':  self._pct(info.get('earningsGrowth')),
            'current_ratio':    self._round(info.get('currentRatio')),
            'debt_to_equity':   self._round(info.get('debtToEquity')),
            'price_to_book':    self._round(info.get('priceToBook')),
            'shares_outstanding': self._fmt_large(info.get('sharesOutstanding')),
        }

    def _analyst(self, ticker, info):
        result = {
            'target_mean':   self._round(info.get('targetMeanPrice')),
            'target_high':   self._round(info.get('targetHighPrice')),
            'target_low':    self._round(info.get('targetLowPrice')),
            'current_price': self._round(info.get('currentPrice') or info.get('regularMarketPrice')),
            'recommendation': info.get('recommendationKey', '').upper(),
            'num_analysts':  info.get('numberOfAnalystOpinions'),
            'strong_buy': 0, 'buy': 0, 'hold': 0, 'sell': 0, 'strong_sell': 0,
        }

        try:
            summary = ticker.recommendations_summary
            if summary is not None and not summary.empty:
                row = summary.iloc[0]
                result['strong_buy']  = int(row.get('strongBuy', 0))
                result['buy']         = int(row.get('buy', 0))
                result['hold']        = int(row.get('hold', 0))
                result['sell']        = int(row.get('sell', 0))
                result['strong_sell'] = int(row.get('strongSell', 0))
        except Exception:
            pass

        return result

    def _income(self, ticker):
        """Last 4 quarters: Total Revenue, Gross Profit, Net Income."""
        rows = []
        try:
            stmt = ticker.quarterly_income_stmt
            if stmt is None or stmt.empty:
                stmt = ticker.quarterly_financials
            if stmt is None or stmt.empty:
                return rows

            def _get_row(names):
                for n in names:
                    matches = [c for c in stmt.index if n.lower() in c.lower()]
                    if matches:
                        return stmt.loc[matches[0]]
                return None

            rev_s   = _get_row(['Total Revenue', 'Revenue'])
            gross_s = _get_row(['Gross Profit'])
            net_s   = _get_row(['Net Income', 'Net Income Common Stockholders'])

            cols = stmt.columns[:4]  # most recent 4 quarters
            for col in cols:
                period = col.strftime('%b %Y') if hasattr(col, 'strftime') else str(col)[:7]
                rows.append({
                    'period':       period,
                    'revenue':      self._fmt_large(rev_s[col] if rev_s is not None else None),
                    'revenue_raw':  int(rev_s[col]) if rev_s is not None and rev_s[col] == rev_s[col] else None,
                    'gross_profit': self._fmt_large(gross_s[col] if gross_s is not None else None),
                    'net_income':   self._fmt_large(net_s[col] if net_s is not None else None),
                    'net_income_raw': int(net_s[col]) if net_s is not None and net_s[col] == net_s[col] else None,
                })
        except Exception as e:
            print(f"Income fetch error: {e}")
        return rows

    def _balance_sheet(self, ticker):
        try:
            bs = ticker.quarterly_balance_sheet
            if bs is None or bs.empty:
                return {}
            col = bs.columns[0]  # most recent quarter

            def _get(names):
                for n in names:
                    matches = [r for r in bs.index if n.lower() in r.lower()]
                    if matches:
                        v = bs.loc[matches[0], col]
                        return self._fmt_large(v) if v == v else None
                return None

            return {
                'period':           col.strftime('%b %Y') if hasattr(col, 'strftime') else str(col)[:7],
                'total_assets':     _get(['Total Assets']),
                'total_debt':       _get(['Total Debt', 'Long Term Debt']),
                'cash':             _get(['Cash And Cash Equivalents', 'Cash Cash Equivalents']),
                'total_equity':     _get(['Stockholders Equity', 'Total Equity']),
                'current_assets':   _get(['Current Assets']),
                'current_liabilities': _get(['Current Liabilities']),
            }
        except Exception as e:
            print(f"Balance sheet error: {e}")
            return {}

    def _cash_flow(self, ticker):
        try:
            cf = ticker.quarterly_cashflow
            if cf is None or cf.empty:
                return {}
            col = cf.columns[0]

            def _get(names):
                for n in names:
                    matches = [r for r in cf.index if n.lower() in r.lower()]
                    if matches:
                        v = cf.loc[matches[0], col]
                        return self._fmt_large(v) if v == v else None
                return None

            operating = _get(['Operating Cash Flow', 'Cash From Operations'])
            capex     = _get(['Capital Expenditure', 'Capital Expenditures'])

            # Free Cash Flow = Operating CF - CapEx (compute if missing)
            fcf = _get(['Free Cash Flow'])

            return {
                'period':       col.strftime('%b %Y') if hasattr(col, 'strftime') else str(col)[:7],
                'operating_cf': operating,
                'capex':        capex,
                'free_cf':      fcf,
            }
        except Exception as e:
            print(f"Cash flow error: {e}")
            return {}
