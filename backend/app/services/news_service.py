from duckduckgo_search import DDGS
from datetime import datetime
from urllib.parse import urlparse

from app.services.vector_store_service import VectorStoreService


class NewsService:
    """Service for fetching financial news via DuckDuckGo search"""

    def __init__(self):
        self.vector_store = VectorStoreService()

    def fetch_news(self, symbol, limit=10):
        """Fetch news articles for a stock symbol using DuckDuckGo"""
        articles = []

        articles.extend(self._fetch_ddg_news(symbol, limit))

        if len(articles) < 3:
            articles.extend(self._fetch_ddg_text(symbol, limit))

        unique_articles = self._deduplicate_articles(articles)
        unique_articles.sort(key=lambda x: x['published_date'], reverse=True)
        result = unique_articles[:limit]

        # Store in ChromaDB for RAG retrieval
        if result:
            stored = self.vector_store.store_articles(symbol, result)
            print(f"Stored {stored} articles for {symbol} in ChromaDB")

        return result

    def _fetch_ddg_news(self, symbol, limit):
        """Fetch from DuckDuckGo News endpoint"""
        articles = []
        try:
            with DDGS() as ddgs:
                results = ddgs.news(
                    f"{symbol} stock financial news",
                    max_results=limit,
                    region='wt-wt',
                    safesearch='moderate'
                )
                for r in results:
                    articles.append({
                        'title': r.get('title', ''),
                        'description': r.get('body', ''),
                        'url': r.get('url', ''),
                        'source': r.get('source', 'DuckDuckGo News'),
                        'published_date': self._parse_date(r.get('date', '')),
                        'image': r.get('image', '')
                    })
        except Exception as e:
            print(f"Error fetching DuckDuckGo news: {e}")

        return articles

    def _fetch_ddg_text(self, symbol, limit):
        """Fetch from DuckDuckGo text search as fallback"""
        articles = []
        try:
            with DDGS() as ddgs:
                results = ddgs.text(
                    f"{symbol} stock market news today",
                    max_results=limit,
                    region='wt-wt',
                    safesearch='moderate'
                )
                for r in results:
                    articles.append({
                        'title': r.get('title', ''),
                        'description': r.get('body', ''),
                        'url': r.get('href', ''),
                        'source': self._extract_source(r.get('href', '')),
                        'published_date': datetime.now().isoformat(),
                        'image': ''
                    })
        except Exception as e:
            print(f"Error fetching DuckDuckGo text: {e}")

        return articles

    def _extract_source(self, url):
        """Extract domain name as source from URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc.replace('www.', '')
        except Exception:
            return 'Web Search'

    def _deduplicate_articles(self, articles):
        """Remove duplicate articles by URL"""
        seen_urls = set()
        unique = []
        for article in articles:
            url = article.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(article)
        return unique

    def _parse_date(self, date_string):
        """Parse various date formats to ISO format"""
        if not date_string:
            return datetime.now().isoformat()
        try:
            return datetime.fromisoformat(date_string).isoformat()
        except (ValueError, TypeError):
            pass
        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S',
                     '%a, %d %b %Y %H:%M:%S %z']:
            try:
                return datetime.strptime(date_string, fmt).isoformat()
            except (ValueError, TypeError):
                continue
        return datetime.now().isoformat()

    def get_trending_news(self, limit=20):
        """Get trending financial news"""
        articles = []
        try:
            with DDGS() as ddgs:
                results = ddgs.news(
                    "stock market financial news today",
                    max_results=limit,
                    region='wt-wt',
                    safesearch='moderate'
                )
                for r in results:
                    articles.append({
                        'title': r.get('title', ''),
                        'description': r.get('body', ''),
                        'url': r.get('url', ''),
                        'source': r.get('source', 'DuckDuckGo News'),
                        'published_date': self._parse_date(r.get('date', '')),
                        'image': r.get('image', '')
                    })
        except Exception as e:
            print(f"Error fetching trending news: {e}")

        articles.sort(key=lambda x: x['published_date'], reverse=True)
        return articles[:limit]
