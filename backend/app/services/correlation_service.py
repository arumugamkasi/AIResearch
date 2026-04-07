import requests
from typing import List, Dict
import random

class CorrelationService:
    """Service for finding correlated stocks"""

    def __init__(self):
        # In a real implementation, you would use a financial data API
        # For now, we'll use a simple approach with common stocks
        self.stock_universe = [
            # Tech
            {'symbol': 'AAPL', 'name': 'Apple Inc.', 'sector': 'Technology'},
            {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'sector': 'Technology'},
            {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'sector': 'Technology'},
            {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'sector': 'Technology'},
            {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'sector': 'Technology'},
            {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'sector': 'Technology'},
            {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'sector': 'Automotive'},
            {'symbol': 'AMD', 'name': 'Advanced Micro Devices', 'sector': 'Technology'},
            {'symbol': 'INTC', 'name': 'Intel Corporation', 'sector': 'Technology'},
            {'symbol': 'CRM', 'name': 'Salesforce Inc.', 'sector': 'Technology'},
            # Finance
            {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co.', 'sector': 'Finance'},
            {'symbol': 'BAC', 'name': 'Bank of America Corp.', 'sector': 'Finance'},
            {'symbol': 'WFC', 'name': 'Wells Fargo & Company', 'sector': 'Finance'},
            {'symbol': 'GS', 'name': 'Goldman Sachs Group', 'sector': 'Finance'},
            {'symbol': 'MS', 'name': 'Morgan Stanley', 'sector': 'Finance'},
            # Healthcare
            {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'sector': 'Healthcare'},
            {'symbol': 'UNH', 'name': 'UnitedHealth Group', 'sector': 'Healthcare'},
            {'symbol': 'PFE', 'name': 'Pfizer Inc.', 'sector': 'Healthcare'},
            {'symbol': 'ABBV', 'name': 'AbbVie Inc.', 'sector': 'Healthcare'},
            {'symbol': 'TMO', 'name': 'Thermo Fisher Scientific', 'sector': 'Healthcare'},
            # Retail
            {'symbol': 'WMT', 'name': 'Walmart Inc.', 'sector': 'Retail'},
            {'symbol': 'HD', 'name': 'Home Depot Inc.', 'sector': 'Retail'},
            {'symbol': 'NKE', 'name': 'Nike Inc.', 'sector': 'Retail'},
            {'symbol': 'COST', 'name': 'Costco Wholesale', 'sector': 'Retail'},
            {'symbol': 'TGT', 'name': 'Target Corporation', 'sector': 'Retail'},
            # Energy
            {'symbol': 'XOM', 'name': 'Exxon Mobil Corporation', 'sector': 'Energy'},
            {'symbol': 'CVX', 'name': 'Chevron Corporation', 'sector': 'Energy'},
            {'symbol': 'COP', 'name': 'ConocoPhillips', 'sector': 'Energy'},
            # Entertainment
            {'symbol': 'DIS', 'name': 'Walt Disney Company', 'sector': 'Entertainment'},
            {'symbol': 'NFLX', 'name': 'Netflix Inc.', 'sector': 'Entertainment'},
        ]

    def find_correlated_stocks(self, symbol: str, sentiment_score: float, limit: int = 10) -> List[Dict]:
        """
        Find stocks that are correlated with the given symbol
        In a real implementation, this would use:
        - Historical price correlation analysis
        - Sector/industry relationships
        - Fundamental metrics correlation
        - News sentiment correlation

        For now, we'll use a simplified approach based on sector similarity
        and add some randomness to simulate varying sentiment scores
        """
        # Find the sector of the given symbol
        current_stock = None
        for stock in self.stock_universe:
            if stock['symbol'].upper() == symbol.upper():
                current_stock = stock
                break

        if not current_stock:
            # If stock not in our universe, return random stocks
            all_other_stocks = [s for s in self.stock_universe if s['symbol'] != symbol.upper()]
            similar_stocks = random.sample(all_other_stocks, min(limit, len(all_other_stocks)))
        else:
            # Find stocks in the same sector first
            same_sector = [s for s in self.stock_universe
                          if s['sector'] == current_stock['sector']
                          and s['symbol'] != symbol.upper()]

            # Add some stocks from other sectors
            other_sectors = [s for s in self.stock_universe
                           if s['sector'] != current_stock['sector']]

            # Combine: prioritize same sector, then fill remaining with others
            similar_stocks = []

            # Add same sector stocks first (up to limit)
            similar_stocks.extend(same_sector[:limit])

            # If we need more stocks to reach the limit, add from other sectors
            remaining = limit - len(similar_stocks)
            if remaining > 0 and len(other_sectors) > 0:
                similar_stocks.extend(random.sample(other_sectors, min(remaining, len(other_sectors))))

        # Add simulated correlation scores and sentiment scores
        results = []
        for stock in similar_stocks:
            # Simulate correlation coefficient (0.5 to 0.95 for same sector, 0.3 to 0.7 for others)
            if current_stock and stock['sector'] == current_stock['sector']:
                correlation = round(random.uniform(0.6, 0.95), 2)
                # Similar sentiment for highly correlated stocks
                stock_sentiment = round(sentiment_score + random.uniform(-0.15, 0.15), 2)
            else:
                correlation = round(random.uniform(0.3, 0.7), 2)
                stock_sentiment = round(random.uniform(-0.5, 0.8), 2)

            results.append({
                'symbol': stock['symbol'],
                'name': stock['name'],
                'sector': stock['sector'],
                'correlation': correlation,
                'sentiment_score': max(-1, min(1, stock_sentiment)),  # Clamp between -1 and 1
                'similarity_reason': f"Same sector ({stock['sector']})" if current_stock and stock['sector'] == current_stock['sector'] else f"Cross-sector correlation"
            })

        # Sort by correlation score (highest first)
        results.sort(key=lambda x: x['correlation'], reverse=True)

        return results[:limit]
