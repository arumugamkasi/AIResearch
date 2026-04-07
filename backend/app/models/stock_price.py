"""
Stock Price Model
Handles database operations for historical stock prices
"""

import sqlite3
from datetime import datetime, date
from typing import List, Dict, Optional
import os


class StockPrice:
    """Model for stock price data"""

    def __init__(self):
        # Get database path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(os.path.dirname(current_dir))
        self.db_path = os.path.join(backend_dir, 'database', 'stocks.db')

    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)

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
        conn = self._get_connection()
        cursor = conn.cursor()

        inserted = 0
        for price in prices:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_prices
                    (symbol, date, open, high, low, close, volume, adj_close, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol.upper(),
                    price['date'],
                    price.get('open'),
                    price.get('high'),
                    price.get('low'),
                    price.get('close'),
                    price.get('volume'),
                    price.get('adj_close'),
                    datetime.now()
                ))
                inserted += 1
            except Exception as e:
                print(f"Error inserting price for {symbol} on {price.get('date')}: {e}")
                continue

        conn.commit()
        conn.close()
        return inserted

    def get_prices(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get historical prices for a symbol

        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            limit: Maximum number of records (most recent)

        Returns:
            List of price dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = '''
            SELECT date, open, high, low, close, volume, adj_close
            FROM stock_prices
            WHERE symbol = ?
        '''
        params = [symbol.upper()]

        if start_date:
            query += ' AND date >= ?'
            params.append(start_date)

        if end_date:
            query += ' AND date <= ?'
            params.append(end_date)

        query += ' ORDER BY date DESC'

        if limit:
            query += ' LIMIT ?'
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        # Convert to list of dictionaries
        prices = []
        for row in rows:
            prices.append({
                'date': row[0],
                'open': row[1],
                'high': row[2],
                'low': row[3],
                'close': row[4],
                'volume': row[5],
                'adj_close': row[6]
            })

        # Reverse to chronological order (oldest first)
        return list(reversed(prices))

    def get_latest_date(self, symbol: str) -> Optional[str]:
        """
        Get the most recent date for which we have price data

        Args:
            symbol: Stock symbol

        Returns:
            Latest date string (YYYY-MM-DD) or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT MAX(date)
            FROM stock_prices
            WHERE symbol = ?
        ''', (symbol.upper(),))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result and result[0] else None

    def get_price_count(self, symbol: str) -> int:
        """
        Get count of price records for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Number of price records
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*)
            FROM stock_prices
            WHERE symbol = ?
        ''', (symbol.upper(),))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else 0

    def delete_prices(self, symbol: str) -> int:
        """
        Delete all price records for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Number of records deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM stock_prices
            WHERE symbol = ?
        ''', (symbol.upper(),))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        return deleted

    def get_all_symbols(self) -> List[str]:
        """
        Get list of all symbols with price data

        Returns:
            List of stock symbols
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT symbol
            FROM stock_prices
            ORDER BY symbol
        ''')

        rows = cursor.fetchall()
        conn.close()

        return [row[0] for row in rows]
