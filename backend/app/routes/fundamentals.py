from flask import Blueprint, jsonify
from app.services.fundamentals_service import FundamentalsService

bp = Blueprint('fundamentals', __name__)
_svc = FundamentalsService()


@bp.route('/api/fundamentals/<symbol>', methods=['GET'])
def get_fundamentals(symbol):
    data = _svc.get_fundamentals(symbol.upper())
    return jsonify(data)
