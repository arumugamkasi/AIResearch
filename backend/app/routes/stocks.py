from flask import Blueprint, request, jsonify
from app.services.stock_service import StockService

bp = Blueprint('stocks', __name__, url_prefix='/api/stocks')

stock_service = StockService()

@bp.route('', methods=['GET'])
def get_stocks():
    """Get list of tracked stocks"""
    stocks = stock_service.get_all_stocks()
    return jsonify(stocks)

@bp.route('/<symbol>', methods=['GET'])
def get_stock(symbol):
    """Get details for a specific stock"""
    stock = stock_service.get_stock_by_symbol(symbol)
    if stock:
        return jsonify(stock)
    return jsonify({'error': 'Stock not found'}), 404

@bp.route('', methods=['POST'])
def add_stock():
    """Add a new stock to track"""
    data = request.json
    symbol = data.get('symbol')
    name = data.get('name')
    
    if not symbol:
        return jsonify({'error': 'Symbol required'}), 400
    
    stock = stock_service.add_stock(symbol, name)
    return jsonify(stock), 201

@bp.route('/<symbol>', methods=['DELETE'])
def delete_stock(symbol):
    """Remove a stock from tracking"""
    success = stock_service.delete_stock(symbol)
    if success:
        return jsonify({'message': 'Stock removed'}), 200
    return jsonify({'error': 'Stock not found'}), 404
