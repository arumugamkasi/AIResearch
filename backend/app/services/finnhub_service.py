"""
Finnhub Service - Real-time financial news and data
Free tier: 60 calls/minute
"""

import finnhub
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class FinnhubService:
    """Service for fetching news from Finnhub API"""

    def __init__(self):
        self.api_key = os.getenv('FINNHUB_API_KEY', '')
        self.enabled = bool(self.api_key and self.api_key != 'your_finnhub_key_here')

        if self.enabled:
            try:
                self.client = finnhub.Client(api_key=self.api_key)
                print("✅ Finnhub API configured")
            except Exception as e:
                print(f"⚠️  Finnhub initialization error: {e}")
                self.client = None
                self.enabled = False
        else:
            self.client = None
            print("⚠️  Finnhub API key not configured")

    def is_available(self) -> bool:
        """Check if Finnhub service is available"""
        return self.enabled and self.client is not None

    def fetch_company_news(
        self,
        symbol: str,
        days_back: int = 7,
        limit: int = 50
    ) -> List[Dict]:
        """
        Fetch company-specific news

        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            days_back: Number of days to look back
            limit: Maximum number of articles

        Returns:
            List of news articles
        """
        if not self.is_available():
            return []

        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # Format dates for Finnhub API (YYYY-MM-DD)
            from_date = start_date.strftime('%Y-%m-%d')
            to_date = end_date.strftime('%Y-%m-%d')

            # Fetch news
            news = self.client.company_news(
                symbol.upper(),
                _from=from_date,
                to=to_date
            )

            # Convert to standard format
            articles = []
            for article in news[:limit]:
                articles.append({
                    'title': article.get('headline', ''),
                    'description': article.get('summary', ''),
                    'url': article.get('url', ''),
                    'source': article.get('source', 'Finnhub'),
                    'published_date': datetime.fromtimestamp(
                        article.get('datetime', 0)
                    ).isoformat(),
                    'image': article.get('image', ''),
                    'category': article.get('category', ''),
                    'source_type': 'finnhub',
                    'credibility_score': 0.85  # Finnhub aggregates quality sources
                })

            print(f"📰 Finnhub: Fetched {len(articles)} articles for {symbol}")
            return articles

        except Exception as e:
            print(f"❌ Finnhub error for {symbol}: {e}")
            return []

    def fetch_market_news(
        self,
        category: str = 'general',
        limit: int = 20
    ) -> List[Dict]:
        """
        Fetch general market news

        Args:
            category: News category (general, forex, crypto, merger)
            limit: Maximum number of articles

        Returns:
            List of news articles
        """
        if not self.is_available():
            return []

        try:
            news = self.client.general_news(category, min_id=0)

            articles = []
            for article in news[:limit]:
                articles.append({
                    'title': article.get('headline', ''),
                    'description': article.get('summary', ''),
                    'url': article.get('url', ''),
                    'source': article.get('source', 'Finnhub'),
                    'published_date': datetime.fromtimestamp(
                        article.get('datetime', 0)
                    ).isoformat(),
                    'image': article.get('image', ''),
                    'category': article.get('category', ''),
                    'source_type': 'finnhub',
                    'credibility_score': 0.85
                })

            return articles

        except Exception as e:
            print(f"❌ Finnhub market news error: {e}")
            return []
