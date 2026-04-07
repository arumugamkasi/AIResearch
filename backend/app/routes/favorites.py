from flask import Blueprint, request, jsonify
from app.services.favorites_service import FavoritesService

bp = Blueprint('favorites', __name__, url_prefix='/api/favorites')

favorites_service = FavoritesService()

@bp.route('', methods=['GET'])
def get_favorites():
    """Get all favorite stocks"""
    try:
        favorites = favorites_service.get_all_favorites()
        return jsonify(favorites)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('', methods=['POST'])
def add_favorite():
    """Add a stock to favorites"""
    try:
        data = request.json
        symbol = data.get('symbol')
        name = data.get('name')
        score = data.get('score')

        if not symbol:
            return jsonify({'error': 'Symbol required'}), 400

        favorite = favorites_service.add_favorite(symbol, name, score)
        if not favorite:
            return jsonify({'error': 'Stock already in favorites'}), 409

        return jsonify(favorite), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<symbol>', methods=['DELETE'])
def remove_favorite(symbol):
    """Remove a stock from favorites"""
    try:
        success = favorites_service.remove_favorite(symbol)
        if success:
            return jsonify({'message': 'Stock removed from favorites'}), 200
        return jsonify({'error': 'Stock not found in favorites'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<symbol>/check', methods=['GET'])
def check_favorite(symbol):
    """Check if a stock is in favorites"""
    try:
        is_fav = favorites_service.is_favorite(symbol)
        return jsonify({'is_favorite': is_fav})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
