from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId

class FavoritesService:
    """Service for managing favorite stocks in MongoDB"""

    def __init__(self):
        self.client = MongoClient('mongodb://localhost:27017/')
        self.db = self.client['SkywayResearch']
        self.favorites = self.db['FavoriteStocks']

    def get_all_favorites(self):
        """Get all favorite stocks"""
        favorites = list(self.favorites.find())
        for fav in favorites:
            fav['_id'] = str(fav['_id'])
        return favorites

    def add_favorite(self, symbol, name=None, score=None):
        """Add a stock to favorites"""
        # Check if already in favorites
        existing = self.favorites.find_one({'symbol': symbol.upper()})
        if existing:
            return None

        favorite = {
            'symbol': symbol.upper(),
            'name': name or symbol.upper(),
            'score': score,
            'added_date': datetime.now()
        }

        result = self.favorites.insert_one(favorite)
        favorite['_id'] = str(result.inserted_id)
        return favorite

    def remove_favorite(self, symbol):
        """Remove a stock from favorites"""
        result = self.favorites.delete_one({'symbol': symbol.upper()})
        return result.deleted_count > 0

    def is_favorite(self, symbol):
        """Check if a stock is in favorites"""
        return self.favorites.find_one({'symbol': symbol.upper()}) is not None

    def update_score(self, symbol, score):
        """Update the score for a favorite stock"""
        result = self.favorites.update_one(
            {'symbol': symbol.upper()},
            {'$set': {'score': score, 'updated_date': datetime.now()}}
        )
        return result.modified_count > 0
