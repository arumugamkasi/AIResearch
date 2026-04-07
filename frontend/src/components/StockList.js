import React, { useState } from 'react';
import './StockList.css';

function StockList({ stocks, selectedStock, onSelectStock, onAddStock, onRemoveStock, favorites = [] }) {
  const isFavorite = (symbol) => favorites.some(f => f.symbol === symbol);
  const [newSymbol, setNewSymbol] = useState('');
  const [newName, setNewName] = useState('');

  const handleAdd = () => {
    if (newSymbol.trim()) {
      onAddStock(newSymbol.toUpperCase(), newName || newSymbol);
      setNewSymbol('');
      setNewName('');
    }
  };

  return (
    <div className="stock-list-container">
      <div className="stock-list-header">
        <h3>Tracked Stocks</h3>
      </div>

      <div className="add-stock-form">
        <input
          type="text"
          placeholder="Symbol (e.g., AAPL)"
          value={newSymbol}
          onChange={(e) => setNewSymbol(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleAdd()}
        />
        <input
          type="text"
          placeholder="Company name (optional)"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleAdd()}
        />
        <button onClick={handleAdd} className="add-btn">+ Add</button>
      </div>

      <div className="stocks-list">
        {stocks.length === 0 ? (
          <div className="no-stocks">
            <p>No stocks yet</p>
            <small>Add one to get started</small>
          </div>
        ) : (
          stocks.map((stock) => (
            <div
              key={stock.symbol}
              className={`stock-item ${selectedStock?.symbol === stock.symbol ? 'active' : ''}`}
              onClick={() => onSelectStock(stock)}
            >
              <div className="stock-info">
                <h4>
                  {isFavorite(stock.symbol) && <span className="fav-indicator">⭐</span>}
                  {stock.symbol}
                </h4>
                <small>{stock.name}</small>
              </div>
              <button
                className="remove-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  if (window.confirm(`Remove ${stock.symbol}?`)) {
                    onRemoveStock(stock.symbol);
                  }
                }}
              >
                ✕
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default StockList;
