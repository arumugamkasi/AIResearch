from datetime import datetime
from pymongo import MongoClient

class AlertConfigMongo:
    def __init__(self):
        self.col = MongoClient('mongodb://localhost:27017/')['SkywayResearch']['AlertConfig']

    def get_config(self):
        return self.col.find_one({'_id': 'main'}, {'_id': 0}) or {}

    def save_config(self, threshold_pct: float, email_enabled: bool, email_to: str):
        self.col.update_one(
            {'_id': 'main'},
            {'$set': {
                'threshold_pct': threshold_pct,
                'email_enabled': email_enabled,
                'email_to': email_to,
                'updated_at': datetime.now(),
            }},
            upsert=True
        )
