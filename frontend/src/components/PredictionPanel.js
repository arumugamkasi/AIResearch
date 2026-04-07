import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './PredictionPanel.css';
import { getApiUrl } from '../config';

function PredictionPanel({ stock, sentimentScore }) {
  const [predictions, setPredictions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!stock) {
      setPredictions(null);
      return;
    }

    // Wait for sentiment score to be available (not just default 0)
    // This ensures predictions use actual sentiment analysis results
    if (sentimentScore === 0 || sentimentScore === undefined) {
      setLoading(true);
      return;
    }

    const fetchPredictions = async () => {
      setLoading(true);
      setError(null);

      try {
        const url = getApiUrl(`/api/predictions/${stock.symbol}?sentiment_score=${sentimentScore}`);
        console.log('Fetching predictions from:', url);
        const response = await axios.get(url);
        console.log('Predictions response:', response.data);
        console.log('Response type:', typeof response.data);

        // Parse JSON if it's a string
        const data = typeof response.data === 'string' ? JSON.parse(response.data) : response.data;
        console.log('Parsed data type:', typeof data);
        setPredictions(data);
      } catch (err) {
        console.error('Error loading predictions:', err);
        setError('Failed to load predictions');
      } finally {
        setLoading(false);
      }
    };

    fetchPredictions();
  }, [stock, sentimentScore]); // Re-fetch when stock changes OR when sentiment analysis completes

  const getRangeColor = (range) => {
    const colors = {
      'strong_up': '#27ae60',
      'up': '#2ecc71',
      'slight_up': '#6dd5a7',
      'neutral': '#95a5a6',
      'slight_down': '#f39c12',
      'down': '#e67e22',
      'strong_down': '#e74c3c'
    };
    return colors[range] || '#95a5a6';
  };

  const getRangeLabel = (range, ranges) => {
    // Use actual backtested ranges if available
    if (ranges && ranges[range]) {
      const [low, high] = ranges[range];
      const isLowInfinity = low === -Infinity || low < -100000;
      const isHighInfinity = high === Infinity || high > 100000;
      const lowStr = isLowInfinity ? '' : `${low >= 0 ? '+' : ''}${low.toFixed(1)}%`;
      const highStr = isHighInfinity ? '' : `${high >= 0 ? '+' : ''}${high.toFixed(1)}%`;

      if (isLowInfinity) return `< ${highStr}`;
      if (isHighInfinity) return `> ${lowStr}`;
      return `${lowStr} to ${highStr}`;
    }

    // Fallback labels
    const labels = {
      'strong_up': '+20% or more',
      'up': '+10% to +20%',
      'slight_up': '+5% to +10%',
      'neutral': '0% to +5%',
      'slight_down': '-5% to 0%',
      'down': '-10% to -5%',
      'strong_down': '-10% or worse'
    };
    return labels[range] || range;
  };

  const getRangeEmoji = (range) => {
    const emojis = {
      'strong_up': '🚀',
      'up': '📈',
      'slight_up': '↗️',
      'neutral': '➡️',
      'slight_down': '↘️',
      'down': '📉',
      'strong_down': '⚠️'
    };
    return emojis[range] || '➡️';
  };

  const getHorizonLabel = (horizon) => {
    const labels = {
      '1w': '1 Week',
      '1m': '1 Month',
      '3m': '3 Months',
      '6m': '6 Months',
      '1y': '1 Year'
    };
    return labels[horizon] || horizon;
  };

  if (!stock) {
    return (
      <div className="prediction-panel empty">
        <div className="empty-message">
          <p>Select a stock to see predictions</p>
        </div>
      </div>
    );
  }

  if (loading) {
    const loadingMessage = (sentimentScore === 0 || sentimentScore === undefined)
      ? 'Waiting for sentiment analysis...'
      : 'Analyzing trends...';

    return (
      <div className="prediction-panel">
        <div className="panel-header">
          <h3>📊 Direction Predictions</h3>
        </div>
        <div className="loading">
          <span className="spinner">⏳</span> {loadingMessage}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="prediction-panel">
        <div className="panel-header">
          <h3>📊 Direction Predictions</h3>
        </div>
        <div className="error-message">{error}</div>
      </div>
    );
  }

  console.log('=== RENDER CHECK ===');
  console.log('predictions:', predictions);
  console.log('predictions type:', typeof predictions);
  console.log('predictions is null?', predictions === null);
  console.log('predictions is undefined?', predictions === undefined);
  console.log('predictions.predictions:', predictions?.predictions);
  console.log('stock:', stock);
  console.log('loading:', loading);
  console.log('error:', error);

  if (!predictions || !predictions.predictions) {
    console.log('❌ FAILED CHECK - Returning null');
    return null;
  }

  console.log('✅ PASSED CHECK - Will render predictions');

  const horizons = ['1w', '1m', '3m', '6m', '1y'];
  console.log('Rendering predictions for horizons:', horizons, 'Data:', predictions.predictions);

  return (
    <div className="prediction-panel">
      <div className="panel-header">
        <h3>📊 Direction Predictions</h3>
        <span className="model-badge">{predictions.model}</span>
      </div>

      <div className="predictions-grid">
        {horizons.map(horizon => {
          const pred = predictions.predictions[horizon];
          console.log(`Rendering ${horizon}:`, pred);
          if (!pred) return null;

          // Get backtest performance for this horizon
          const backtest = predictions.backtest_performance?.[horizon];

          return (
            <div key={horizon} className="prediction-card">
              <div className="prediction-header">
                <span className="horizon-label">{getHorizonLabel(horizon)}</span>
                <span className="confidence-badge">{pred.confidence}% confident</span>
              </div>

              {backtest && backtest.total_predictions > 0 && (
                <div className="backtest-metrics">
                  {backtest.directional_accuracy && (
                    <div className="metric-item">
                      <span className="metric-icon">✓</span>
                      <span className="metric-text">
                        {backtest.directional_accuracy}% accuracy
                      </span>
                    </div>
                  )}
                  {backtest.mae && (
                    <div className="metric-item">
                      <span className="metric-icon">±</span>
                      <span className="metric-text">
                        {backtest.mae}% avg error
                      </span>
                    </div>
                  )}
                </div>
              )}

              <div className="prediction-result">
                <span className="range-emoji">{getRangeEmoji(pred.likely_range)}</span>
                <div className="range-info">
                  <div
                    className="range-label"
                    style={{ color: getRangeColor(pred.likely_range) }}
                  >
                    {getRangeLabel(pred.likely_range, pred.ranges)}
                  </div>
                  {pred.expected_return !== undefined && (
                    <div className="expected-return">
                      Expected: {pred.expected_return >= 0 ? '+' : ''}{pred.expected_return.toFixed(2)}%
                    </div>
                  )}
                  <div className="range-explanation">{pred.explanation}</div>
                </div>
              </div>

              <div className="probability-bars">
                {Object.entries(pred.probabilities || {})
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 3)
                  .map(([range, prob]) => (
                    <div key={range} className="prob-bar-item">
                      <span className="prob-label">{getRangeLabel(range, pred.ranges)}</span>
                      <div className="prob-bar-container">
                        <div
                          className="prob-bar"
                          style={{
                            width: `${prob}%`,
                            backgroundColor: getRangeColor(range)
                          }}
                        />
                      </div>
                      <span className="prob-value">{prob.toFixed(1)}%</span>
                    </div>
                  ))
                }
              </div>
            </div>
          );
        })}
      </div>

      {predictions.backtest_performance && Object.keys(predictions.backtest_performance).length > 0 && (
        <div className="backtest-performance">
          <h4>📈 Model Backtest Performance</h4>
          <div className="performance-grid">
            {Object.entries(predictions.backtest_performance).map(([horizon, perf]) => {
              if (!perf || perf.total_predictions === 0) return null;

              return (
                <div key={horizon} className="performance-card">
                  <div className="perf-horizon">{getHorizonLabel(horizon)}</div>
                  {perf.directional_accuracy && (
                    <div className="perf-metric">
                      <span className="perf-label">Accuracy:</span>
                      <span className={`perf-value ${perf.directional_accuracy > 60 ? 'good' : 'fair'}`}>
                        {perf.directional_accuracy}%
                      </span>
                    </div>
                  )}
                  {perf.mae && (
                    <div className="perf-metric">
                      <span className="perf-label">Avg Error:</span>
                      <span className="perf-value">±{perf.mae}%</span>
                    </div>
                  )}
                  <div className="perf-samples">{perf.total_predictions} tests</div>
                </div>
              );
            })}
          </div>
          <div className="backtest-note">
            <small>Historical accuracy from {Object.values(predictions.backtest_performance).reduce((sum, p) => sum + (p.total_predictions || 0), 0)} predictions</small>
          </div>
        </div>
      )}

      <div className="prediction-disclaimer">
        <small>
          ⚠️ Predictions are based on sentiment analysis and price momentum.
          Not financial advice. Past performance doesn't guarantee future results.
        </small>
      </div>
    </div>
  );
}

export default PredictionPanel;
