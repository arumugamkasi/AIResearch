from flask import Blueprint, request, jsonify
from app.services.analysis_service import AnalysisService

bp = Blueprint('analysis', __name__, url_prefix='/api/analysis')

analysis_service = AnalysisService()

@bp.route('/summarize', methods=['POST'])
def summarize_news():
    """Summarize news articles for investment decision"""
    data = request.json
    articles = data.get('articles', [])
    symbol = data.get('symbol')
    
    if not articles:
        return jsonify({'error': 'Articles required'}), 400
    
    summary = analysis_service.summarize_articles(articles, symbol)
    return jsonify(summary)

@bp.route('/sentiment', methods=['POST'])
def analyze_sentiment():
    """Analyze sentiment of articles"""
    data = request.json
    articles = data.get('articles', [])
    
    if not articles:
        return jsonify({'error': 'Articles required'}), 400
    
    sentiment = analysis_service.analyze_sentiment(articles)
    return jsonify(sentiment)

@bp.route('/recommendation', methods=['POST'])
def get_recommendation():
    """Get investment recommendation based on RAG analysis"""
    data = request.json
    symbol = data.get('symbol')
    articles = data.get('articles', [])
    current_position = data.get('current_position', 'none')

    if not symbol:
        return jsonify({'error': 'Symbol required'}), 400

    try:
        recommendation = analysis_service.get_recommendation(
            symbol, articles, current_position
        )
        return jsonify(recommendation)
    except Exception as e:
        return jsonify({
            'symbol': symbol,
            'recommendation': 'HOLD',
            'confidence': 0.0,
            'sentiment_score': 0.0,
            'sentiment_breakdown': {'positive': 0.33, 'neutral': 0.34, 'negative': 0.33},
            'summary': f'Analysis error: {str(e)}',
            'key_points': ['An error occurred during analysis'],
            'reasoning': str(e),
            'critical_events': [],
            'revenue_outlook': {'direction': 'UNCERTAIN', 'summary': 'Unavailable.', 'factors': []}
        }), 200
