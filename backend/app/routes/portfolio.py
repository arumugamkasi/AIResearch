from flask import Blueprint, jsonify, request
from app.services.portfolio_service import PortfolioService

bp = Blueprint('portfolio', __name__, url_prefix='/api/portfolio')
_svc = PortfolioService()


@bp.route('/seed', methods=['POST'])
def seed():
    seeded = _svc.seed()
    return jsonify({'seeded': seeded,
                    'message': 'Initial positions loaded.' if seeded else 'Already seeded.'})


@bp.route('/positions', methods=['GET'])
def get_positions():
    return jsonify(_svc.get_positions_by_portfolio())


@bp.route('/positions', methods=['POST'])
def upsert_position():
    data = request.get_json() or {}
    portfolio = data.get('portfolio', '').strip().upper()
    symbol    = data.get('symbol', '').strip().upper()
    quantity  = data.get('quantity')
    purchase_price = data.get('purchase_price')

    if not portfolio or not symbol or quantity is None:
        return jsonify({'error': 'portfolio, symbol, and quantity are required'}), 400
    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        return jsonify({'error': 'quantity must be a number'}), 400

    _svc.upsert_position(portfolio, symbol, quantity, purchase_price)
    return jsonify({'ok': True, 'portfolio': portfolio, 'symbol': symbol, 'quantity': quantity})


@bp.route('/positions/<portfolio>/<symbol>', methods=['DELETE'])
def delete_position(portfolio, symbol):
    _svc.delete_position(portfolio.upper(), symbol.upper())
    return jsonify({'ok': True})


@bp.route('/analysis', methods=['GET'])
def get_analysis():
    portfolios_param = request.args.get('portfolios', '').strip()
    selected = [p.strip().upper() for p in portfolios_param.split(',') if p.strip()] \
               if portfolios_param else None
    result = _svc.analyze_portfolio(selected_portfolios=selected)
    return jsonify(result)
