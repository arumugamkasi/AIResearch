import json
import os
from datetime import datetime

class StockService:
    """Service for managing stock tracking"""
    
    def __init__(self):
        # Get the directory where this service file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up two levels to the backend directory
        backend_dir = os.path.dirname(os.path.dirname(current_dir))
        self.STOCKS_FILE = os.path.join(backend_dir, 'stocks.json')
        self.stocks = self._load_stocks()
    
    def _load_stocks(self):
        """Load stocks from file"""
        if os.path.exists(self.STOCKS_FILE):
            with open(self.STOCKS_FILE, 'r') as f:
                return json.load(f)
        return []
    
    def _save_stocks(self):
        """Save stocks to file"""
        with open(self.STOCKS_FILE, 'w') as f:
            json.dump(self.stocks, f, indent=2)
    
    def get_all_stocks(self):
        """Get all tracked stocks"""
        return self.stocks
    
    def get_stock_by_symbol(self, symbol):
        """Get a stock by symbol"""
        for stock in self.stocks:
            if stock['symbol'].upper() == symbol.upper():
                return stock
        return None
    
    def add_stock(self, symbol, name=None):
        """Add a new stock to track"""
        if self.get_stock_by_symbol(symbol):
            return None
        
        stock = {
            'symbol': symbol.upper(),
            'name': name or symbol,
            'added_date': datetime.now().isoformat(),
            'notes': ''
        }
        
        self.stocks.append(stock)
        self._save_stocks()
        return stock
    
    def delete_stock(self, symbol):
        """Remove a stock from tracking"""
        initial_count = len(self.stocks)
        self.stocks = [s for s in self.stocks if s['symbol'].upper() != symbol.upper()]
        
        if len(self.stocks) < initial_count:
            self._save_stocks()
            return True
        return False
    
    def update_stock_notes(self, symbol, notes):
        """Update notes for a stock"""
        stock = self.get_stock_by_symbol(symbol)
        if stock:
            stock['notes'] = notes
            self._save_stocks()
            return stock
        return None
