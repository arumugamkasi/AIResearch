import React from 'react';
import './NewsPanel.css';

function NewsPanel({ stock, news, loading, onAnalyze }) {
  return (
    <div className="news-panel">
      <div className="panel-header">
        <h3>📰 Latest News</h3>
        <span className="news-count">{news.length} articles</span>
      </div>

      {loading ? (
        <div className="loading">
          <p>Fetching news...</p>
        </div>
      ) : news.length === 0 ? (
        <div className="no-news">
          <p>No news found</p>
        </div>
      ) : (
        <>
          <div className="articles-list">
            {news.map((article, index) => (
              <article key={index} className="article-card">
                {article.image && (
                  <div className="article-image">
                    <img src={article.image} alt={article.title} onError={(e) => e.target.style.display = 'none'} />
                  </div>
                )}
                <div className="article-content">
                  <h4>{article.title}</h4>
                  <p className="article-desc">{article.description}</p>
                  <footer className="article-footer">
                    <span className="source">{article.source}</span>
                    <span className="date">{new Date(article.published_date).toLocaleDateString()}</span>
                  </footer>
                  <a href={article.url} target="_blank" rel="noopener noreferrer" className="read-more">
                    Read More →
                  </a>
                </div>
              </article>
            ))}
          </div>

          <button className="analyze-btn" onClick={onAnalyze}>
            📊 Analyze All Articles
          </button>
        </>
      )}
    </div>
  );
}

export default NewsPanel;
