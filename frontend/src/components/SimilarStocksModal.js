import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './SimilarStocksModal.css';
import { getApiUrl } from '../config';

function SimilarStocksModal({ stock, sentimentScore, onClose, onAddToFavorites }) {
  const [similarStocks, setSimilarStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadSimilarStocks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stock.symbol, sentimentScore]);

  const loadSimilarStocks = async () => {
    setLoading(true);
    setError(null);
    try {
      console.log('Fetching similar stocks for:', stock.symbol);
      const response = await axios.get(
        getApiUrl(`/api/stocks/${stock.symbol}/similar?sentiment_score=${sentimentScore || 0}&limit=10`)
      );
      console.log('Similar stocks response:', response.data);
      setSimilarStocks(response.data || []);
    } catch (error) {
      console.error('Error loading similar stocks:', error);
      setError(error.response?.data?.error || error.message || 'Failed to load similar stocks');
    } finally {
      setLoading(false);
    }
  };

  const getSentimentColor = (score) => {
    if (score > 0.3) return '#27ae60';
    if (score < -0.3) return '#e74c3c';
    return '#f39c12';
  };

  const getCorrelationBadge = (correlation) => {
    if (correlation >= 0.8) return { label: 'High', color: '#27ae60' };
    if (correlation >= 0.6) return { label: 'Medium', color: '#f39c12' };
    return { label: 'Low', color: '#e74c3c' };
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>🔍 Stocks Similar to {stock.symbol}</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          {loading ? (
            <div className="loading-state">
              <p>Finding correlated stocks...</p>
            </div>
          ) : error ? (
            <div className="error-state">
              <p>❌ {error}</p>
              <button onClick={loadSimilarStocks}>Try Again</button>
            </div>
          ) : similarStocks.length === 0 ? (
            <div className="empty-state">
              <p>No similar stocks found</p>
            </div>
          ) : (
            <div className="similar-stocks-list">
              {similarStocks.map((similar, index) => {
                const corrBadge = getCorrelationBadge(similar.correlation);
                return (
                  <div key={index} className="similar-stock-card">
                    <div className="stock-info">
                      <div className="stock-header">
                        <h3>{similar.symbol}</h3>
                        <span className="stock-name">{similar.name}</span>
                      </div>
                      <div className="stock-meta">
                        <span className="sector-badge">{similar.sector}</span>
                        <span
                          className="correlation-badge"
                          style={{ backgroundColor: corrBadge.color }}
                        >
                          {corrBadge.label} Correlation ({similar.correlation})
                        </span>
                      </div>
                      <div className="stock-metrics">
                        <div className="metric">
                          <label>Sentiment Score:</label>
                          <span style={{ color: getSentimentColor(similar.sentiment_score) }}>
                            {similar.sentiment_score.toFixed(2)}
                          </span>
                        </div>
                        <div className="metric">
                          <label>Reason:</label>
                          <span>{similar.similarity_reason}</span>
                        </div>
                      </div>
                    </div>
                    <button
                      className="add-favorite-btn"
                      onClick={() => onAddToFavorites(similar.symbol, similar.name, similar.sentiment_score)}
                    >
                      ⭐ Add to Favorites
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default SimilarStocksModal;
