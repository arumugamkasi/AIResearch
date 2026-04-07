import React from 'react';
import './AnalysisPanel.css';
import PriceChart from './PriceChart';

function AnalysisPanel({ analysis, stock, newsCount, analyzing }) {
  // Only show full-page spinner if we have no data at all
  if (analyzing && !analysis) {
    return (
      <div className="analysis-panel">
        <div className="panel-header">
          <h3>💡 Analysis & Recommendation</h3>
        </div>
        <div className="analyzing-indicator">
          <span className="spinner">⏳</span> Analyzing articles...
        </div>
      </div>
    );
  }

  if (!analysis) {
    // Only show "Select a stock" message if no stock is selected
    if (!stock) {
      return (
        <div className="analysis-panel empty">
          <div className="empty-message">
            <p>📊 Analysis will appear here</p>
            <small>Select a stock to begin</small>
          </div>
        </div>
      );
    }

    // Stock selected but analysis not ready yet - show empty panel
    return (
      <div className="analysis-panel">
        <div className="panel-header">
          <h3>💡 Analysis & Recommendation</h3>
        </div>
      </div>
    );
  }

  const getRecommendationColor = (action) => {
    if (action.includes('BUY') || action.includes('INCREASE')) return '#27ae60';
    if (action.includes('CLOSE') || action.includes('AVOID')) return '#e74c3c';
    return '#f39c12';
  };

  const getRecommendationEmoji = (action) => {
    if (action.includes('BUY')) return '🟢';
    if (action.includes('CLOSE') || action.includes('AVOID')) return '🔴';
    return '🟡';
  };

  return (
    <div className="analysis-panel">
      <div className="panel-header">
        <h3>💡 Analysis & Recommendation</h3>
      </div>

      {analysis.isPreliminary ? (
        <div className="recommendation-box preliminary">
          <div className="recommendation-header">
            <span className="emoji">⏳</span>
            <div>
              <h4 className="recommendation" style={{ color: '#888' }}>Generating recommendation…</h4>
              <p className="confidence">LLM analysis in progress</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="recommendation-box">
          <div className="recommendation-header">
            <span className="emoji">{getRecommendationEmoji(analysis.recommendation)}</span>
            <div>
              <h4 className="recommendation" style={{ color: getRecommendationColor(analysis.recommendation) }}>
                {analysis.recommendation.replace(/_/g, ' ')}
              </h4>
              <p className="confidence">Confidence: {(analysis.confidence * 100).toFixed(0)}%</p>
            </div>
          </div>
        </div>
      )}

      <div className="sentiment-section">
        <h4>📈 Sentiment Analysis</h4>
        <div className="sentiment-bars">
          <div className="sentiment-bar">
            <label>Positive</label>
            <div className="bar-container">
              <div className="bar positive" style={{ width: `${analysis.sentiment_breakdown.positive * 100}%` }}></div>
            </div>
            <span>{(analysis.sentiment_breakdown.positive * 100).toFixed(0)}%</span>
          </div>
          <div className="sentiment-bar">
            <label>Neutral</label>
            <div className="bar-container">
              <div className="bar neutral" style={{ width: `${analysis.sentiment_breakdown.neutral * 100}%` }}></div>
            </div>
            <span>{(analysis.sentiment_breakdown.neutral * 100).toFixed(0)}%</span>
          </div>
          <div className="sentiment-bar">
            <label>Negative</label>
            <div className="bar-container">
              <div className="bar negative" style={{ width: `${Math.abs(analysis.sentiment_breakdown.negative * 100)}%` }}></div>
            </div>
            <span>{(analysis.sentiment_breakdown.negative * 100).toFixed(0)}%</span>
          </div>
        </div>
        <div className="sentiment-score">
          Sentiment Score: <span className={analysis.sentiment_score > 0 ? 'positive' : analysis.sentiment_score < 0 ? 'negative' : 'neutral'}>
            {analysis.sentiment_score.toFixed(2)}
          </span>
        </div>
      </div>

      <PriceChart symbol={stock.symbol} />

      {analysis.isPreliminary ? (
        <div className="preliminary-notice">
          <small>⏳ LLM summary, key points &amp; reasoning loading…</small>
        </div>
      ) : (
        <>
          {analysis.summary && (
            <div className="summary-section">
              <h4>📝 Summary</h4>
              <p>{analysis.summary}</p>
            </div>
          )}

          {analysis.key_points && analysis.key_points.length > 0 && (
            <div className="key-points-section">
              <h4>🎯 Key Points</h4>
              <ul>
                {analysis.key_points.map((point, index) => (
                  <li key={index}>{point}</li>
                ))}
              </ul>
            </div>
          )}

          {analysis.reasoning && (
            <div className="reasoning-section">
              <h4>💭 Reasoning</h4>
              <p>{analysis.reasoning}</p>
            </div>
          )}

          {analysis.critical_events && analysis.critical_events.length > 0 && (
            <div className="critical-events-section">
              <h4>🚨 Critical Events</h4>
              <div className="events-list">
                {analysis.critical_events.map((event, index) => (
                  <div key={index} className={`event-card event-${(event.impact || 'neutral').toLowerCase()}`}>
                    <div className="event-header">
                      <span className={`event-impact impact-${(event.impact || 'neutral').toLowerCase()}`}>
                        {event.impact || 'NEUTRAL'}
                      </span>
                      <span className="event-category">
                        {(event.category || 'OTHER').replace(/_/g, ' ')}
                      </span>
                    </div>
                    <p className="event-description">{event.event}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {analysis.revenue_outlook && analysis.revenue_outlook.direction && analysis.revenue_outlook.direction !== 'UNCERTAIN' && (
            <div className="revenue-outlook-section">
              <h4>💰 Revenue Outlook</h4>
              <div className="outlook-direction">
                <span className={`direction-badge direction-${(analysis.revenue_outlook.direction || 'uncertain').toLowerCase()}`}>
                  {analysis.revenue_outlook.direction}
                </span>
              </div>
              <p className="outlook-summary">{analysis.revenue_outlook.summary}</p>
              {analysis.revenue_outlook.factors && analysis.revenue_outlook.factors.length > 0 && (
                <ul className="outlook-factors">
                  {analysis.revenue_outlook.factors.map((factor, index) => (
                    <li key={index}>{factor}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </>
      )}

      <div className="meta-info">
        <small>Based on {newsCount} articles analyzed</small>
      </div>
    </div>
  );
}

export default AnalysisPanel;
