import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import StockList from './components/StockList';
import NewsPanel from './components/NewsPanel';
import FundamentalsPanel from './components/FundamentalsPanel';
import PredictionPanel from './components/PredictionPanel';
import SimilarStocksModal from './components/SimilarStocksModal';
import FavoritesPanel from './components/FavoritesPanel';
import Login from './components/Login';
import PortfolioModal from './components/PortfolioModal';
import { getApiUrl } from './config';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [stocks, setStocks] = useState([]);
  const [selectedStock, setSelectedStock] = useState(null);
  const [news, setNews] = useState([]);
  const [sentimentScore, setSentimentScore] = useState(0);
  const [loading, setLoading] = useState(false);
  const [favorites, setFavorites] = useState([]);
  const [showSimilarStocks, setShowSimilarStocks] = useState(false);
  const [showPortfolio, setShowPortfolio] = useState(false);

  useEffect(() => {
    // Check if already authenticated
    const token = localStorage.getItem('authToken');
    if (token) {
      setIsAuthenticated(true);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      loadStocks();
      loadFavorites();
    }
  }, [isAuthenticated]);

  const loadStocks = async () => {
    try {
      const response = await axios.get(getApiUrl('/api/stocks'));
      setStocks(response.data);
    } catch (error) {
      console.error('Error loading stocks:', error);
    }
  };

  const loadFavorites = async () => {
    try {
      const response = await axios.get(getApiUrl('/api/favorites'));
      setFavorites(response.data);
    } catch (error) {
      console.error('Error loading favorites:', error);
    }
  };

  const handleAddStock = async (symbol, name) => {
    try {
      const url = getApiUrl('/api/stocks');
      console.log('DEBUG: Adding stock, URL:', url);
      console.log('DEBUG: Data:', { symbol, name });

      const response = await axios.post(url, { symbol, name });
      console.log('DEBUG: Response:', response);
      console.log('DEBUG: Response data:', response.data);

      const newStock = response.data;
      if (!newStock || !newStock.symbol) {
        console.error('DEBUG: Invalid stock data received:', newStock);
        alert('Failed to add stock - invalid response from server');
        return;
      }

      setStocks([...stocks, newStock]);
      // Automatically select the new stock to trigger research
      handleSelectStock(newStock);
    } catch (error) {
      console.error('Error adding stock:', error);
      console.error('Error details:', error.message, error.response);
      alert(`Failed to add stock: ${error.message}`);
    }
  };

  const handleRemoveStock = async (symbol) => {
    try {
      await axios.delete(getApiUrl(`/api/stocks/${symbol}`));
      setStocks(stocks.filter(s => s.symbol !== symbol));
      if (selectedStock?.symbol === symbol) {
        setSelectedStock(null);
        setNews([]);
        setSentimentScore(0);
      }
    } catch (error) {
      console.error('Error removing stock:', error);
    }
  };

  const handleSelectStock = async (stock) => {
    setSelectedStock(stock);
    setNews([]);
    setSentimentScore(0);
    setLoading(true);
    try {
      const response = await axios.get(getApiUrl(`/api/news/search?symbol=${stock.symbol}&limit=50`));
      setNews(response.data.articles);
      const ss = response.data.sentiment_summary;
      if (ss) setSentimentScore(ss.overall_score || 0);
    } catch (error) {
      console.error('Error fetching news:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleFavorite = async (symbol, name, score) => {
    const isFavorite = favorites.some(f => f.symbol === symbol);

    if (isFavorite) {
      try {
        await axios.delete(getApiUrl(`/api/favorites/${symbol}`));
        setFavorites(favorites.filter(f => f.symbol !== symbol));
      } catch (error) {
        console.error('Error removing favorite:', error);
      }
    } else {
      try {
        const response = await axios.post(getApiUrl('/api/favorites'), {
          symbol,
          name,
          score
        });
        setFavorites([...favorites, response.data]);
      } catch (error) {
        console.error('Error adding favorite:', error);
      }
    }
  };

  const isFavorite = (symbol) => {
    return favorites.some(f => f.symbol === symbol);
  };

  const handleLogin = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('username');
    setIsAuthenticated(false);
    setStocks([]);
    setSelectedStock(null);
    setNews([]);
    setSentimentScore(0);
    setFavorites([]);
  };

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="header-title">
            <h1>📈 AI Research</h1>
            <p>Financial News Analysis for Smart Investment Decisions</p>
          </div>
          <div className="header-actions">
            <button className="portfolio-btn" onClick={() => setShowPortfolio(true)} title="Portfolio Manager">
              💼 Portfolio
            </button>
            <button className="logout-btn" onClick={handleLogout} title="Logout">
              👤 Logout
            </button>
          </div>
        </div>
      </header>
      
      <div className="app-container">
        <aside className="sidebar">
          <FavoritesPanel
            onSelectStock={handleSelectStock}
            currentStock={selectedStock}
          />
          <StockList
            stocks={stocks}
            selectedStock={selectedStock}
            onSelectStock={handleSelectStock}
            onAddStock={handleAddStock}
            onRemoveStock={handleRemoveStock}
            favorites={favorites}
          />
        </aside>
        
        <main className="main-content">
          {selectedStock ? (
            <>
              <div className="content-header">
                <h2>
                  {selectedStock.name} ({selectedStock.symbol})
                  <button
                    className={`favorite-btn ${isFavorite(selectedStock.symbol) ? 'favorited' : ''}`}
                    onClick={() => handleToggleFavorite(
                      selectedStock.symbol,
                      selectedStock.name,
                      sentimentScore
                    )}
                    title={isFavorite(selectedStock.symbol) ? 'Remove from favorites' : 'Add to favorites'}
                  >
                    {isFavorite(selectedStock.symbol) ? '⭐' : '☆'}
                  </button>
                  <button
                    className="similar-btn"
                    onClick={() => setShowSimilarStocks(true)}
                    title="Find similar stocks"
                  >
                    🔍 Find Similar Stocks
                  </button>
                </h2>
              </div>
              
              <div className="content-grid">
                <section className="news-section">
                  <NewsPanel news={news} loading={loading} />
                </section>

                <section className="analysis-section">
                  <FundamentalsPanel stock={selectedStock} />
                </section>

                <section className="prediction-section">
                  <PredictionPanel
                    stock={selectedStock}
                    sentimentScore={sentimentScore}
                  />
                </section>
              </div>
            </>
          ) : (
            <div className="empty-state">
              <h3>Select a stock to get started</h3>
              <p>Add a stock symbol on the left to begin analyzing financial news</p>
            </div>
          )}
        </main>
      </div>

      {showSimilarStocks && selectedStock && (
        <SimilarStocksModal
          stock={selectedStock}
          sentimentScore={sentimentScore}
          onClose={() => setShowSimilarStocks(false)}
          onAddToFavorites={(symbol, name, score) => {
            handleToggleFavorite(symbol, name, score);
          }}
        />
      )}

      {showPortfolio && (
        <PortfolioModal onClose={() => setShowPortfolio(false)} />
      )}
    </div>
  );
}

export default App;
