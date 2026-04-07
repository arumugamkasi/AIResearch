from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING


class PortfolioSnapshotMongo:
    """
    Stores daily portfolio snapshots for YTD P&L tracking.

    Collection: PortfolioSnapshots
    One document per date (upserted each time analysis is run).

    Schema:
      date             : "YYYY-MM-DD"  (unique per day)
      total_value      : float
      equity_value     : float
      portfolio_cash   : float
      symbol_values    : { SYMBOL: {market_value, price, total_qty} }      ← consolidated
      portfolio_values : { PORTFOLIO_NAME: {total_value, equity_value,
                                            portfolio_cash} }               ← per-portfolio
      created_at       : datetime
      updated_at       : datetime
    """

    def __init__(self):
        self.client = MongoClient('mongodb://localhost:27017/')
        self.db = self.client['SkywayResearch']
        self.col = self.db['PortfolioSnapshots']
        self._ensure_indexes()

    def _ensure_indexes(self):
        self.col.create_index('date', unique=True, background=True)

    def save_snapshot(self, total_value: float, equity_value: float,
                      portfolio_cash: float, symbol_values: dict,
                      portfolio_values: dict = None):
        """Insert today's snapshot on first write; never overwrite during the day.
        Value fields use $setOnInsert so the first run's values become the
        immutable daily baseline used for YTD P&L comparisons.
        symbol_values    = {sym: {market_value, price, total_qty}}
        portfolio_values = {portfolio_name: {total_value, equity_value, portfolio_cash}}
        """
        today = datetime.now().strftime('%Y-%m-%d')
        on_insert = {
            'created_at':     datetime.now(),
            'total_value':    total_value,
            'equity_value':   equity_value,
            'portfolio_cash': portfolio_cash,
            'symbol_values':  symbol_values,
        }
        if portfolio_values:
            on_insert['portfolio_values'] = portfolio_values
        self.col.update_one(
            {'date': today},
            {
                '$set':         {'updated_at': datetime.now()},
                '$setOnInsert': on_insert,
            },
            upsert=True
        )
        return today

    def get_ytd_start_snapshot(self):
        """
        Return the YTD baseline snapshot:
          1. Jan 1 of the current year if it exists, else
          2. The earliest snapshot in the current year, else
          3. None (no history yet).
        """
        year = datetime.now().year
        jan1 = f'{year}-01-01'

        # Try exact Jan 1
        doc = self.col.find_one({'date': jan1}, {'_id': 0})
        if doc:
            return doc

        # Earliest in current year
        doc = self.col.find_one(
            {'date': {'$gte': jan1, '$lt': f'{year + 1}-01-01'}},
            {'_id': 0},
            sort=[('date', ASCENDING)]
        )
        return doc

    def get_all_snapshot_dates(self) -> list:
        """Return list of all stored snapshot dates, newest first."""
        return [d['date'] for d in self.col.find({}, {'date': 1, '_id': 0},
                                                  sort=[('date', DESCENDING)])]
