"""
Sentiment History Service
Builds daily historical sentiment from existing ChromaDB news articles.
Uses fast keyword-based scoring (no Ollama needed) so it runs instantly.
Feeds into the backtest to improve prediction accuracy.
"""

from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Optional
from app.models.historical_sentiment_mongo import HistoricalSentimentMongo


# Financial sentiment keyword lists
BULLISH_WORDS = {
    'strong', 'beat', 'beats', 'surge', 'surges', 'record', 'record-high', 'breakthrough',
    'growth', 'grows', 'grew', 'profit', 'profits', 'gain', 'gains', 'rise', 'rises',
    'rose', 'rally', 'rallied', 'upgrade', 'upgrades', 'upgraded', 'outperform',
    'buy', 'recommend', 'positive', 'bullish', 'momentum', 'boosts', 'boost', 'boosted',
    'exceeds', 'exceeded', 'upside', 'revenue', 'expanded', 'expansion', 'winning',
    'opportunities', 'optimistic', 'confidence', 'confident', 'upbeat', 'robust',
    'solid', 'strong', 'accelerating', 'accelerate', 'ahead', 'leading', 'leader',
    'innovative', 'innovation', 'partnership', 'partnerships', 'acquisition',
    'dividend', 'dividends', 'buyback', 'buybacks', 'target', 'raised', 'raising',
    'increases', 'increased', 'new high', 'new highs', 'all-time high',
    'blockbuster', 'blowout', 'smashes', 'smashed', 'exceeds', 'impressive'
}

BEARISH_WORDS = {
    'weak', 'miss', 'misses', 'missed', 'drop', 'drops', 'dropped', 'fall', 'falls',
    'fell', 'decline', 'declines', 'declined', 'loss', 'losses', 'cut', 'cuts',
    'downgrade', 'downgrades', 'downgraded', 'underperform', 'sell', 'negative',
    'bearish', 'concern', 'concerns', 'risk', 'risks', 'warning', 'warns', 'warned',
    'weak', 'slowdown', 'contraction', 'disappointing', 'disappointed', 'disappoints',
    'shortfall', 'below', 'layoffs', 'layoff', 'restructuring', 'charges', 'write-off',
    'write-down', 'debt', 'default', 'lawsuit', 'investigation', 'fine', 'penalty',
    'recall', 'scandal', 'fraud', 'probe', 'subpoena', 'bankruptcy', 'liquidation',
    'struggles', 'struggling', 'headwinds', 'challenge', 'challenges', 'volatile',
    'uncertainty', 'uncertain', 'pressure', 'pressures', 'inflation', 'recession',
    'slowdown', 'losses', 'tumbles', 'tumbled', 'plunges', 'plunged', 'crash'
}


class SentimentHistoryService:
    """Builds and maintains historical sentiment from ChromaDB articles"""

    def __init__(self):
        self.sentiment_model = HistoricalSentimentMongo()

    def keyword_sentiment_score(self, text: str) -> float:
        """
        Fast keyword-based sentiment scorer.
        No Ollama / LLM needed — runs in milliseconds.

        Args:
            text: Article title + description

        Returns:
            Score from -1.0 (very bearish) to +1.0 (very bullish)
        """
        if not text:
            return 0.0

        words = text.lower().split()
        word_set = set(words)

        bull_count = len(word_set & BULLISH_WORDS)
        bear_count = len(word_set & BEARISH_WORDS)

        total = bull_count + bear_count
        if total == 0:
            return 0.0

        # Score: +1 = all bullish, -1 = all bearish
        score = (bull_count - bear_count) / total
        return round(score, 4)

    def build_daily_sentiment(self, symbol: str, articles: List[Dict]) -> int:
        """
        Score articles and aggregate into daily sentiment scores → MongoDB.
        Called every time news is analyzed, so sentiment builds up over time.

        Args:
            symbol: Stock ticker
            articles: List of article dicts with 'published_date', 'title', 'text'

        Returns:
            Number of days stored
        """
        if not articles:
            return 0

        # Group articles by date
        daily_groups: Dict[str, List[float]] = defaultdict(list)

        for article in articles:
            pub_date = article.get('published_date', '')
            if not pub_date:
                continue

            # Normalize to YYYY-MM-DD
            date_str = self._normalize_date(pub_date)
            if not date_str:
                continue

            # Score article
            text = f"{article.get('title', '')} {article.get('text', article.get('description', ''))}"
            score = self.keyword_sentiment_score(text)
            daily_groups[date_str].append(score)

        if not daily_groups:
            return 0

        # Aggregate and store each day
        stored = 0
        for date_str, scores in daily_groups.items():
            avg_score = sum(scores) / len(scores)

            positive_count = sum(1 for s in scores if s > 0.1)
            negative_count = sum(1 for s in scores if s < -0.1)
            neutral_count = len(scores) - positive_count - negative_count
            total = len(scores)

            if avg_score > 0.15:
                label = 'Bullish'
            elif avg_score < -0.15:
                label = 'Bearish'
            else:
                label = 'Neutral'

            sentiment_data = {
                'sentiment_score': round(avg_score, 4),
                'sentiment_label': label,
                'articles_count': total,
                'relevance_score': 1.0,  # Our own news = fully relevant
                'positive_ratio': round(positive_count / total, 3) if total else 0,
                'negative_ratio': round(negative_count / total, 3) if total else 0,
                'neutral_ratio': round(neutral_count / total, 3) if total else 0,
                'source': 'local_news'
            }

            if self.sentiment_model.insert_sentiment(symbol, date_str, sentiment_data):
                stored += 1

        return stored

    def backfill_from_chromadb(self, symbol: str, vector_store) -> int:
        """
        Process all existing ChromaDB articles for a symbol and populate
        MongoDB with daily sentiment scores.
        Call this once per stock to get immediate historical data.

        Args:
            symbol: Stock ticker
            vector_store: VectorStoreService instance

        Returns:
            Number of days backfilled
        """
        # Check if already backfilled
        existing = self.sentiment_model.get_sentiment_count(symbol)
        if existing > 10:
            return existing  # Already have enough data

        # Get all stored articles
        articles = vector_store.get_all_articles(symbol, limit=500)
        if not articles:
            return 0

        print(f"  📅 Backfilling sentiment from {len(articles)} ChromaDB articles for {symbol}...")
        stored = self.build_daily_sentiment(symbol, articles)
        print(f"  ✅ Backfilled {stored} days of sentiment for {symbol}")
        return stored

    def get_coverage(self, symbol: str) -> Dict:
        """
        Get sentiment coverage info for a symbol

        Args:
            symbol: Stock ticker

        Returns:
            Dict with coverage stats
        """
        info = self.sentiment_model.get_date_range(symbol)
        return {
            'symbol': symbol,
            'days_available': info['count'],
            'earliest': info['earliest'],
            'latest': info['latest']
        }

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """
        Normalize date string to YYYY-MM-DD format

        Args:
            date_str: Date in various formats

        Returns:
            Normalized date string or None if parsing fails
        """
        if not date_str:
            return None

        # Try common formats
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S+00:00',
            '%a, %d %b %Y %H:%M:%S %z',
            '%a, %d %b %Y %H:%M:%S GMT',
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str[:len(fmt)].strip(), fmt.strip())
                return dt.strftime('%Y-%m-%d')
            except:
                continue

        # Last resort: try to extract YYYY-MM-DD
        import re
        match = re.search(r'(\d{4}-\d{2}-\d{2})', date_str)
        if match:
            return match.group(1)

        return None
