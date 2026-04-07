"""
Alpha Vantage News Sentiment API Service
Fetches historical news sentiment data for stocks
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from app.models.historical_sentiment_mongo import HistoricalSentimentMongo


class AlphaVantageService:
    """Service for fetching news sentiment from Alpha Vantage API"""

    def __init__(self):
        self.api_key = os.getenv('ALPHA_VANTAGE_API_KEY', '')
        self.base_url = 'https://www.alphavantage.co/query'
        self.sentiment_model = HistoricalSentimentMongo()
        self.enabled = bool(self.api_key and self.api_key != 'YOUR_API_KEY_HERE')

        if not self.enabled:
            print("⚠️  Alpha Vantage API key not configured.")
            print("   Historical sentiment data will not be available.")
            print("   Get a free key at: https://www.alphavantage.co/support/#api-key")

    def fetch_news_sentiment(
        self,
        symbol: str,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        limit: int = 1000
    ) -> Optional[Dict]:
        """
        Fetch news sentiment from Alpha Vantage API

        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            time_from: Start datetime in format 'YYYYMMDDTHHMM' (optional)
            time_to: End datetime in format 'YYYYMMDDTHHMM' (optional)
            limit: Max number of articles (default 1000)

        Returns:
            API response dict or None if error
        """
        if not self.enabled:
            return None

        params = {
            'function': 'NEWS_SENTIMENT',
            'tickers': symbol.upper(),
            'apikey': self.api_key,
            'limit': limit
        }

        if time_from:
            params['time_from'] = time_from
        if time_to:
            params['time_to'] = time_to

        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if 'Error Message' in data:
                print(f"❌ Alpha Vantage API error: {data['Error Message']}")
                return None

            if 'Note' in data:
                print(f"⚠️  Alpha Vantage rate limit: {data['Note']}")
                return None

            return data

        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching Alpha Vantage data: {e}")
            return None

    def process_and_cache_sentiment(
        self,
        symbol: str,
        days_back: int = 365
    ) -> int:
        """
        Fetch news sentiment and cache daily aggregated scores in MongoDB

        Args:
            symbol: Stock ticker
            days_back: How many days of history to fetch (default 365)

        Returns:
            Number of days cached
        """
        if not self.enabled:
            print(f"⚠️  Alpha Vantage not configured, skipping sentiment fetch for {symbol}")
            return 0

        print(f"📰 Fetching {days_back} days of news sentiment for {symbol}...")

        # Calculate time range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        time_from = start_date.strftime('%Y%m%dT0000')
        time_to = end_date.strftime('%Y%m%dT2359')

        # Fetch from API
        data = self.fetch_news_sentiment(symbol, time_from, time_to)

        if not data or 'feed' not in data:
            print(f"❌ No sentiment data returned for {symbol}")
            return 0

        articles = data.get('feed', [])
        print(f"   Retrieved {len(articles)} articles")

        # Aggregate by day
        daily_sentiments = self._aggregate_daily_sentiment(symbol, articles)

        # Cache in MongoDB
        cached_count = self.sentiment_model.bulk_insert_sentiments(symbol, daily_sentiments)
        print(f"✅ Cached {cached_count} days of sentiment for {symbol}")

        return cached_count

    def _aggregate_daily_sentiment(self, symbol: str, articles: List[Dict]) -> List[Dict]:
        """
        Aggregate news articles into daily sentiment scores

        Args:
            symbol: Stock ticker
            articles: List of article dicts from Alpha Vantage

        Returns:
            List of daily sentiment dicts
        """
        from collections import defaultdict

        # Group articles by date
        daily_groups = defaultdict(list)

        for article in articles:
            # Get article timestamp
            time_published = article.get('time_published', '')
            if not time_published:
                continue

            # Parse date (format: YYYYMMDDTHHMMSS)
            try:
                date = datetime.strptime(time_published[:8], '%Y%m%d').strftime('%Y-%m-%d')
            except:
                continue

            # Get ticker-specific sentiment
            ticker_sentiments = article.get('ticker_sentiment', [])
            for ticker_data in ticker_sentiments:
                if ticker_data.get('ticker', '').upper() == symbol.upper():
                    daily_groups[date].append({
                        'sentiment_score': float(ticker_data.get('ticker_sentiment_score', 0)),
                        'sentiment_label': ticker_data.get('ticker_sentiment_label', 'Neutral'),
                        'relevance_score': float(ticker_data.get('relevance_score', 0))
                    })
                    break

        # Aggregate each day
        daily_sentiments = []
        for date, day_articles in daily_groups.items():
            if not day_articles:
                continue

            # Calculate weighted average sentiment (weight by relevance)
            total_relevance = sum(a['relevance_score'] for a in day_articles)
            if total_relevance > 0:
                weighted_sentiment = sum(
                    a['sentiment_score'] * a['relevance_score']
                    for a in day_articles
                ) / total_relevance
            else:
                weighted_sentiment = sum(a['sentiment_score'] for a in day_articles) / len(day_articles)

            # Count sentiment labels
            labels = [a['sentiment_label'] for a in day_articles]
            total = len(labels)
            positive_count = sum(1 for l in labels if 'Bullish' in l or 'Positive' in l)
            negative_count = sum(1 for l in labels if 'Bearish' in l or 'Negative' in l)
            neutral_count = total - positive_count - negative_count

            # Determine overall label
            if weighted_sentiment > 0.15:
                overall_label = 'Bullish'
            elif weighted_sentiment < -0.15:
                overall_label = 'Bearish'
            else:
                overall_label = 'Neutral'

            daily_sentiments.append({
                'date': date,
                'sentiment_score': round(weighted_sentiment, 4),
                'sentiment_label': overall_label,
                'articles_count': len(day_articles),
                'relevance_score': round(total_relevance / len(day_articles), 4),
                'positive_ratio': round(positive_count / total, 3),
                'negative_ratio': round(negative_count / total, 3),
                'neutral_ratio': round(neutral_count / total, 3)
            })

        return sorted(daily_sentiments, key=lambda x: x['date'])

    def get_cached_sentiment(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        auto_fetch: bool = True
    ) -> Optional[object]:
        """
        Get cached sentiment data, optionally fetching if missing

        Args:
            symbol: Stock ticker
            start_date: Start date 'YYYY-MM-DD'
            end_date: End date 'YYYY-MM-DD'
            auto_fetch: If True, fetch from API if cache is empty

        Returns:
            DataFrame with sentiment data
        """
        # Check if we have cached data
        cache_info = self.sentiment_model.get_date_range(symbol)

        if cache_info['count'] == 0 and auto_fetch and self.enabled:
            # No cached data - fetch from API
            print(f"📥 No cached sentiment for {symbol}, fetching from Alpha Vantage...")
            self.process_and_cache_sentiment(symbol, days_back=365)

        # Get cached data
        df = self.sentiment_model.get_sentiments(symbol, start_date, end_date)
        return df if not df.empty else None

    def update_sentiment_cache(self, symbol: str) -> int:
        """
        Update sentiment cache with recent data

        Args:
            symbol: Stock ticker

        Returns:
            Number of new days cached
        """
        if not self.enabled:
            return 0

        # Get latest cached date
        latest_date = self.sentiment_model.get_latest_date(symbol)

        if latest_date:
            # Fetch only new data since last update
            latest_dt = datetime.strptime(latest_date, '%Y-%m-%d')
            days_to_fetch = (datetime.now() - latest_dt).days + 1
            print(f"🔄 Updating {symbol} sentiment (last cached: {latest_date})")
        else:
            # No cache - fetch full history
            days_to_fetch = 365
            print(f"📥 Fetching full sentiment history for {symbol}")

        return self.process_and_cache_sentiment(symbol, days_back=days_to_fetch)

    def is_available(self) -> bool:
        """Check if Alpha Vantage service is available"""
        return self.enabled
