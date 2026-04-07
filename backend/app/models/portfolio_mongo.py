from datetime import datetime
from pymongo import MongoClient, ASCENDING


INITIAL_POSITIONS = [
    {'portfolio_name': 'ARUIB',  'symbol': 'NVDA',  'quantity': 700},
    {'portfolio_name': 'ARUIB',  'symbol': 'GLD',   'quantity': 150},
    {'portfolio_name': 'ARUIB',  'symbol': 'GOOG',  'quantity': 850},
    {'portfolio_name': 'UMAMM',  'symbol': 'GLD',   'quantity': 9},
    {'portfolio_name': 'UMAMM',  'symbol': 'MRVL',  'quantity': 20},
    {'portfolio_name': 'UMAMM',  'symbol': 'NVDA',  'quantity': 325},
    {'portfolio_name': 'UMAMM',  'symbol': 'RGTI',  'quantity': 10},
    {'portfolio_name': 'ARUMM',  'symbol': 'NVDA',  'quantity': 360},
    {'portfolio_name': 'ARUMM',  'symbol': 'GOOG',  'quantity': 200},
    {'portfolio_name': 'ARUMM',  'symbol': 'GLD',   'quantity': 100},
    {'portfolio_name': 'ARUMM',  'symbol': 'AAPL',  'quantity': 80},
    {'portfolio_name': 'MAANWB', 'symbol': 'NVDA',  'quantity': 110},
    {'portfolio_name': 'MAANWB', 'symbol': 'GLD',   'quantity': 40},
    {'portfolio_name': 'MAANWB', 'symbol': 'GOOGL', 'quantity': 55},
    {'portfolio_name': 'MAANWB', 'symbol': 'QQQ',   'quantity': 10},
    {'portfolio_name': 'MAANWB', 'symbol': 'NFLX',  'quantity': 55},
    {'portfolio_name': 'MAANWB', 'symbol': 'ASML',  'quantity': 1},
    {'portfolio_name': 'MAANWB', 'symbol': 'BRK-B', 'quantity': 2},
]


class PortfolioMongo:
    def __init__(self):
        self.client = MongoClient('mongodb://localhost:27017/')
        self.db = self.client['SkywayResearch']
        self.positions = self.db['PortfolioPositions']
        self._create_indexes()

    def _create_indexes(self):
        self.positions.create_index(
            [('portfolio_name', ASCENDING), ('symbol', ASCENDING)],
            unique=True, background=True
        )
        self.positions.create_index('portfolio_name', background=True)
        self.positions.create_index('symbol', background=True)

    def upsert_position(self, portfolio_name: str, symbol: str,
                        quantity: float, purchase_price: float = None):
        doc = {
            'quantity': quantity,
            'updated_at': datetime.now(),
        }
        if purchase_price is not None:
            doc['purchase_price'] = purchase_price
        self.positions.update_one(
            {'portfolio_name': portfolio_name.upper(),
             'symbol': symbol.upper()},
            {'$set': doc,
             '$setOnInsert': {'created_at': datetime.now()}},
            upsert=True
        )

    def delete_position(self, portfolio_name: str, symbol: str):
        self.positions.delete_one(
            {'portfolio_name': portfolio_name.upper(),
             'symbol': symbol.upper()}
        )

    def get_all_positions(self) -> list:
        docs = list(self.positions.find({}, {'_id': 0}))
        for d in docs:
            for k in ('created_at', 'updated_at'):
                if k in d and hasattr(d[k], 'isoformat'):
                    d[k] = d[k].isoformat()
        return docs

    def get_portfolio_names(self) -> list:
        return sorted(self.positions.distinct('portfolio_name'))

    def count(self) -> int:
        return self.positions.count_documents({})

    def seed_initial_data(self):
        """Insert the initial positions if collection is empty."""
        if self.count() > 0:
            return False
        for pos in INITIAL_POSITIONS:
            self.upsert_position(
                pos['portfolio_name'],
                pos['symbol'],
                pos['quantity']
            )
        return True
