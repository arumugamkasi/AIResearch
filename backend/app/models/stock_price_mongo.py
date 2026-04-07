"""
Stock Price Model (MongoDB)
Handles database operations for historical stock prices using MongoDB
"""

from pymongo import MongoClient, ASCENDING
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd


class StockPriceMongo:
    """Model for stock price data in MongoDB"""

    def __init__(self):
        # Connect to MongoDB
        self.client = MongoClient('mongodb://localhost:27017/')
        self.db = self.client['SkywayResearch']
        self.collection = self.db['StockPrices']

        # Create indexes for fast queries
        self.collection.create_index([('symbol', ASCENDING), ('date', ASCENDING)], unique=True)
        self.collection.create_index([('symbol', ASCENDING)])
        self.collection.create_index([('date', ASCENDING)])

    def insert_prices(self, symbol: str, prices: List[Dict]) -> int:
        """
        Insert multiple price records for a symbol

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            prices: List of price dictionaries with keys:
                   date, open, high, low, close, volume, adj_close

        Returns:
            Number of records inserted
        """
        inserted = 0
        for price in prices:
            try:
                document = {
                    'symbol': symbol.upper(),
                    'date': price['date'],  # String format: YYYY-MM-DD
                    'open': price.get('open'),
                    'high': price.get('high'),
                    'low': price.get('low'),
                    'close': price.get('close'),
                    'volume': price.get('volume'),
                    'adj_close': price.get('adj_close'),
                    'updated_at': datetime.now()
                }

                # Upsert (insert or update if exists)
                self.collection.replace_one(
                    {'symbol': symbol.upper(), 'date': price['date']},
                    document,
                    upsert=True
                )
                inserted += 1
            except Exception as e:
                print(f"Error inserting price for {symbol} on {price.get('date')}: {e}")
                continue

        return inserted

    def get_prices(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Get historical prices for a symbol as DataFrame

        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            limit: Maximum number of records (most recent)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, adj_close
        """
        query = {'symbol': symbol.upper()}

        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['$gte'] = start_date
            if end_date:
                date_filter['$lte'] = end_date
            query['date'] = date_filter

        # Find documents, sorted by date descending
        cursor = self.collection.find(
            query,
            {'_id': 0, 'date': 1, 'open': 1, 'high': 1, 'low': 1,
             'close': 1, 'volume': 1, 'adj_close': 1}
        ).sort('date', -1)

        if limit:
            cursor = cursor.limit(limit)

        # Convert to list and reverse to chronological order
        prices = list(cursor)
        prices.reverse()

        # Convert to DataFrame
        if prices:
            df = pd.DataFrame(prices)
            df['date'] = pd.to_datetime(df['date'])
            return df
        else:
            return pd.DataFrame()

    def get_latest_date(self, symbol: str) -> Optional[str]:
        """
        Get the most recent date for which we have price data

        Args:
            symbol: Stock symbol

        Returns:
            Latest date string (YYYY-MM-DD) or None
        """
        result = self.collection.find_one(
            {'symbol': symbol.upper()},
            {'date': 1},
            sort=[('date', -1)]
        )

        return result['date'] if result else None

    def get_price_count(self, symbol: str) -> int:
        """
        Get count of price records for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Number of price records
        """
        return self.collection.count_documents({'symbol': symbol.upper()})

    def delete_prices(self, symbol: str) -> int:
        """
        Delete all price records for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Number of records deleted
        """
        result = self.collection.delete_many({'symbol': symbol.upper()})
        return result.deleted_count

    def get_all_symbols(self) -> List[str]:
        """
        Get list of all symbols with price data

        Returns:
            List of stock symbols
        """
        symbols = self.collection.distinct('symbol')
        return sorted(symbols)

    def get_date_range(self, symbol: str) -> Dict:
        """
        Get the date range of available data for a symbol

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
        else:
            return {'earliest': None, 'latest': None, 'count': 0}
