from flask import Blueprint, request, jsonify
from app.services.price_service import PriceService

bp = Blueprint('prices', __name__, url_prefix='/api/prices')

price_service = PriceService()

@bp.route('/<symbol>/current', methods=['GET'])
def get_current_price(symbol):
    """Get current stock price"""
    try:
        price_data = price_service.get_current_price(symbol)
        if price_data:
            return jsonify(price_data)
        return jsonify({'error': 'Price data not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<symbol>/historical', methods=['GET'])
def get_historical_data(symbol):
    """Get historical stock price data"""
    try:
        period = request.args.get('period', '1mo')
        interval = request.args.get('interval', '1d')

        historical_data = price_service.get_historical_data(symbol, period, interval)
        if historical_data:
            return jsonify(historical_data)
        return jsonify({'error': 'Historical data not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
