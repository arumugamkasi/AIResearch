import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './PortfolioModal.css';
import { getApiUrl } from '../config';

const ACTION_META = {
  STRONG_BUY: { label: 'Strong Buy', cls: 'action-strong-buy' },
  BUY:        { label: 'Buy',         cls: 'action-buy'        },
  HOLD:       { label: 'Hold',        cls: 'action-hold'       },
  REVIEW:     { label: 'Review',      cls: 'action-review'     },
  SELL:       { label: 'Sell',        cls: 'action-sell'       },
  TRIM:       { label: 'Trim',        cls: 'action-trim'       },
  ADD:        { label: 'Add',         cls: 'action-add'        },
};

function fmt(v, prefix = '$') {
  if (v == null) return '—';
  const n = Number(v);
  if (Math.abs(n) >= 1e6) return `${prefix}${(n / 1e6).toFixed(2)}M`;
  if (Math.abs(n) >= 1e3) return `${prefix}${(n / 1e3).toFixed(1)}K`;
  return `${prefix}${n.toLocaleString()}`;
}

function fmtPct(v) {
  if (v == null) return '—';
  const n = Number(v);
  const sign = n >= 0 ? '+' : '';
  // Use enough decimal places so small intraday moves show non-zero
  if (Math.abs(n) < 0.1) return `${sign}${n.toFixed(3)}%`;
  if (Math.abs(n) < 1)   return `${sign}${n.toFixed(2)}%`;
  return `${sign}${n.toFixed(1)}%`;
}

function ActionBadge({ action }) {
  const meta = ACTION_META[action] || { label: action, cls: 'action-review' };
  return <span className={`action-badge ${meta.cls}`}>{meta.label}</span>;
}

const EMPTY_FORM = { portfolio: '', newPortfolioName: '', symbol: '', quantity: '', avg_price: '' };

export default function PortfolioModal({ onClose }) {
  // Positions (fast load)
  const [positions, setPositions] = useState({});  // {portfolio_name: [...]}
  const [loadingPos, setLoadingPos] = useState(true);
  const [posError, setPosError]     = useState(null);
  const [activePortfolio, setActivePortfolio] = useState(null);

  // Portfolio filter (default: all selected)
  const [selectedPortfolios, setSelectedPortfolios] = useState(null); // null = all

  // Add / edit form
  const [form, setForm]           = useState(EMPTY_FORM);
  const [formError, setFormError] = useState('');
  const [formSaving, setFormSaving] = useState(false);
  const [editingKey, setEditingKey] = useState(null);

  // Analysis (slow, on demand)
  const [analysis, setAnalysis]     = useState(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisError, setAnalysisError]     = useState(null);
  const [showAnalysis, setShowAnalysis]       = useState(false);

  // Auto-refresh
  const [autoRefreshSecs, setAutoRefreshSecs] = useState(0);  // 0 = off
  const [countdown, setCountdown] = useState(0);
  const loadingRef = useRef(false);

  // Alert system
  const [alertConfig, setAlertConfig] = useState({ threshold_pct: 5, email_enabled: false, email_to: 'arumugamkasi@gmail.com' });
  const [showAlertConfig, setShowAlertConfig] = useState(false);
  const [activeAlerts, setActiveAlerts] = useState([]);

  // ── Load positions (DB read only — instant) ──────────────────────────────
  const loadPositions = useCallback(async () => {
    setLoadingPos(true);
    setPosError(null);
    try {
      const res = await axios.get(getApiUrl('/api/portfolio/positions'));
      setPositions(res.data || {});
      const names = Object.keys(res.data || {}).sort();
      if (names.length > 0) setActivePortfolio(prev => prev || names[0]);
    } catch {
      setPosError('Could not load positions. Is the backend running?');
    } finally {
      setLoadingPos(false);
    }
  }, []);

  useEffect(() => { loadPositions(); }, [loadPositions]);

  // ── Load alert config ─────────────────────────────────────────────────────
  const loadAlertConfig = useCallback(async () => {
    try {
      const res = await axios.get(getApiUrl('/api/alerts/config'));
      setAlertConfig(res.data);
    } catch {}
  }, []);

  useEffect(() => { loadAlertConfig(); }, [loadAlertConfig]);

  // Escape to close
  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, [onClose]);

  // ── Add / Update position ────────────────────────────────────────────────
  const handleAdd = async (e) => {
    e.preventDefault();
    setFormError('');
    const portfolio = form.portfolio === 'NEW'
      ? form.newPortfolioName.trim().toUpperCase()
      : form.portfolio.trim().toUpperCase();
    const symbol   = form.symbol.trim().toUpperCase();
    const quantity = parseFloat(form.quantity);
    const avg_price = form.avg_price ? parseFloat(form.avg_price) : undefined;

    if (!portfolio) { setFormError('Portfolio name is required'); return; }
    if (!symbol)    { setFormError('Symbol is required'); return; }
    if (!form.quantity || isNaN(quantity) || quantity <= 0) {
      setFormError('Quantity must be a positive number'); return;
    }

    setFormSaving(true);
    try {
      await axios.post(getApiUrl('/api/portfolio/positions'), {
        portfolio, symbol, quantity,
        purchase_price: avg_price || null,
      });
      setForm(EMPTY_FORM);
      setEditingKey(null);
      setAnalysis(null);  // invalidate analysis
      await loadPositions();
    } catch {
      setFormError('Failed to save position. Please try again.');
    } finally {
      setFormSaving(false);
    }
  };

  const handleEditPosition = (portfolioName, pos) => {
    setForm({
      portfolio:        portfolioName,
      newPortfolioName: '',
      symbol:           pos.symbol,
      quantity:         String(pos.quantity),
      avg_price:        pos.purchase_price ? String(pos.purchase_price) : '',
    });
    setEditingKey(`${portfolioName}/${pos.symbol}`);
    setFormError('');
  };

  const handleCancelEdit = () => {
    setForm(EMPTY_FORM);
    setEditingKey(null);
    setFormError('');
  };

  // ── Delete position ──────────────────────────────────────────────────────
  const handleDelete = async (portfolio, symbol) => {
    if (!window.confirm(`Remove ${symbol} from ${portfolio}?`)) return;
    try {
      await axios.delete(getApiUrl(`/api/portfolio/positions/${portfolio}/${symbol}`));
      setAnalysis(null);  // invalidate analysis
      await loadPositions();
    } catch {
      // ignore
    }
  };

  // ── Portfolio filter toggle ───────────────────────────────────────────────
  const togglePortfolio = (name) => {
    const allNames = Object.keys(positions).sort();
    const current  = selectedPortfolios || allNames;
    const next = current.includes(name)
      ? current.filter(n => n !== name)
      : [...current, name];
    // If all selected, reset to null (= all)
    setSelectedPortfolios(next.length === allNames.length ? null : (next.length ? next : current));
    setAnalysis(null);
  };

  const isPortfolioSelected = (name) => {
    if (!selectedPortfolios) return true;
    return selectedPortfolios.includes(name);
  };

  // ── Run analysis (yfinance — slow) ────────────────────────────────────────
  // silent=true: background refresh — keep existing data visible, no spinner
  const runAnalysis = useCallback(async (silent = false) => {
    if (loadingRef.current) return;   // skip overlapping refreshes
    loadingRef.current = true;
    if (!silent) setLoadingAnalysis(true);
    setAnalysisError(null);
    setShowAnalysis(true);
    try {
      const allNames = Object.keys(positions).sort();
      const sel = selectedPortfolios || allNames;
      const param = sel.length < allNames.length ? `?portfolios=${sel.join(',')}` : '';
      const res = await axios.get(getApiUrl(`/api/portfolio/analysis${param}`));
      setAnalysis(res.data);

      // ── Check for price-drop alerts ──────────────────────────────────────
      const consolidatedData = res.data?.consolidated || [];
      const triggered = consolidatedData.filter(c =>
        !c.is_cash && c.day_change_pct != null && c.day_change_pct <= -alertConfig.threshold_pct
      );
      setActiveAlerts(triggered);
      if (triggered.length > 0 && document.hidden) {
        if (Notification.permission === 'granted') {
          new Notification('⚠️ Portfolio Alert', {
            body: triggered.map(c => `${c.symbol}: ${c.day_change_pct.toFixed(1)}%`).join('\n'),
          });
        } else if (Notification.permission !== 'denied') {
          Notification.requestPermission();
        }
      }
    } catch {
      setAnalysisError('Analysis failed. Check backend logs.');
    } finally {
      setLoadingAnalysis(false);
      loadingRef.current = false;
    }
  }, [positions, selectedPortfolios, alertConfig]);

  // ── Auto-refresh interval ─────────────────────────────────────────────────
  useEffect(() => {
    if (autoRefreshSecs === 0 || !showAnalysis) { setCountdown(0); return; }
    setCountdown(autoRefreshSecs);
    const refreshId  = setInterval(() => runAnalysis(true), autoRefreshSecs * 1000);
    const countdownId = setInterval(() => {
      setCountdown(prev => (prev <= 1 ? autoRefreshSecs : prev - 1));
    }, 1000);
    return () => { clearInterval(refreshId); clearInterval(countdownId); };
  }, [autoRefreshSecs, showAnalysis, runAnalysis]);

  // ── Derived ──────────────────────────────────────────────────────────────
  const portfolioNames  = Object.keys(positions).sort();
  const activePositions = (positions[activePortfolio] || [])
    .slice()
    .sort((a, b) => b.quantity - a.quantity);
  const totalPositions  = Object.values(positions).reduce((s, arr) => s + arr.length, 0);
  const summary      = analysis?.summary;
  const advice       = analysis?.advice;
  const consolidated = analysis?.consolidated || [];
  const mtm          = analysis?.mtm || [];
  const ytd          = analysis?.ytd;
  const portfolioYtd = ytd?.portfolio_ytd || {};   // {PNAME: {ytd_pnl, ytd_pnl_pct, value_at_start}}
  const mtmWithCost  = mtm.filter(r => r.cost_basis != null);
  const totalCostBasis   = mtmWithCost.reduce((s, r) => s + r.cost_basis, 0);
  const totalMarketValue = mtmWithCost.reduce((s, r) => s + r.market_value, 0);
  const totalUnrealPnl   = totalMarketValue - totalCostBasis;

  return (
    <div className="portfolio-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="portfolio-modal">

        {/* ── Header ── */}
        <div className="pm-header">
          <div className="pm-header-left">
            <h2 className="pm-title">💼 Portfolio Manager</h2>
            {totalPositions > 0 && (
              <span className="pm-pos-count">{totalPositions} positions · {portfolioNames.length} portfolios</span>
            )}
            {summary && (
              <span className={`pm-track-badge ${summary.on_track ? 'on-track' : 'off-track'}`}>
                {summary.on_track
                  ? `✅ On Track · ${summary.weighted_expected_return_pct}% wtd return`
                  : `⚠️ ${summary.gap_to_target_pct}% below 25% target`}
              </span>
            )}
          </div>
          <div className="pm-header-right">
            {/* Market state + auto-refresh controls */}
            {showAnalysis && (
              <div className="pm-refresh-ctrl">
                {analysis?.market_state && (
                  <span className={`pm-market-state pm-mkt-${(analysis.market_state || 'closed').toLowerCase()}`}>
                    {analysis.market_state === 'REGULAR'                          ? '🟢 Live'
                      : analysis.market_state === 'PRE'                           ? '🌅 Pre-mkt'
                      : (analysis.market_state === 'POST' ||
                         analysis.market_state === 'POSTPOST')                    ? '🌙 After-hrs'
                      : '⚫ Closed'}
                  </span>
                )}
                <span className="pm-refresh-label">Refresh:</span>
                {[0, 30, 60, 90, 120, 180].map(s => (
                  <button
                    key={s}
                    className={`pm-auto-btn ${autoRefreshSecs === s ? 'active' : ''}`}
                    onClick={() => setAutoRefreshSecs(s)}
                    title={s === 0 ? 'No auto-refresh' : `Refresh every ${s}s`}
                  >
                    {s === 0 ? 'Off' : `${s}s`}
                  </button>
                ))}
              </div>
            )}
            {!showAnalysis && totalPositions > 0 && (
              <button className="pm-analyse-btn" onClick={runAnalysis} disabled={loadingAnalysis}>
                {loadingAnalysis ? '⏳ Fetching prices…' : '📊 Run Analysis'}
              </button>
            )}
            {showAnalysis && (
              <button className="pm-analyse-btn secondary" onClick={runAnalysis} disabled={loadingAnalysis}>
                {loadingAnalysis ? '⏳ …' : '🔄 Refresh'}
              </button>
            )}
            {countdown > 0 && <span className="pm-next-refresh">{countdown}s</span>}
            <button
              className={`pm-alert-btn ${activeAlerts.length > 0 ? 'firing' : ''}`}
              onClick={() => setShowAlertConfig(s => !s)}
              title={activeAlerts.length > 0 ? `${activeAlerts.length} alert(s) firing` : alertConfig.email_enabled ? 'Alerts on' : 'Alerts off'}
            >
              {activeAlerts.length > 0 ? '🚨' : alertConfig.email_enabled ? '🔔' : '🔕'}
            </button>
            <button className="pm-close" onClick={onClose}>✕</button>
          </div>
        </div>

        {/* ── Alert Config Panel ── */}
        {showAlertConfig && (
          <div className="pm-alert-config">
            <span className="pm-alert-config-label">Alert when drop &gt;</span>
            <input type="number" className="pm-alert-input" value={alertConfig.threshold_pct}
              onChange={e => setAlertConfig(p => ({...p, threshold_pct: parseFloat(e.target.value)}))}
              min="1" max="50" step="0.5" style={{width:'3.5rem'}}
            />
            <span className="pm-alert-config-label">%</span>
            <label className="pm-alert-toggle">
              <input type="checkbox" checked={alertConfig.email_enabled}
                onChange={e => setAlertConfig(p => ({...p, email_enabled: e.target.checked}))}
              />
              Email alerts
            </label>
            <button className="pm-alert-save" onClick={async () => {
              try {
                await axios.post(getApiUrl('/api/alerts/config'), alertConfig);
                setShowAlertConfig(false);
              } catch (e) {
                alert('Could not save alert config — is the backend running?\n' + (e.message || e));
              }
            }}>Save</button>
          </div>
        )}

        {/* ── Portfolio Filter Bar ── */}
        {portfolioNames.length > 1 && (
          <div className="pm-filter-bar">
            <span className="pm-filter-label">Portfolio:</span>
            {portfolioNames.map(name => {
              const py = portfolioYtd[name];
              return (
                <button
                  key={name}
                  className={`pm-filter-btn ${isPortfolioSelected(name) ? 'active' : ''}`}
                  onClick={() => togglePortfolio(name)}
                  title={py ? `YTD: ${py.ytd_pnl >= 0 ? '+' : ''}${fmt(py.ytd_pnl)} (${fmtPct(py.ytd_pnl_pct)}) from ${fmt(py.value_at_start)}` : name}
                >
                  <span>{name}</span>
                  {py && (
                    <span className={`pm-filter-ytd ${py.ytd_pnl >= 0 ? 'pos' : 'neg'}`}>
                      {py.ytd_pnl >= 0 ? '+' : ''}{fmt(py.ytd_pnl)}
                    </span>
                  )}
                </button>
              );
            })}
            {selectedPortfolios && (
              <button className="pm-filter-reset" onClick={() => { setSelectedPortfolios(null); setAnalysis(null); }}>
                All
              </button>
            )}
          </div>
        )}

        <div className="pm-body">

          {/* ══ LEFT — Portfolios & Add Form ══ */}
          <div className="pm-col pm-left">

            {/* Add / Update Position Form */}
            <div className="pm-section-title">
              {editingKey ? `✏️ Editing ${editingKey}` : 'Add / Update Position'}
              {editingKey && (
                <button type="button" className="pm-cancel-edit" onClick={handleCancelEdit}>✕ Cancel</button>
              )}
            </div>
            <form className="pm-add-form" onSubmit={handleAdd}>
              {/* Portfolio selector */}
              <select
                value={form.portfolio}
                onChange={e => setForm(f => ({ ...f, portfolio: e.target.value, newPortfolioName: '' }))}
                className="pm-input"
              >
                <option value="">Select portfolio…</option>
                {portfolioNames.map(n => <option key={n} value={n}>{n}</option>)}
                <option value="NEW">+ New portfolio…</option>
              </select>
              {form.portfolio === 'NEW' && (
                <input
                  className="pm-input"
                  placeholder="Portfolio name (e.g. MYPORT)"
                  value={form.newPortfolioName}
                  onChange={e => setForm(f => ({ ...f, newPortfolioName: e.target.value }))}
                  autoFocus
                />
              )}

              {/* Symbol */}
              <input
                className="pm-input"
                placeholder="Ticker symbol (e.g. NVDA)"
                value={form.symbol}
                onChange={e => setForm(f => ({ ...f, symbol: e.target.value.toUpperCase() }))}
              />

              {/* Quantity */}
              <input
                className="pm-input"
                type="number"
                min="0"
                step="any"
                placeholder="Quantity (shares)"
                value={form.quantity}
                onChange={e => setForm(f => ({ ...f, quantity: e.target.value }))}
              />

              {/* Avg price (optional) */}
              <input
                className="pm-input"
                type="number"
                min="0"
                step="any"
                placeholder="Avg purchase price (optional)"
                value={form.avg_price}
                onChange={e => setForm(f => ({ ...f, avg_price: e.target.value }))}
              />

              {formError && <div className="pm-add-error">{formError}</div>}
              <button type="submit" className="pm-add-btn" disabled={formSaving}>
                {formSaving ? 'Saving…' : editingKey ? 'Update Position' : 'Save Position'}
              </button>
            </form>

            {/* Portfolio Tabs + Positions */}
            {loadingPos && <div className="pm-loading-small">Loading positions…</div>}
            {posError   && <div className="pm-add-error" style={{ marginTop: '1rem' }}>{posError}</div>}

            {portfolioNames.length > 0 && (
              <div style={{ marginTop: '1.25rem' }}>
                <div className="pm-section-title">Positions</div>
                <div className="pm-portfolio-tabs">
                  {portfolioNames.map(name => {
                    const py = portfolioYtd[name];
                    return (
                      <button
                        key={name}
                        className={`pm-tab ${activePortfolio === name ? 'active' : ''}`}
                        onClick={() => setActivePortfolio(name)}
                        title={py ? `YTD: ${py.ytd_pnl >= 0 ? '+' : ''}${fmt(py.ytd_pnl)} (${fmtPct(py.ytd_pnl_pct)})` : ''}
                      >
                        <div>{name}</div>
                        {py && (
                          <div className={`pm-tab-ytd ${py.ytd_pnl >= 0 ? 'pos' : 'neg'}`}>
                            {py.ytd_pnl >= 0 ? '+' : ''}{fmt(py.ytd_pnl)}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>

                {activePortfolio && (
                  <table className="pm-table">
                    <thead>
                      <tr>
                        <th>Symbol</th>
                        <th className="num-cell">Qty</th>
                        <th className="num-cell">Avg $</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {activePositions.map(pos => {
                        const key = `${activePortfolio}/${pos.symbol}`;
                        const isEditing = editingKey === key;
                        return (
                          <tr
                            key={pos.symbol}
                            className={`pm-pos-row ${isEditing ? 'pm-pos-editing' : ''}`}
                            onClick={() => handleEditPosition(activePortfolio, pos)}
                            title="Click to edit"
                          >
                            <td className="sym-label">{pos.symbol}</td>
                            <td className="num-cell">{pos.quantity}</td>
                            <td className="num-cell">
                              {pos.purchase_price ? `$${pos.purchase_price}` : '—'}
                            </td>
                            <td>
                              <button
                                className="pm-del-btn"
                                onClick={(e) => { e.stopPropagation(); handleDelete(activePortfolio, pos.symbol); }}
                                title="Remove position"
                              >×</button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {!loadingPos && totalPositions === 0 && !posError && (
              <div className="pm-empty-hint">
                No positions yet. Use the form above to add your first position.
              </div>
            )}
          </div>

          {/* ══ MIDDLE — Consolidated (after analysis) ══ */}
          <div className="pm-col pm-middle">
            {!showAnalysis && (
              <div className="pm-analysis-prompt">
                <div className="pm-analysis-prompt-icon">📊</div>
                <div className="pm-analysis-prompt-text">
                  {totalPositions > 0
                    ? <>Add your positions on the left, then click <strong>Run Analysis</strong> to see consolidated holdings with live prices and buy/sell signals.</>
                    : <>Start by adding your stock positions on the left panel.</>
                  }
                </div>
              </div>
            )}

            {showAnalysis && loadingAnalysis && (
              <div className="pm-loading">
                <span className="spinner">⏳</span>
                Fetching live prices &amp; analyst targets for {totalPositions} positions…
              </div>
            )}

            {showAnalysis && analysisError && (
              <div className="pm-error">{analysisError}</div>
            )}

            {analysis && !loadingAnalysis && (
              <>
                {/* ── Alert Banner ── */}
                {activeAlerts.length > 0 && (
                  <div className="pm-alert-banner">
                    <span className="pm-alert-icon">⚠️</span>
                    <span className="pm-alert-text">
                      {activeAlerts.map(a => (
                        <span key={a.symbol} className="pm-alert-item">
                          <strong>{a.symbol}</strong> {a.day_change_pct.toFixed(1)}%
                        </span>
                      ))}
                    </span>
                    <span className="pm-alert-label">down &gt;{alertConfig.threshold_pct}% today</span>
                  </div>
                )}

                <div className="pm-section-title">
                  Consolidated Holdings
                  <span className="pm-section-sub">
                    {summary?.selected_portfolios?.join(', ')}
                  </span>
                </div>

                {summary && (
                  <div className="pm-summary-strip" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
                    <div className="pm-stat"><span>Equities</span><strong>{fmt(summary.equity_value)}</strong></div>
                    <div className="pm-stat"><span>Cash</span><strong className="pos">{fmt(summary.portfolio_cash)}</strong></div>
                    <div className="pm-stat"><span>Total</span><strong>{fmt(summary.total_investable)}</strong></div>
                    <div className="pm-stat">
                      <span>Target (25%)</span>
                      <strong className="target">
                        {fmt(summary.target_25pct)}
                        {summary.baseline_total && summary.baseline_total !== summary.total_investable && (
                          <span className="pm-baseline-ref"> (from {fmt(summary.baseline_total)})</span>
                        )}
                      </strong>
                    </div>
                    {ytd ? (
                      <div className="pm-stat">
                        <span>YTD P&amp;L <em style={{fontSize:'0.6rem', opacity:0.7}}>since {ytd.snapshot_date}</em></span>
                        <strong className={ytd.ytd_pnl >= 0 ? 'pos' : 'neg'}>
                          {ytd.ytd_pnl >= 0 ? '+' : ''}{fmt(ytd.ytd_pnl)}
                          <span style={{fontSize:'0.7rem', marginLeft:'0.3rem'}}>
                            ({fmtPct(ytd.ytd_pnl_pct)})
                          </span>
                        </strong>
                      </div>
                    ) : (
                      <div className="pm-stat">
                        <span>YTD P&amp;L</span>
                        <strong style={{color:'var(--text-muted)', fontSize:'0.72rem'}}>Run again tomorrow</strong>
                      </div>
                    )}
                  </div>
                )}

                <table className="pm-table pm-consolidated-table">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Qty</th>
                      <th>Price</th>
                      <th>Value</th>
                      <th>Alloc</th>
                      <th>Target</th>
                      <th>Exp Ret</th>
                      <th>YTD P&amp;L</th>
                      <th>Signal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {consolidated.map(c => {
                      const sy = ytd?.symbol_ytd?.[c.symbol];
                      return (
                      <tr key={c.symbol} className={c.is_cash ? 'pm-cash-row' : ''}>
                        <td>
                          <div className="sym-name">{c.symbol}</div>
                          <div className="sym-sector">{c.sector || ''}</div>
                        </td>
                        <td>{c.is_cash ? fmt(c.total_qty, '') : c.total_qty}</td>
                        <td>
                          {c.is_cash
                            ? (c.currency === 'USD' ? '$1.00' : `$${c.fx_rate}`)
                            : <>
                                ${c.price}
                                {c.price_source === 'pre'  && <span className="pm-price-ext" title="Pre-market price"> pre</span>}
                                {c.price_source === 'post' && <span className="pm-price-ext" title="After-hours price"> aft</span>}
                                {c.day_change_pct != null && (
                                  <span
                                    className={`pm-day-chg ${c.day_change_pct >= 0 ? 'pos' : 'neg'}`}
                                    title={`vs yesterday's close`}
                                  >
                                    {c.day_change_pct >= 0 ? '▲' : '▼'}{Math.abs(c.day_change_pct).toFixed(2)}%
                                  </span>
                                )}
                              </>}
                        </td>
                        <td className="num-cell">{fmt(c.value)}</td>
                        <td>
                          <div className="alloc-wrap">
                            <div className="alloc-bar" style={{ width: `${c.allocation_pct}%` }} />
                            <span>{c.allocation_pct}%</span>
                          </div>
                        </td>
                        <td>
                          {c.is_cash
                            ? <span className="sym-sector">cash</span>
                            : c.is_commodity
                              ? <span className="pm-hedge-tag">Hedge ETF</span>
                              : (c.target_mean ? `$${c.target_mean}` : '—')}
                        </td>
                        <td className={`num-cell ${
                          c.is_commodity
                            ? (c.trailing_return_1y >= 0 ? 'pos' : 'neg')
                            : (!c.is_cash && (c.expected_return || 0) >= 20 ? 'pos'
                              : !c.is_cash && (c.expected_return || 0) < 5 ? 'neg' : 'neutral')
                        }`}>
                          {c.is_cash ? '—'
                            : c.is_commodity
                              ? (c.trailing_return_1y != null
                                  ? `1Y: ${c.trailing_return_1y >= 0 ? '+' : ''}${c.trailing_return_1y}%`
                                  : '—')
                              : (c.expected_return != null ? `${c.expected_return}%` : '—')}
                        </td>
                        <td className={`num-cell ${sy ? (sy.ytd_pnl >= 0 ? 'pos' : 'neg') : ''}`}>
                          {sy ? (
                            <span title={`From $${fmt(sy.value_at_start, '')} on ${ytd.snapshot_date}`}>
                              {sy.ytd_pnl >= 0 ? '+' : ''}{fmt(sy.ytd_pnl)}
                              <br/><span style={{fontSize:'0.65rem'}}>{fmtPct(sy.ytd_pnl_pct)}</span>
                            </span>
                          ) : '—'}
                        </td>
                        <td>{c.is_cash ? <span className="sym-sector">Cash</span> : <ActionBadge action={c.action} />}</td>
                      </tr>
                      );
                    })}
                  </tbody>
                </table>

                {/* ── MTM Section ── */}
                {mtm.length > 0 && (
                  <div style={{ marginTop: '1.25rem' }}>
                    <div className="pm-section-title">
                      Mark-to-Market (MTM)
                      {mtmWithCost.length > 0 && (
                        <span className={`pm-mtm-total ${totalUnrealPnl >= 0 ? 'pos' : 'neg'}`}>
                          {totalUnrealPnl >= 0 ? '+' : ''}{fmt(totalUnrealPnl)}
                          &nbsp;({totalCostBasis > 0 ? ((totalUnrealPnl / totalCostBasis) * 100).toFixed(1) : '—'}%)
                        </span>
                      )}
                    </div>
                    <table className="pm-table pm-consolidated-table">
                      <thead>
                        <tr>
                          <th>Symbol</th>
                          <th>Qty</th>
                          <th>Avg Cost</th>
                          <th>Cur Price</th>
                          <th>Cost Basis</th>
                          <th>Mkt Value</th>
                          <th>Unreal P&amp;L</th>
                          <th>P&amp;L %</th>
                          <th>YTD P&amp;L</th>
                          <th>YTD %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {mtm.map(r => {
                          const pnlCls = r.unrealized_pnl == null ? '' : r.unrealized_pnl >= 0 ? 'pos' : 'neg';
                          const sy = ytd?.symbol_ytd?.[r.symbol];
                          const ytdCls = sy ? (sy.ytd_pnl >= 0 ? 'pos' : 'neg') : '';
                          return (
                            <tr key={r.symbol}>
                              <td className="sym-name">{r.symbol}</td>
                              <td>{r.total_qty}</td>
                              <td className="num-cell">{r.avg_cost != null ? `$${r.avg_cost}` : '—'}</td>
                              <td className="num-cell">${r.current_price}</td>
                              <td className="num-cell">{r.cost_basis != null ? fmt(r.cost_basis) : '—'}</td>
                              <td className="num-cell">{fmt(r.market_value)}</td>
                              <td className={`num-cell ${pnlCls}`}>
                                {r.unrealized_pnl != null ? `${r.unrealized_pnl >= 0 ? '+' : ''}${fmt(r.unrealized_pnl)}` : '—'}
                              </td>
                              <td className={`num-cell ${pnlCls}`}>
                                {r.unrealized_pnl_pct != null ? fmtPct(r.unrealized_pnl_pct) : '—'}
                              </td>
                              <td className={`num-cell ${ytdCls}`}>
                                {sy ? `${sy.ytd_pnl >= 0 ? '+' : ''}${fmt(sy.ytd_pnl)}` : '—'}
                              </td>
                              <td className={`num-cell ${ytdCls}`}>
                                {sy ? fmtPct(sy.ytd_pnl_pct) : '—'}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    {mtmWithCost.length < mtm.length && (
                      <div className="pm-mtm-note">
                        — shown for positions with avg purchase price entered. Add avg prices to see full MTM.
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>

          {/* ══ RIGHT — Advice (after analysis) ══ */}
          <div className="pm-col pm-right">
            {!showAnalysis && (
              <div className="pm-analysis-prompt">
                <div className="pm-analysis-prompt-icon">💡</div>
                <div className="pm-analysis-prompt-text">
                  Investment advice, cash deployment plan, and rebalancing suggestions will appear here after running analysis.
                </div>
              </div>
            )}

            {analysis && !loadingAnalysis && summary && (
              <>
                <div className="pm-section-title">Target Analysis &amp; Advice</div>

                {/* Return gauge */}
                {(() => {
                  const projectedValue      = summary.total_investable * (1 + summary.weighted_expected_return_pct / 100);
                  const projRetFromBase     = summary.baseline_total
                                              ? (projectedValue / summary.baseline_total - 1) * 100
                                              : null;
                  const vsTargetPct         = projRetFromBase != null ? projRetFromBase - 25 : null;
                  const vsTargetAmt         = projectedValue - summary.target_25pct;
                  const onTrack             = vsTargetPct != null ? vsTargetPct >= 0 : summary.on_track;
                  const barMax              = Math.max(50, projRetFromBase != null ? projRetFromBase * 1.1 : 50);
                  return (
                    <div className="pm-gauge-box">
                      <div className="pm-gauge-label">Analyst Projection vs Your 25% Target</div>

                      <div className="pm-proj-row">
                        <div className="pm-proj-col">
                          <div className="pm-proj-sub">If analysts are right</div>
                          <div className="pm-proj-val" style={{color: onTrack ? 'var(--positive)' : 'var(--negative)'}}>
                            {fmt(projectedValue)}
                          </div>
                          {projRetFromBase != null && (
                            <div className="pm-proj-ret" style={{color: onTrack ? 'var(--positive)' : 'var(--negative)'}}>
                              {projRetFromBase >= 0 ? '+' : ''}{projRetFromBase.toFixed(1)}% from {ytd?.snapshot_date || 'baseline'}
                            </div>
                          )}
                        </div>
                        <div className="pm-proj-divider">vs</div>
                        <div className="pm-proj-col">
                          <div className="pm-proj-sub">Your 25% target</div>
                          <div className="pm-proj-val" style={{color: 'var(--accent)'}}>
                            {fmt(summary.target_25pct)}
                          </div>
                          <div className="pm-proj-ret" style={{color: 'var(--neutral)'}}>
                            from {fmt(summary.baseline_total)}
                          </div>
                        </div>
                      </div>

                      <div className="pm-gauge-track" style={{marginTop: '0.6rem'}}>
                        <div
                          className="pm-gauge-fill"
                          style={{
                            width: `${projRetFromBase != null ? Math.min(projRetFromBase / barMax * 100, 100) : 0}%`,
                            background: onTrack ? 'var(--positive)' : 'var(--negative)',
                          }}
                        />
                        <div className="pm-gauge-target-line" style={{ left: `${25 / barMax * 100}%` }} title="25% target" />
                      </div>

                      <div className="pm-gauge-caption">
                        {vsTargetPct != null
                          ? onTrack
                            ? `✅ Would overshoot target by ${fmt(vsTargetAmt)} (+${vsTargetPct.toFixed(1)}%)`
                            : `⚠️ Would miss target by ${fmt(Math.abs(vsTargetAmt))} (${vsTargetPct.toFixed(1)}%)`
                          : summary.on_track
                            ? `✅ Exceeds 25% target by ${(summary.weighted_expected_return_pct - 25).toFixed(1)}%`
                            : `⚠️ ${summary.gap_to_target_pct}% below the 25% target`
                        }
                      </div>
                      <div className="pm-gauge-sub">
                        Analysts see {summary.weighted_expected_return_pct}% remaining upside from today's prices
                      </div>
                    </div>
                  );
                })()}

                {/* Cash deployment */}
                {advice?.cash_deployment?.length > 0 && (
                  <div className="pm-advice-block">
                    <div className="pm-advice-title">💰 Deploy {fmt(summary.portfolio_cash)} Portfolio Cash</div>
                    {advice.cash_deployment.map((item, i) => item.note ? (
                      <div key={i} className="pm-advice-note">{item.note}</div>
                    ) : (
                      <div key={i} className="pm-advice-row">
                        <div className="pm-advice-sym">
                          <span className="pm-advice-symbol">{item.symbol}</span>
                          <ActionBadge action="STRONG_BUY" />
                        </div>
                        <div className="pm-advice-detail">
                          Buy <strong>{item.shares_to_buy} shares</strong> @ ${item.price} = <strong>{fmt(item.cost)}</strong>
                        </div>
                        <div className="pm-advice-rationale">{item.rationale}</div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Top performers */}
                {advice?.top_performers?.length > 0 && (
                  <div className="pm-advice-block">
                    <div className="pm-advice-title">🚀 Hold &amp; Build — Top Performers</div>
                    {advice.top_performers.map(p => (
                      <div key={p.symbol} className="pm-advice-row">
                        <div className="pm-advice-sym">
                          <span className="pm-advice-symbol">{p.symbol}</span>
                          <span className="pm-ret pos">+{p.expected_return}%</span>
                        </div>
                        <div className="pm-advice-detail">
                          {fmt(p.value)} position · target ${p.target_mean}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Underperformers */}
                {advice?.underperformers?.length > 0 && (
                  <div className="pm-advice-block">
                    <div className="pm-advice-title">⚠️ Review / Reduce</div>
                    {advice.underperformers.map(u => (
                      <div key={u.symbol} className="pm-advice-row">
                        <div className="pm-advice-sym">
                          <span className="pm-advice-symbol">{u.symbol}</span>
                          <ActionBadge action={u.action} />
                        </div>
                        <div className="pm-advice-detail">
                          {fmt(u.value)} · {u.expected_return != null ? `${u.expected_return}% expected` : 'No analyst target'}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Hedges & Commodities */}
                {advice?.hedges?.length > 0 && (
                  <div className="pm-advice-block">
                    <div className="pm-advice-title">🛡️ Hedges &amp; Commodities</div>
                    {advice.hedges.map(h => (
                      <div key={h.symbol} className="pm-advice-row">
                        <div className="pm-advice-sym">
                          <span className="pm-advice-symbol">{h.symbol}</span>
                          <ActionBadge action={h.action} />
                          {h.trailing_return_1y != null && (
                            <span className={`pm-ret ${h.trailing_return_1y >= 0 ? 'pos' : 'neg'}`}>
                              1Y: {h.trailing_return_1y >= 0 ? '+' : ''}{h.trailing_return_1y}%
                            </span>
                          )}
                        </div>
                        <div className="pm-advice-detail">
                          {fmt(h.value)} · {h.allocation_pct}% of portfolio
                        </div>
                        <div className="pm-advice-rationale">{h.commodity_rationale}</div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Rebalancing */}
                {advice?.rebalancing?.length > 0 && (
                  <div className="pm-advice-block">
                    <div className="pm-advice-title">🔄 Rebalancing Plan</div>
                    {advice.rebalancing.map((r, i) => (
                      <div key={i} className={`pm-advice-row pm-rebal-row ${r.action === 'REDUCE' ? 'reduce' : 'redirect'}`}>
                        <div className="pm-advice-sym">
                          <span className="pm-advice-symbol">{r.symbol || '→'}</span>
                          <span className="pm-rebal-action">{r.action}</span>
                        </div>
                        <div className="pm-advice-rationale">{r.rationale}</div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="pm-disclaimer">
                  ⚠️ Expected returns based on analyst consensus price targets. Not financial advice. Past performance ≠ future results.
                </div>
              </>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
