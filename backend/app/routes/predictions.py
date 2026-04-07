from flask import Blueprint, request, jsonify
from app.services.prediction_service import PredictionService
from app.services.analysis_service import AnalysisService
from app.services.vector_store_service import VectorStoreService
from app.services.sentiment_history_service import SentimentHistoryService

bp = Blueprint('predictions', __name__, url_prefix='/api/predictions')

prediction_service = PredictionService()
analysis_service = AnalysisService()
vector_store = VectorStoreService()
sentiment_history = SentimentHistoryService()

@bp.route('/<symbol>', methods=['GET'])
def get_predictions(symbol):
    """Get stock direction predictions for multiple time horizons"""
    try:
        # Get sentiment data if available
        sentiment_score = request.args.get('sentiment_score', type=float, default=0.0)

        # Try to get sentiment breakdown from recent analysis
        sentiment_breakdown = None
        try:
            # Get all stored articles from ChromaDB
            articles = vector_store.get_all_articles(symbol, limit=200)
            if articles:
                # Build historical daily sentiment from all stored articles (fast, keyword-based)
                # First call backfills all existing articles; subsequent calls add new ones
                sentiment_history.backfill_from_chromadb(symbol, vector_store)
                sentiment_history.build_daily_sentiment(symbol, articles)

                # Use fast keyword-based sentiment for current score unless Ollama explicitly requested
                use_ollama = request.args.get('use_ollama', 'false').lower() == 'true'
                if use_ollama:
                    # Slower but more accurate (Ollama LLM analysis)
                    sentiment_data = analysis_service.analyze_sentiment(articles[:10])
                    sentiment_breakdown = sentiment_data.get('overall_sentiment', {})
                    if not sentiment_score:
                        sentiment_score = sentiment_data.get('sentiment_score', 0.0)
                elif not sentiment_score:
                    # Fast keyword-based sentiment (instant)
                    scores = [sentiment_history.keyword_sentiment_score(
                        (a.get('title', '') + ' ' + a.get('content', ''))[:500]
                    ) for a in articles[:20]]
                    if scores:
                        sentiment_score = float(sum(scores) / len(scores))
        except:
            pass

        # Generate predictions (backtest now uses accumulated historical sentiment)
        predictions = prediction_service.predict_direction(
            symbol,
            sentiment_score=sentiment_score,
            sentiment_breakdown=sentiment_breakdown
        )

        return jsonify(predictions)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
