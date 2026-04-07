from flask import Flask
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    CORS(app)

    # Register blueprints
    from app.routes import stocks, news, analysis, favorites, prices, auth, predictions, fundamentals, portfolio
    from app.routes import alerts as alerts_bp
    from app.routes.alerts import set_monitor
    app.register_blueprint(auth.bp)
    app.register_blueprint(stocks.bp)
    app.register_blueprint(news.bp)
    app.register_blueprint(analysis.bp)
    app.register_blueprint(favorites.bp)
    app.register_blueprint(prices.bp)
    app.register_blueprint(predictions.bp)
    app.register_blueprint(fundamentals.bp)
    app.register_blueprint(portfolio.bp)
    app.register_blueprint(alerts_bp.bp)

    # Start portfolio alert monitor background thread
    from app.services.alert_monitor import AlertMonitor
    from app.models.alert_config_mongo import AlertConfigMongo
    from app.models.portfolio_mongo import PortfolioMongo

    monitor = AlertMonitor(db=PortfolioMongo(), config=AlertConfigMongo())
    monitor.start()
    set_monitor(monitor)

    return app
