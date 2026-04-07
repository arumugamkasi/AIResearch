from flask import Blueprint, request, jsonify
from app.services.news_service import NewsService

bp = Blueprint('news', __name__, url_prefix='/api/news')

news_service = NewsService()

@bp.route('/search', methods=['GET'])
def search_news():
    """
    Search financial news for a stock from multiple sources with FinBERT sentiment

    This endpoint now uses multi-source aggregation (Finnhub + DuckDuckGo)
    with FinBERT sentiment analysis by default for better results.
    """
    symbol = request.args.get('symbol')
    limit = request.args.get('limit', 50, type=int)  # Default to 50 for better coverage

    if not symbol:
        return jsonify({'error': 'Symbol required'}), 400

    # Use multi-source fetch with FinBERT sentiment by default
    news = news_service.fetch_news_multi_source(
        symbol,
        limit=limit,
        use_finbert=True,
        credibility_threshold=0.0
    )

    # Calculate aggregate sentiment for frontend
    sentiment_summary = None
    if news and any('finbert_sentiment' in article for article in news):
        sentiment_summary = news_service.finbert.aggregate_sentiment(news)

    return jsonify({
        'symbol': symbol,
        'articles': news,
        'article_count': len(news),
        'sentiment_summary': sentiment_summary
    })

@bp.route('/search-multi-source', methods=['GET'])
def search_news_multi_source():
    """
    Search financial news from multiple sources with FinBERT sentiment analysis

    Query params:
        symbol: Stock symbol (required)
        limit: Max articles to return (default: 50)
        use_finbert: Whether to run FinBERT sentiment (default: true)
        credibility_threshold: Minimum credibility score 0-1 (default: 0.0)
    """
    symbol = request.args.get('symbol')
    limit = request.args.get('limit', 50, type=int)
    use_finbert = request.args.get('use_finbert', 'true').lower() == 'true'
    credibility_threshold = request.args.get('credibility_threshold', 0.0, type=float)

    if not symbol:
        return jsonify({'error': 'Symbol required'}), 400

    # Validate credibility threshold
    if not 0.0 <= credibility_threshold <= 1.0:
        return jsonify({'error': 'credibility_threshold must be between 0.0 and 1.0'}), 400

    news = news_service.fetch_news_multi_source(
        symbol,
        limit=limit,
        use_finbert=use_finbert,
        credibility_threshold=credibility_threshold
    )

    # Calculate aggregate sentiment if FinBERT was used
    sentiment_summary = None
    if use_finbert and news and any('finbert_sentiment' in article for article in news):
        from app.services.finbert_sentiment import FinBERTSentimentAnalyzer
        analyzer = FinBERTSentimentAnalyzer()
        sentiment_summary = analyzer.aggregate_sentiment(news)

    return jsonify({
        'symbol': symbol,
        'article_count': len(news),
        'articles': news,
        'sentiment_summary': sentiment_summary
    })

@bp.route('/trending', methods=['GET'])
def get_trending():
    """Get trending financial news"""
    limit = request.args.get('limit', 20, type=int)
    news = news_service.get_trending_news(limit)
    return jsonify({'articles': news})

@bp.route('/bulk-search', methods=['POST'])
def bulk_search():
    """
    Search news for multiple stocks at once using multi-source aggregation

    Now uses Finnhub + DuckDuckGo with FinBERT sentiment for all stocks.
    """
    data = request.json
    symbols = data.get('symbols', [])
    limit = data.get('limit', 50)

    if not symbols:
        return jsonify({'error': 'Symbols required'}), 400

    results = {}
    for symbol in symbols:
        articles = news_service.fetch_news_multi_source(
            symbol,
            limit=limit,
            use_finbert=True,
            credibility_threshold=0.0
        )

        # Add sentiment summary for each stock
        sentiment_summary = None
        if articles and any('finbert_sentiment' in article for article in articles):
            sentiment_summary = news_service.finbert.aggregate_sentiment(articles)

        results[symbol] = {
            'articles': articles,
            'article_count': len(articles),
            'sentiment_summary': sentiment_summary
        }

    return jsonify(results)
