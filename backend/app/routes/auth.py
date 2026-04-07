from flask import Blueprint, request, jsonify
import hashlib
import secrets

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Simple in-memory user store (in production, use a database)
USERS = {
    'admin': {
        'password_hash': hashlib.sha256('admin123'.encode()).hexdigest(),
        'name': 'Admin User'
    },
    'demo': {
        'password_hash': hashlib.sha256('demo123'.encode()).hexdigest(),
        'name': 'Demo User'
    }
}

@bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return token"""
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({
            'success': False,
            'message': 'Username and password required'
        }), 400

    user = USERS.get(username)
    if not user:
        return jsonify({
            'success': False,
            'message': 'Invalid username or password'
        }), 401

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if password_hash != user['password_hash']:
        return jsonify({
            'success': False,
            'message': 'Invalid username or password'
        }), 401

    # Generate a simple token (in production, use JWT)
    token = secrets.token_urlsafe(32)

    return jsonify({
        'success': True,
        'token': token,
        'username': username,
        'name': user['name']
    })

@bp.route('/logout', methods=['POST'])
def logout():
    """Logout user (client-side handles token removal)"""
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    })
