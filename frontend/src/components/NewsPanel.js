import React, { useState, useEffect } from 'react';
import './NewsPanel.css';

const PAGE_SIZE = 5;

function NewsPanel({ news, loading }) {
  const [page, setPage] = useState(1);

  // Reset to page 1 when news changes (new stock selected)
  useEffect(() => { setPage(1); }, [news]);

  const totalPages = Math.ceil(news.length / PAGE_SIZE);
  const start = (page - 1) * PAGE_SIZE;
  const pageArticles = news.slice(start, start + PAGE_SIZE);

  return (
    <div className="news-panel">
      <div className="panel-header">
        <h3>📰 Latest News</h3>
        <span className="news-count">{news.length} articles</span>
      </div>

      {loading ? (
        <div className="loading">
          <span className="spinner">⏳</span> Fetching news...
        </div>
      ) : news.length === 0 ? (
        <div className="no-news">
          <p>No news found</p>
        </div>
      ) : (
        <>
          <div className="articles-list">
            {pageArticles.map((article, index) => (
              <article key={start + index} className="article-card">
                {article.image && (
                  <div className="article-image">
                    <img
                      src={article.image}
                      alt={article.title}
                      onError={(e) => {
                        e.target.style.display = 'none';
                        e.target.parentElement.style.display = 'none';
                      }}
                    />
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

          {totalPages > 1 && (
            <div className="pagination">
              <button
                className="page-btn"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                ‹
              </button>
              <span className="page-info">{page} / {totalPages}</span>
              <button
                className="page-btn"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                ›
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default NewsPanel;
