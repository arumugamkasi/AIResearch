import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './FundamentalsPanel.css';
import PriceChart from './PriceChart';
import { getApiUrl } from '../config';

function FundamentalsPanel({ stock }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!stock) { setData(null); return; }
    setData(null);
    setLoading(true);
    setError(null);
    axios.get(getApiUrl(`/api/fundamentals/${stock.symbol}`))
      .then(r => setData(r.data))
      .catch(() => setError('Failed to load fundamentals'))
      .finally(() => setLoading(false));
  }, [stock]);

  if (!stock) {
    return (
      <div className="fund-panel empty">
        <div className="fund-empty"><p>Select a stock to view fundamentals</p></div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="fund-panel">
        <div className="fund-panel-header"><h3>Fundamentals</h3></div>
        <div className="fund-loading"><span className="spinner">⏳</span> Loading fundamentals…</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="fund-panel">
        <div className="fund-panel-header"><h3>Fundamentals</h3></div>
        <div className="fund-error">{error || 'No data available'}</div>
      </div>
    );
  }

  const { key_stats: ks, analyst, income, balance_sheet: bs, cash_flow: cf } = data;

  const totalAnalyst = analyst
    ? analyst.strong_buy + analyst.buy + analyst.hold + analyst.sell + analyst.strong_sell
    : 0;

  const pct = (v) => totalAnalyst > 0 ? Math.round((v / totalAnalyst) * 100) : 0;

  const statRow = (label, value, unit = '') =>
    value != null ? (
      <div className="stat-row" key={label}>
        <span className="stat-label">{label}</span>
        <span className="stat-value">{value}{unit}</span>
      </div>
    ) : null;

  const maxRev = income?.length
    ? Math.max(...income.map(q => q.revenue_raw || 0))
    : 1;

  return (
    <div className="fund-panel">
      <div className="fund-panel-header">
        <h3>Fundamentals</h3>
      </div>

      {/* Price Chart */}
      <PriceChart symbol={stock.symbol} />

      {/* Key Stats */}
      {ks && (
        <div className="fund-section">
          <h4 className="fund-section-title">Key Statistics</h4>
          <div className="stat-grid">
            {statRow('Market Cap',      ks.market_cap)}
            {statRow('P/E (TTM)',       ks.pe_trailing, 'x')}
            {statRow('P/E (Fwd)',       ks.pe_forward,  'x')}
            {statRow('EPS (TTM)',       ks.eps_trailing != null ? `$${ks.eps_trailing}` : null)}
            {statRow('EPS (Fwd)',       ks.eps_forward  != null ? `$${ks.eps_forward}`  : null)}
            {statRow('Beta',            ks.beta)}
            {statRow('52w High',        ks.week52_high  != null ? `$${ks.week52_high}`  : null)}
            {statRow('52w Low',         ks.week52_low   != null ? `$${ks.week52_low}`   : null)}
            {statRow('Div Yield',       ks.dividend_yield != null ? `${ks.dividend_yield}%` : null)}
            {statRow('Profit Margin',   ks.profit_margin  != null ? `${ks.profit_margin}%`  : null)}
            {statRow('Op. Margin',      ks.operating_margin != null ? `${ks.operating_margin}%` : null)}
            {statRow('ROE',             ks.roe != null ? `${ks.roe}%` : null)}
            {statRow('Revenue Growth',  ks.revenue_growth != null ? `${ks.revenue_growth}%` : null)}
            {statRow('P/B Ratio',       ks.price_to_book, 'x')}
            {statRow('D/E Ratio',       ks.debt_to_equity)}
            {statRow('Current Ratio',   ks.current_ratio)}
          </div>
        </div>
      )}

      {/* Analyst Ratings */}
      {analyst && totalAnalyst > 0 && (
        <div className="fund-section">
          <h4 className="fund-section-title">Analyst Ratings</h4>
          {analyst.recommendation && (
            <div className={`consensus-badge consensus-${analyst.recommendation.toLowerCase().replace(' ', '-')}`}>
              {analyst.recommendation.replace('_', ' ')}
            </div>
          )}
          <div className="analyst-bars">
            {[
              { label: 'Strong Buy', val: analyst.strong_buy,  cls: 'strong-buy'  },
              { label: 'Buy',        val: analyst.buy,         cls: 'buy'          },
              { label: 'Hold',       val: analyst.hold,        cls: 'hold'         },
              { label: 'Sell',       val: analyst.sell,        cls: 'sell'         },
              { label: 'Strong Sell',val: analyst.strong_sell, cls: 'strong-sell'  },
            ].map(({ label, val, cls }) => val > 0 ? (
              <div key={label} className="analyst-bar-row">
                <span className="analyst-label">{label}</span>
                <div className="analyst-bar-track">
                  <div className={`analyst-bar-fill ${cls}`} style={{ width: `${pct(val)}%` }} />
                </div>
                <span className="analyst-count">{val}</span>
              </div>
            ) : null)}
          </div>
          {analyst.target_mean && (
            <div className="price-targets">
              <div className="target-row">
                <span className="stat-label">Mean Target</span>
                <span className="stat-value target-mean">${analyst.target_mean}</span>
              </div>
              <div className="target-row">
                <span className="stat-label">Target Range</span>
                <span className="stat-value">${analyst.target_low} – ${analyst.target_high}</span>
              </div>
              {analyst.current_price && analyst.target_mean && (
                <div className="target-row">
                  <span className="stat-label">Upside</span>
                  <span className={`stat-value ${analyst.target_mean > analyst.current_price ? 'positive' : 'negative'}`}>
                    {((analyst.target_mean / analyst.current_price - 1) * 100).toFixed(1)}%
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Revenue (Quarterly) */}
      {income?.length > 0 && (
        <div className="fund-section">
          <h4 className="fund-section-title">Quarterly Revenue</h4>
          {income.map((q, i) => (
            <div key={i} className="rev-row">
              <span className="rev-period">{q.period}</span>
              <div className="rev-bar-track">
                <div
                  className="rev-bar-fill"
                  style={{ width: `${maxRev > 0 && q.revenue_raw ? (q.revenue_raw / maxRev) * 100 : 0}%` }}
                />
              </div>
              <span className="rev-value">{q.revenue || '—'}</span>
            </div>
          ))}
          {income[0] && (
            <div className="income-extras">
              {income[0].gross_profit && statRow('Gross Profit', income[0].gross_profit)}
              {income[0].net_income   && statRow('Net Income',   income[0].net_income)}
            </div>
          )}
        </div>
      )}

      {/* Balance Sheet */}
      {bs && Object.keys(bs).length > 1 && (
        <div className="fund-section">
          <h4 className="fund-section-title">Balance Sheet {bs.period && <span className="period-tag">({bs.period})</span>}</h4>
          <div className="stat-grid">
            {statRow('Total Assets',    bs.total_assets)}
            {statRow('Total Debt',      bs.total_debt)}
            {statRow('Cash & Equiv.',   bs.cash)}
            {statRow('Equity',          bs.total_equity)}
            {statRow('Current Assets',  bs.current_assets)}
            {statRow('Current Liab.',   bs.current_liabilities)}
          </div>
        </div>
      )}

      {/* Cash Flow */}
      {cf && Object.keys(cf).length > 1 && (
        <div className="fund-section">
          <h4 className="fund-section-title">Cash Flow {cf.period && <span className="period-tag">({cf.period})</span>}</h4>
          <div className="stat-grid">
            {statRow('Operating CF', cf.operating_cf)}
            {statRow('Free CF',      cf.free_cf)}
            {statRow('CapEx',        cf.capex)}
          </div>
        </div>
      )}
    </div>
  );
}

export default FundamentalsPanel;
