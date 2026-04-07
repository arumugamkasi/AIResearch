"""
MongoDB Model for Historical Sentiment Data
Stores daily sentiment scores from Alpha Vantage News Sentiment API
"""

from pymongo import MongoClient, ASCENDING
from datetime import datetime
from typing import Optional, List, Dict
import pandas as pd


class HistoricalSentimentMongo:
    """MongoDB model for historical stock sentiment data"""

    def __init__(self):
        self.client = MongoClient('mongodb://localhost:27017/')
        self.db = self.client['SkywayResearch']
        self.collection = self.db['HistoricalSentiment']
        self._create_indexes()

    def _create_indexes(self):
        """Create indexes for efficient querying"""
        # Unique index on symbol + date
        self.collection.create_index(
            [('symbol', ASCENDING), ('date', ASCENDING)],
            unique=True,
            background=True
        )
        # Index on symbol for quick lookups
        self.collection.create_index('symbol', background=True)
        # Index on date for time-range queries
        self.collection.create_index('date', background=True)

    def insert_sentiment(self, symbol: str, date: str, sentiment_data: Dict) -> bool:
        """
        Insert or update sentiment data for a specific date

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            date: Date string in format 'YYYY-MM-DD'
            sentiment_data: Dict with sentiment metrics

        Returns:
            True if successful, False otherwise
        """
        try:
            document = {
                'symbol': symbol.upper(),
                'date': date,
                'sentiment_score': sentiment_data.get('sentiment_score', 0.0),
                'sentiment_label': sentiment_data.get('sentiment_label', 'Neutral'),
                'articles_count': sentiment_data.get('articles_count', 0),
                'relevance_score': sentiment_data.get('relevance_score', 0.0),
                'positive_ratio': sentiment_data.get('positive_ratio', 0.0),
                'negative_ratio': sentiment_data.get('negative_ratio', 0.0),
                'neutral_ratio': sentiment_data.get('neutral_ratio', 0.0),
                'updated_at': datetime.now()
            }

            # Upsert (update if exists, insert if not)
            self.collection.update_one(
                {'symbol': symbol.upper(), 'date': date},
                {'$set': document},
                upsert=True
            )
            return True

        except Exception as e:
            print(f"Error inserting sentiment for {symbol} on {date}: {e}")
            return False

    def bulk_insert_sentiments(self, symbol: str, sentiments: List[Dict]) -> int:
        """
        Insert multiple sentiment records

        Args:
            symbol: Stock symbol
            sentiments: List of dicts with 'date' and sentiment data

        Returns:
            Number of records inserted/updated
        """
        inserted_count = 0
        for sentiment in sentiments:
            date = sentiment.pop('date')
            if self.insert_sentiment(symbol, date, sentiment):
                inserted_count += 1
        return inserted_count

    def get_sentiment(self, symbol: str, date: str) -> Optional[Dict]:
        """
        Get sentiment for a specific date

        Args:
            symbol: Stock symbol
            date: Date string 'YYYY-MM-DD'

        Returns:
            Sentiment dict or None if not found
        """
        result = self.collection.find_one(
            {'symbol': symbol.upper(), 'date': date},
            {'_id': 0}
        )
        return result

    def get_sentiments(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get sentiment data for a date range

        Args:
            symbol: Stock symbol
            start_date: Start date 'YYYY-MM-DD' (optional)
            end_date: End date 'YYYY-MM-DD' (optional)

        Returns:
            DataFrame with sentiment data sorted by date
        """
        query = {'symbol': symbol.upper()}

        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['$gte'] = start_date
            if end_date:
                date_filter['$lte'] = end_date
            query['date'] = date_filter

        cursor = self.collection.find(
            query,
            {'_id': 0}
        ).sort('date', ASCENDING)

        df = pd.DataFrame(list(cursor))
        return df

    def get_latest_date(self, symbol: str) -> Optional[str]:
        """
        Get the latest date with sentiment data for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Latest date string or None if no data
        """
        result = self.collection.find_one(
            {'symbol': symbol.upper()},
            {'date': 1, '_id': 0},
            sort=[('date', -1)]
        )
        return result['date'] if result else None

    def get_sentiment_count(self, symbol: str) -> int:
        """
        Count sentiment records for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Number of records
        """
        return self.collection.count_documents({'symbol': symbol.upper()})

    def get_date_range(self, symbol: str) -> Dict:
        """
        Get the date range of available sentiment data

        Args:
            symbol: Stock symbol

        Returns:
            Dict with 'earliest' and 'latest' dates
        """
        pipeline = [
            {'$match': {'symbol': symbol.upper()}},
            {'$group': {
                '_id': '$symbol',
                'earliest': {'$min': '$date'},
                'latest': {'$max': '$date'},
                'count': {'$sum': 1}
            }}
        ]

        result = list(self.collection.aggregate(pipeline))
        if result:
            return {
                'earliest': result[0]['earliest'],
                'latest': result[0]['latest'],
                'count': result[0]['count']
            }
        return {'earliest': None, 'latest': None, 'count': 0}

    def delete_sentiments(self, symbol: str) -> int:
        """
        Delete all sentiment data for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Number of records deleted
        """
        result = self.collection.delete_many({'symbol': symbol.upper()})
        return result.deleted_count

    def get_all_symbols(self) -> List[str]:
        """
        Get list of all symbols with sentiment data

        Returns:
            List of stock symbols
        """
        return self.collection.distinct('symbol')
