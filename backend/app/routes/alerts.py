from flask import Blueprint, request, jsonify
from app.models.alert_config_mongo import AlertConfigMongo

bp = Blueprint('alerts', __name__, url_prefix='/api/alerts')
_cfg = AlertConfigMongo()

# Will be set by __init__.py after monitor is started
_monitor = None

def set_monitor(monitor):
    global _monitor
    _monitor = monitor

@bp.route('/config', methods=['GET'])
def get_config():
    return jsonify(_cfg.get_config() or {'threshold_pct': 5, 'email_enabled': False, 'email_to': 'arumugamkasi@gmail.com'})

@bp.route('/config', methods=['POST'])
def save_config():
    data = request.json
    _cfg.save_config(
        threshold_pct=float(data.get('threshold_pct', 5)),
        email_enabled=bool(data.get('email_enabled', False)),
        email_to=data.get('email_to', 'arumugamkasi@gmail.com'),
    )
    return jsonify({'ok': True})

@bp.route('/active', methods=['GET'])
def get_active():
    if _monitor:
        return jsonify(_monitor.get_active_alerts())
    return jsonify([])
