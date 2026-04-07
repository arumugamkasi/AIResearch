import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { getApiUrl } from '../config';
import './FavoritesPanel.css';

function FavoritesPanel({ onSelectStock, currentStock }) {
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadFavorites();
  }, []);

  const loadFavorites = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(getApiUrl('/api/favorites'));
      setFavorites(response.data);
    } catch (err) {
      console.error('Error loading favorites:', err);
      setError('Failed to load favorites');
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveFavorite = async (symbol, e) => {
    e.stopPropagation(); // Prevent stock selection when clicking remove
    try {
      await axios.delete(getApiUrl(`/api/favorites/${symbol}`));
      setFavorites(favorites.filter(f => f.symbol !== symbol));
    } catch (err) {
      console.error('Error removing favorite:', err);
      alert('Failed to remove favorite');
    }
  };

  const getSentimentColor = (score) => {
    if (!score && score !== 0) return '#888';
    if (score > 0.3) return '#4caf50'; // Green
    if (score < -0.3) return '#f44336'; // Red
    return '#ff9800'; // Orange
  };

  const getSentimentLabel = (score) => {
    if (!score && score !== 0) return 'N/A';
    if (score > 0.3) return 'Positive';
    if (score < -0.3) return 'Negative';
    return 'Neutral';
  };

  if (loading) {
    return (
      <div className="favorites-panel">
        <h3>⭐ Favorites</h3>
        <div className="loading">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="favorites-panel">
        <h3>⭐ Favorites</h3>
        <div className="error">{error}</div>
      </div>
    );
  }

  return (
    <div className="favorites-panel">
      <div className="favorites-header">
        <h3>⭐ Favorites</h3>
        <span className="favorites-count">{favorites.length} stocks</span>
      </div>

      {favorites.length === 0 ? (
        <div className="empty-favorites">
          <p>No favorites yet</p>
          <p className="hint">Click the ☆ next to a stock to add it to favorites</p>
        </div>
      ) : (
        <div className="favorites-list">
          {favorites.map((fav) => (
            <div
              key={fav.symbol}
              className={`favorite-item ${currentStock?.symbol === fav.symbol ? 'selected' : ''}`}
              onClick={() => onSelectStock(fav)}
            >
              <div className="favorite-info">
                <div className="favorite-symbol">{fav.symbol}</div>
                <div className="favorite-name">{fav.name || fav.symbol}</div>
              </div>

              {fav.score !== undefined && fav.score !== null && (
                <div
                  className="favorite-sentiment"
                  style={{ color: getSentimentColor(fav.score) }}
                >
                  {getSentimentLabel(fav.score)}
                </div>
              )}

              <button
                className="remove-favorite"
                onClick={(e) => handleRemoveFavorite(fav.symbol, e)}
                title="Remove from favorites"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default FavoritesPanel;
