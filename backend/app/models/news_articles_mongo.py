"""
MongoDB Model for News Articles
Stores fetched articles with FinBERT sentiment for backtesting and historical analysis
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class NewsArticlesMongo:
    """MongoDB model for news articles and daily sentiment summaries"""

    def __init__(self):
        self.client = MongoClient('mongodb://localhost:27017/')
        self.db = self.client['SkywayResearch']
        self.articles = self.db['NewsArticles']
        self.daily_sentiment = self.db['DailySentiment']
        self._create_indexes()

    def _create_indexes(self):
        """Create indexes for efficient querying"""
        # Unique constraint on (symbol, url) to prevent duplicates
        self.articles.create_index(
            [('symbol', ASCENDING), ('url', ASCENDING)],
            unique=True, background=True
        )
        # Fast date-range queries per stock
        self.articles.create_index(
            [('symbol', ASCENDING), ('published_date', DESCENDING)],
            background=True
        )
        # For archival/cleanup
        self.articles.create_index('fetch_date', background=True)

        # Daily sentiment: unique per (symbol, date)
        self.daily_sentiment.create_index(
            [('symbol', ASCENDING), ('date', ASCENDING)],
            unique=True, background=True
        )

    def upsert_articles(self, symbol: str, articles: List[Dict]) -> int:
        """
        Store articles in MongoDB. Updates existing articles, inserts new ones.

        Args:
            symbol: Stock ticker
            articles: List of article dicts (from fetch_news_multi_source)

        Returns:
            Number of articles stored
        """
        if not articles:
            return 0

        stored = 0
        fetch_date = datetime.now()

        for article in articles:
            if not article.get('url'):
                continue  # Skip articles without a URL (can't deduplicate)

            doc = {
                'symbol': symbol.upper(),
                'fetch_date': fetch_date,
                'published_date': article.get('published_date'),
                'title': article.get('title', ''),
                'description': article.get('description', ''),
                'url': article.get('url', ''),
                'source': article.get('source', ''),
                'source_type': article.get('source_type', ''),
                'credibility_score': article.get('credibility_score', 0.5),
                'rank_score': article.get('rank_score'),
                'finbert_sentiment': article.get('finbert_sentiment'),
            }

            try:
                self.articles.update_one(
                    {'symbol': symbol.upper(), 'url': article['url']},
                    {'$set': doc},
                    upsert=True
                )
                stored += 1
            except Exception as e:
                print(f"    ⚠️  Failed to store article: {e}")

        return stored

    def upsert_daily_sentiment(self, symbol: str, date_str: str, sentiment_data: Dict) -> bool:
        """
        Store aggregated daily sentiment (FinBERT-based).

        Args:
            symbol: Stock ticker
            date_str: Date as 'YYYY-MM-DD'
            sentiment_data: Output from FinBERTSentimentAnalyzer.aggregate_sentiment()

        Returns:
            True if stored successfully
        """
        try:
            doc = {
                'symbol': symbol.upper(),
                'date': date_str,
                'sentiment_score': sentiment_data.get('overall_score', 0.0),
                'sentiment_label': sentiment_data.get('overall_label', 'neutral'),
                'article_count': sentiment_data.get('article_count', 0),
                'positive_ratio': sentiment_data.get('positive_ratio', 0.0),
                'negative_ratio': sentiment_data.get('negative_ratio', 0.0),
                'neutral_ratio': sentiment_data.get('neutral_ratio', 0.0),
                'avg_confidence': sentiment_data.get('avg_confidence', 0.0),
                'source': 'finbert',
                'updated_at': datetime.now()
            }

            self.daily_sentiment.update_one(
                {'symbol': symbol.upper(), 'date': date_str},
                {'$set': doc},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"    ⚠️  Failed to store daily sentiment: {e}")
            return False

    def get_fresh_articles(self, symbol: str, max_age_minutes: int = 60) -> List[Dict]:
        """
        Return cached articles if they were fetched recently (within max_age_minutes).
        Used to avoid re-fetching on every UI click.

        Returns empty list if cache is stale or missing (caller should re-fetch).
        """
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        yesterday_start = (datetime.now() - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Check whether we have any recently-fetched article for this symbol
        recent_fetch = self.articles.find_one(
            {'symbol': symbol.upper(), 'fetch_date': {'$gte': cutoff}},
            {'_id': 0, 'fetch_date': 1}
        )
        if not recent_fetch:
            return []

        # Return today/yesterday articles sorted by rank_score
        cursor = self.articles.find(
            {
                'symbol': symbol.upper(),
                'published_date': {'$gte': yesterday_start.isoformat()}
            },
            {'_id': 0}
        ).sort([('rank_score', DESCENDING)]).limit(200)

        return list(cursor)

    def get_articles(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 200
    ) -> List[Dict]:
        """Get articles for a symbol within an optional date range"""
        query = {'symbol': symbol.upper()}
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['$gte'] = start_date
            if end_date:
                date_filter['$lte'] = end_date
            query['published_date'] = date_filter

        cursor = self.articles.find(
            query, {'_id': 0}
        ).sort('published_date', DESCENDING).limit(limit)

        return list(cursor)

    def get_daily_sentiment(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """Get daily sentiment records for backtesting"""
        query = {'symbol': symbol.upper()}
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['$gte'] = start_date
            if end_date:
                date_filter['$lte'] = end_date
            query['date'] = date_filter

        cursor = self.daily_sentiment.find(
            query, {'_id': 0}
        ).sort('date', ASCENDING)

        return list(cursor)
