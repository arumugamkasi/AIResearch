import yfinance as yf
from datetime import datetime

class PriceService:
    """Service for fetching stock prices and historical data using yfinance"""

    def get_current_price(self, symbol):
        """Get current stock price"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info or 'regularMarketPrice' not in info:
                # Fallback to fast_info if info doesn't have price
                fast_info = ticker.fast_info
                current_price = fast_info.get('lastPrice') or fast_info.get('regularMarketPrice', 0)
                previous_close = fast_info.get('previousClose', current_price)
            else:
                current_price = info.get('regularMarketPrice', 0)
                previous_close = info.get('previousClose', current_price)

            change = current_price - previous_close
            change_percent = (change / previous_close * 100) if previous_close else 0

            return {
                'symbol': symbol,
                'price': round(current_price, 2),
                'currency': info.get('currency', 'USD') if info else 'USD',
                'previous_close': round(previous_close, 2),
                'change': round(change, 2),
                'change_percent': round(change_percent, 2),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            print(f"Error fetching current price for {symbol}: {e}")
            return None

    def get_historical_data(self, symbol, period='1mo', interval='1d'):
        """
        Get historical stock price data

        Periods: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max
        Intervals: 1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)

            if hist.empty:
                return None

            # Convert DataFrame to list of dictionaries
            historical_data = []
            for index, row in hist.iterrows():
                historical_data.append({
                    'date': index.strftime('%Y-%m-%d'),
                    'timestamp': int(index.timestamp()),
                    'open': round(float(row['Open']), 2),
                    'high': round(float(row['High']), 2),
                    'low': round(float(row['Low']), 2),
                    'close': round(float(row['Close']), 2),
                    'volume': int(row['Volume'])
                })

            return {
                'symbol': symbol,
                'period': period,
                'interval': interval,
                'data': historical_data
            }

        except Exception as e:
            print(f"Error fetching historical data for {symbol}: {e}")
            return None
