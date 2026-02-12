from flask import Flask
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Register blueprints
    from app.routes import stocks, news, analysis
    app.register_blueprint(stocks.bp)
    app.register_blueprint(news.bp)
    app.register_blueprint(analysis.bp)
    
    return app
