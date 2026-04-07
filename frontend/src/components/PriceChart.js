import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getApiUrl } from '../config';
import './PriceChart.css';

function PriceChart({ symbol }) {
  const [currentPrice, setCurrentPrice] = useState(null);
  const [historicalData, setHistoricalData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('1mo');

  useEffect(() => {
    if (symbol) {
      loadPriceData();
    }
  }, [symbol, period]);

  const loadPriceData = async () => {
    setLoading(true);
    try {
      // Fetch current price and historical data in parallel
      const [currentResponse, historicalResponse] = await Promise.all([
        axios.get(getApiUrl(`/api/prices/${symbol}/current`)),
        axios.get(getApiUrl(`/api/prices/${symbol}/historical?period=${period}&interval=1d`))
      ]);

      setCurrentPrice(currentResponse.data);
      setHistoricalData(historicalResponse.data.data || []);
    } catch (error) {
      console.error('Error loading price data:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatPrice = (price) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currentPrice?.currency || 'USD'
    }).format(price);
  };

  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  if (loading) {
    return (
      <div className="price-chart-section">
        <h4>📈 Stock Price</h4>
        <div className="loading">Loading price data...</div>
      </div>
    );
  }

  if (!currentPrice) {
    return (
      <div className="price-chart-section">
        <h4>📈 Stock Price</h4>
        <div className="no-data">Price data unavailable</div>
      </div>
    );
  }

  const priceChange = currentPrice.change;
  const priceChangePercent = currentPrice.change_percent;
  const isPositive = priceChange >= 0;

  return (
    <div className="price-chart-section">
      <h4>📈 Stock Price</h4>

      {/* Current Price Display */}
      <div className="current-price-card">
        <div className="price-main">
          <span className="price-value">{formatPrice(currentPrice.price)}</span>
          <span className={`price-change ${isPositive ? 'positive' : 'negative'}`}>
            {isPositive ? '+' : ''}{formatPrice(priceChange)} ({priceChangePercent.toFixed(2)}%)
          </span>
        </div>
        <div className="price-meta">
          <span>Previous Close: {formatPrice(currentPrice.previous_close)}</span>
        </div>
      </div>

      {/* Period Selector */}
      <div className="period-selector">
        {['5d', '1mo', '3mo', '6mo', '1y'].map(p => (
          <button
            key={p}
            className={`period-btn ${period === p ? 'active' : ''}`}
            onClick={() => setPeriod(p)}
          >
            {p.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Price Chart */}
      {historicalData.length > 0 ? (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={historicalData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="date"
                tickFormatter={formatDate}
                stroke="#999"
                style={{ fontSize: '0.75rem' }}
              />
              <YAxis
                domain={['auto', 'auto']}
                stroke="#999"
                style={{ fontSize: '0.75rem' }}
                tickFormatter={(value) => `$${value.toFixed(2)}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  fontSize: '0.85rem'
                }}
                formatter={(value) => [formatPrice(value), 'Close']}
                labelFormatter={(label) => new Date(label).toLocaleDateString()}
              />
              <Line
                type="monotone"
                dataKey="close"
                stroke={isPositive ? '#27ae60' : '#e74c3c'}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="no-data">No historical data available</div>
      )}
    </div>
  );
}

export default PriceChart;
