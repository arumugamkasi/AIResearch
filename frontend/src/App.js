import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import StockList from './components/StockList';
import NewsPanel from './components/NewsPanel';
import AnalysisPanel from './components/AnalysisPanel';

function App() {
  const [stocks, setStocks] = useState([]);
  const [selectedStock, setSelectedStock] = useState(null);
  const [news, setNews] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadStocks();
  }, []);

  const loadStocks = async () => {
    try {
      const response = await axios.get('/api/stocks');
      setStocks(response.data);
    } catch (error) {
      console.error('Error loading stocks:', error);
    }
  };

  const handleAddStock = async (symbol, name) => {
    try {
      const response = await axios.post('/api/stocks', { symbol, name });
      const newStock = response.data;
      setStocks([...stocks, newStock]);
      // Automatically select the new stock to trigger research
      handleSelectStock(newStock);
    } catch (error) {
      console.error('Error adding stock:', error);
    }
  };

  const handleRemoveStock = async (symbol) => {
    try {
      await axios.delete(`/api/stocks/${symbol}`);
      setStocks(stocks.filter(s => s.symbol !== symbol));
      if (selectedStock?.symbol === symbol) {
        setSelectedStock(null);
        setNews([]);
        setAnalysis(null);
      }
    } catch (error) {
      console.error('Error removing stock:', error);
    }
  };

  const handleSelectStock = async (stock) => {
    setSelectedStock(stock);
    setLoading(true);
    try {
      const response = await axios.get(`/api/news/search?symbol=${stock.symbol}&limit=15`);
      setNews(response.data.articles);
      
      // Auto-analyze
      if (response.data.articles.length > 0) {
        analyzeNews(response.data.articles, stock.symbol);
      }
    } catch (error) {
      console.error('Error fetching news:', error);
    } finally {
      setLoading(false);
    }
  };

  const analyzeNews = async (articles, symbol) => {
    try {
      const response = await axios.post('/api/analysis/recommendation', {
        symbol: symbol,
        articles: articles,
        current_position: 'none'
      });
      setAnalysis(response.data);
    } catch (error) {
      console.error('Error analyzing news:', error);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>📈 AI Research</h1>
        <p>Financial News Analysis for Smart Investment Decisions</p>
      </header>
      
      <div className="app-container">
        <aside className="sidebar">
          <StockList
            stocks={stocks}
            selectedStock={selectedStock}
            onSelectStock={handleSelectStock}
            onAddStock={handleAddStock}
            onRemoveStock={handleRemoveStock}
          />
        </aside>
        
        <main className="main-content">
          {selectedStock ? (
            <>
              <div className="content-header">
                <h2>{selectedStock.name} ({selectedStock.symbol})</h2>
              </div>
              
              <div className="content-grid">
                <section className="news-section">
                  <NewsPanel
                    stock={selectedStock}
                    news={news}
                    loading={loading}
                    onAnalyze={() => analyzeNews(news, selectedStock.symbol)}
                  />
                </section>
                
                <section className="analysis-section">
                  <AnalysisPanel
                    analysis={analysis}
                    stock={selectedStock}
                    newsCount={news.length}
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
    </div>
  );
}

export default App;
