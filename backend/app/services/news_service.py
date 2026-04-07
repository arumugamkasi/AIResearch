from duckduckgo_search import DDGS
from datetime import datetime, timedelta
from urllib.parse import urlparse
import math
import threading
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.vector_store_service import VectorStoreService
from app.services.finnhub_service import FinnhubService
from app.services.finbert_sentiment import FinBERTSentimentAnalyzer
from app.services.tavily_service import TavilyService
from app.models.news_articles_mongo import NewsArticlesMongo


def _safe_parse_dt(date_str) -> datetime:
    """Parse ISO date string; returns epoch (1970) on failure so filters discard it."""
    if not date_str:
        return datetime.min
    try:
        dt = datetime.fromisoformat(str(date_str))
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except (ValueError, TypeError):
        return datetime.min


class NewsService:
    """Service for fetching financial news from multiple sources with sentiment analysis"""

    def __init__(self):
        self.vector_store = VectorStoreService()
        self.finnhub = FinnhubService()
        self.finbert = FinBERTSentimentAnalyzer()
        self.tavily = TavilyService()
        self.news_mongo = NewsArticlesMongo()
        self._company_name_cache = {}  # symbol → company name (persists across requests)

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

    def _resolve_company_name(self, symbol: str) -> str:
        """
        Resolve full company name from ticker via yfinance (cached).
        Falls back to symbol if lookup fails.
        """
        if symbol in self._company_name_cache:
            return self._company_name_cache[symbol]
        try:
            info = yf.Ticker(symbol).info
            name = info.get('longName') or info.get('shortName', '')
            if name:
                self._company_name_cache[symbol] = name
                return name
        except Exception:
            pass
        self._company_name_cache[symbol] = symbol
        return symbol

    def fetch_news_multi_source(self, symbol, limit=50, use_finbert=True, credibility_threshold=0.0):
        """
        Fetch news from multiple sources and rank by credibility and recency

        Args:
            symbol: Stock symbol
            limit: Maximum number of articles to return
            use_finbert: Whether to run FinBERT sentiment analysis
            credibility_threshold: Minimum credibility score (0.0 to 1.0)

        Returns:
            List of articles with sentiment scores and credibility rankings
        """
        symbol = symbol.strip()

        # ── 1. Serve from MongoDB cache if data is fresh (< 60 min old) ──────
        cached = self.news_mongo.get_fresh_articles(symbol, max_age_minutes=60)
        if cached:
            print(f"⚡ {symbol}: serving {len(cached)} cached articles (< 60 min old)")
            return cached[:limit]

        # ── 2. Resolve company name (cached after first call) ─────────────────
        company_name = self._resolve_company_name(symbol)
        print(f"📰 Fetching multi-source news for {symbol} ({company_name})...")

        # ── 3. Fetch all sources IN PARALLEL ──────────────────────────────────
        now = datetime.now()
        yesterday_start = (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        all_articles = []

        def fetch_ddg():
            articles = self._fetch_ddg_news(symbol, company_name, limit=30)
            for a in articles:
                a['credibility_score'] = 0.6
                a['source_type'] = 'duckduckgo_news'
            return ('DuckDuckGo News', articles)

        def fetch_finnhub():
            raw = self.finnhub.fetch_company_news(symbol, days_back=1, limit=50)
            recent = [
                a for a in raw
                if _safe_parse_dt(a.get('published_date')) >= yesterday_start
            ]
            return ('Finnhub', recent)

        def fetch_tavily():
            articles = self.tavily.fetch_company_news(symbol, company_name=company_name, limit=10)
            return ('Tavily', articles)

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(fetch_ddg): 'DuckDuckGo',
                executor.submit(fetch_finnhub): 'Finnhub',
                executor.submit(fetch_tavily): 'Tavily',
            }
            for future in as_completed(futures):
                try:
                    source_name, articles = future.result()
                    all_articles.extend(articles)
                    print(f"  ✓ {source_name}: {len(articles)}")
                except Exception as e:
                    print(f"  ⚠️  {futures[future]} error: {e}")

        # Fallback DuckDuckGo Text
        if len(all_articles) < limit:
            ddg_text = self._fetch_ddg_text(symbol, company_name, limit=20)
            for a in ddg_text:
                a['credibility_score'] = 0.5
                a['source_type'] = 'duckduckgo_text'
            all_articles.extend(ddg_text)

        # ── 4. Deduplicate + date filter ──────────────────────────────────────
        unique_articles = self._deduplicate_articles(all_articles)
        now = datetime.now()
        yesterday_start = (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        recent_articles = [
            a for a in unique_articles
            if _safe_parse_dt(a.get('published_date')) >= yesterday_start
        ]
        print(f"  📅 {len(recent_articles)} recent / {len(unique_articles)} total unique")

        if credibility_threshold > 0.0:
            recent_articles = [
                a for a in recent_articles
                if a.get('credibility_score', 0) >= credibility_threshold
            ]

        # ── 5. Rank + FinBERT ─────────────────────────────────────────────────
        ranked = self._rank_articles(recent_articles)
        subset = ranked[:limit]

        if use_finbert and subset:
            subset = self.finbert.analyze_articles(subset)
            stats = self.finbert.aggregate_sentiment(subset)
            print(f"  📊 {stats['overall_label']} score={stats['overall_score']:.2f}")

        # ── 6. Store in background (non-blocking) ─────────────────────────────
        if subset:
            t = threading.Thread(
                target=self._store_background,
                args=(symbol, list(subset)),
                daemon=True
            )
            t.start()

        return subset

    def _store_background(self, symbol: str, articles: list):
        """Persist articles to ChromaDB + MongoDB in a background thread."""
        try:
            self.vector_store.store_articles(symbol, articles)
            self.news_mongo.upsert_articles(symbol, articles)
            if any('finbert_sentiment' in a for a in articles):
                stats = self.finbert.aggregate_sentiment(articles)
                today_str = datetime.now().strftime('%Y-%m-%d')
                self.news_mongo.upsert_daily_sentiment(symbol, today_str, stats)
        except Exception as e:
            print(f"  ⚠️  Background storage error: {e}")

    def _rank_articles(self, articles):
        """
        Rank articles by credibility and recency

        Ranking formula:
            rank_score = credibility_score * 0.7 + recency_score * 0.3

        Recency score uses exponential decay with 3-day half-life
        """
        now = datetime.now()
        half_life_days = 3.0

        for article in articles:
            # Get credibility score
            credibility = article.get('credibility_score', 0.5)

            # Calculate recency score
            try:
                pub_date = datetime.fromisoformat(article['published_date'])
                age_days = (now - pub_date).total_seconds() / 86400.0  # Convert to days
                # Exponential decay: score = exp(-age * ln(2) / half_life)
                recency_score = math.exp(-age_days * math.log(2) / half_life_days)
            except (ValueError, TypeError, KeyError):
                recency_score = 0.5  # Default for unparseable dates

            # Combined rank score (70% credibility, 30% recency)
            rank_score = credibility * 0.7 + recency_score * 0.3
            article['rank_score'] = round(rank_score, 3)
            article['recency_score'] = round(recency_score, 3)

        # Sort by rank score (highest first)
        articles.sort(key=lambda x: x.get('rank_score', 0), reverse=True)
        return articles

    def _fetch_ddg_news(self, symbol, company_name=None, limit=10):
        """Fetch from DuckDuckGo News endpoint"""
        articles = []
        # Use company name in query to avoid ambiguous single-letter symbols
        query_name = company_name if company_name and company_name != symbol else symbol
        try:
            with DDGS() as ddgs:
                results = ddgs.news(
                    f"{query_name} {symbol} stock financial news",
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

    def _fetch_ddg_text(self, symbol, company_name=None, limit=10):
        """Fetch from DuckDuckGo text search as fallback"""
        articles = []
        query_name = company_name if company_name and company_name != symbol else symbol
        try:
            with DDGS() as ddgs:
                results = ddgs.text(
                    f"{query_name} {symbol} stock market news today",
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
