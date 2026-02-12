from flask import Blueprint, request, jsonify
from app.services.news_service import NewsService

bp = Blueprint('news', __name__, url_prefix='/api/news')

news_service = NewsService()

@bp.route('/search', methods=['GET'])
def search_news():
    """Search financial news for a stock"""
    symbol = request.args.get('symbol')
    limit = request.args.get('limit', 10, type=int)
    
    if not symbol:
        return jsonify({'error': 'Symbol required'}), 400
    
    news = news_service.fetch_news(symbol, limit)
    return jsonify({'symbol': symbol, 'articles': news})

@bp.route('/trending', methods=['GET'])
def get_trending():
    """Get trending financial news"""
    limit = request.args.get('limit', 20, type=int)
    news = news_service.get_trending_news(limit)
    return jsonify({'articles': news})

@bp.route('/bulk-search', methods=['POST'])
def bulk_search():
    """Search news for multiple stocks at once"""
    data = request.json
    symbols = data.get('symbols', [])
    limit = data.get('limit', 10)
    
    if not symbols:
        return jsonify({'error': 'Symbols required'}), 400
    
    results = {}
    for symbol in symbols:
        results[symbol] = news_service.fetch_news(symbol, limit)
    
    return jsonify(results)
