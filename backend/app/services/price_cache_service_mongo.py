"""
Price Cache Service (MongoDB)
Manages historical price data caching using MongoDB
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List
from app.models.stock_price_mongo import StockPriceMongo


class PriceCacheServiceMongo:
    """Service for caching and retrieving historical stock prices using MongoDB"""

    def __init__(self):
        self.stock_price_model = StockPriceMongo()
        # Cache is considered stale if older than 1 day
        self.max_cache_age_days = 1
        # In-memory set of symbols already fetched in this process session today
        # Avoids repeated yfinance calls within a single server run
        self._fetched_today: Dict[str, date] = {}

    def get_prices(
        self,
        symbol: str,
        days: int = 365,
        force_refresh: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        Get historical prices for a symbol

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            days: Number of days of history to fetch
            force_refresh: If True, fetch fresh data from yfinance

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, adj_close
            Returns None if no data available
        """
        # Check if we need to fetch new data
        # Skip network fetch if we already fetched for this symbol today (in-process cache)
        already_fetched_today = (
            not force_refresh
            and symbol in self._fetched_today
            and self._fetched_today[symbol] == date.today()
        )
        needs_update = not already_fetched_today and (force_refresh or self._needs_update(symbol))

        if needs_update:
            print(f"📥 Fetching fresh price data for {symbol}")
            success = self._fetch_and_cache(symbol, days)
            if success:
                self._fetched_today[symbol] = date.today()
            else:
                print(f"⚠️  Failed to fetch data for {symbol}, using cached data if available")

        # Get data from MongoDB
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        df = self.stock_price_model.get_prices(
            symbol,
            start_date=start_date
        )

        if df.empty:
            print(f"❌ No price data available for {symbol}")
            return None

        print(f"✅ Retrieved {len(df)} days of price data for {symbol} from MongoDB")
        return df

    def _needs_update(self, symbol: str) -> bool:
        """
        Check if cached data needs to be updated

        Args:
            symbol: Stock symbol

        Returns:
            True if data is stale or missing
        """
        latest_date = self.stock_price_model.get_latest_date(symbol)

        if not latest_date:
            # No data cached
            return True

        # Parse latest date
        try:
            latest = datetime.strptime(latest_date, '%Y-%m-%d').date()
        except:
            return True

        # Check if data is stale
        today = date.today()
        age_days = (today - latest).days

        # Update if data is more than max_cache_age_days old
        if age_days > self.max_cache_age_days:
            return True

        # On weekends, data from Friday is OK
        if today.weekday() >= 5:  # Saturday or Sunday
            # We're OK if we have Friday's data
            friday = today - timedelta(days=today.weekday() - 4)
            return latest < friday
        else:
            # On weekdays, we should have yesterday's data at minimum
            yesterday = today - timedelta(days=1)
            return latest < yesterday

    def _fetch_and_cache(self, symbol: str, days: int = 730) -> bool:
        """
        Fetch fresh data from yfinance and cache it

        Args:
            symbol: Stock symbol
            days: Number of days to fetch (default 730 = 2 years)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Fetch data from yfinance
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d')
            )

            if df.empty:
                print(f"⚠️  No data returned from yfinance for {symbol}")
                return False

            # Convert to list of dictionaries
            prices = []
            for date_idx, row in df.iterrows():
                prices.append({
                    'date': date_idx.strftime('%Y-%m-%d'),
                    'open': float(row['Open']) if not pd.isna(row['Open']) else None,
                    'high': float(row['High']) if not pd.isna(row['High']) else None,
                    'low': float(row['Low']) if not pd.isna(row['Low']) else None,
                    'close': float(row['Close']) if not pd.isna(row['Close']) else None,
                    'volume': int(row['Volume']) if not pd.isna(row['Volume']) else 0,
                    'adj_close': float(row['Close']) if not pd.isna(row['Close']) else None,
                })

            # Insert into MongoDB
            inserted = self.stock_price_model.insert_prices(symbol, prices)
            print(f"✅ Cached {inserted} price records for {symbol} in MongoDB")

            return inserted > 0

        except Exception as e:
            print(f"❌ Error fetching/caching data for {symbol}: {e}")
            return False

    def clear_cache(self, symbol: str) -> int:
        """
        Clear cached price data for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Number of records deleted
        """
        deleted = self.stock_price_model.delete_prices(symbol)
        print(f"🗑️  Cleared {deleted} price records for {symbol} from MongoDB")
        return deleted

    def get_cache_info(self, symbol: str) -> Dict:
        """
        Get information about cached data for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary with cache info
        """
        count = self.stock_price_model.get_price_count(symbol)
        date_range = self.stock_price_model.get_date_range(symbol)

        info = {
            'symbol': symbol,
            'record_count': count,
            'earliest_date': date_range['earliest'],
            'latest_date': date_range['latest'],
            'needs_update': self._needs_update(symbol)
        }

        if date_range['latest']:
            try:
                latest = datetime.strptime(date_range['latest'], '%Y-%m-%d').date()
                info['days_old'] = (date.today() - latest).days
            except:
                pass

        return info

    def get_all_cached_symbols(self) -> List[str]:
        """
        Get list of all symbols with cached data

        Returns:
            List of stock symbols
        """
        return self.stock_price_model.get_all_symbols()

    def bulk_update(self, symbols: List[str]) -> Dict[str, bool]:
        """
        Update cache for multiple symbols

        Args:
            symbols: List of stock symbols

        Returns:
            Dictionary mapping symbol to success status
        """
        results = {}
        for symbol in symbols:
            if self._needs_update(symbol):
                results[symbol] = self._fetch_and_cache(symbol)
            else:
                results[symbol] = True  # Already up to date

        return results
