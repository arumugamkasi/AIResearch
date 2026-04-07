import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
from app.services.price_service import PriceService
from app.services.analysis_service import AnalysisService
from app.services.vector_store_service import VectorStoreService
from app.services.price_cache_service_mongo import PriceCacheServiceMongo
from app.services.alpha_vantage_service import AlphaVantageService

# Try to import PyTorch LSTM model
try:
    from app.models.lstm_model_pytorch import LSTMStockPredictor, LSTMEnsemble, PYTORCH_AVAILABLE
    LSTM_AVAILABLE = PYTORCH_AVAILABLE
except Exception as e:
    print(f"⚠️  Could not import PyTorch LSTM model: {e}")
    LSTM_AVAILABLE = False
    LSTMStockPredictor = None
    LSTMEnsemble = None

# Try to import GBM 1w model
try:
    from app.models.gbm_1w_model import GBM1WeekPredictor
    GBM_AVAILABLE = True
except Exception as e:
    print(f"⚠️  Could not import GBM 1w model: {e}")
    GBM_AVAILABLE = False
    GBM1WeekPredictor = None

class PredictionService:
    """Service for predicting stock direction using backtested sentiment and technical indicators"""

    def __init__(self):
        self.price_service = PriceService()
        self.analysis_service = AnalysisService()
        self.vector_store = VectorStoreService()
        self.price_cache = PriceCacheServiceMongo()  # MongoDB cached price data
        self.alpha_vantage = AlphaVantageService()  # Historical sentiment data

        # LSTM model (PyTorch)
        self.use_lstm = LSTM_AVAILABLE
        self.lstm_predictor = None
        self.lstm_ensemble = LSTMEnsemble() if (LSTM_AVAILABLE and LSTMEnsemble is not None) else None

        # LSTM model cache: {symbol: {'predictor': LSTMStockPredictor, 'trained_at': date, 'history': ...}}
        self._lstm_cache: dict = {}

        if self.use_lstm:
            print("✅ LSTM predictions enabled (PyTorch)")
        else:
            print("⚠️  LSTM predictions disabled (PyTorch not installed)")
            print("   Install with: pip install torch")

        # GBM 1w model (scikit-learn)
        self.use_gbm = GBM_AVAILABLE
        self.gbm_predictor = None

        # GBM model cache: {symbol: {'predictor': GBM1WeekPredictor, 'trained_at': date, 'stats': ...}}
        self._gbm_cache: dict = {}

        if self.use_gbm:
            print("✅ GBM 1w predictions enabled (scikit-learn)")
        else:
            print("⚠️  GBM 1w predictions disabled")

        # Optimized parameters (can be tuned via backtesting)
        self.params = {
            'sentiment_multiplier': 0.8,   # reduced: LSTM handles sentiment patterns
            'momentum_weights': {
                'short_term': {'7d': 0.4, '14d': 0.15, '30d': 0.0},
                'medium_term': {'7d': 0.2, '14d': 0.2, '30d': 0.15},
                'long_term': {'7d': 0.1, '14d': 0.1, '30d': 0.15}
            },
            'volume_boost_factor': 0.05,  # reduced: avoid over-amplification
            'news_boost_max': 0.1,        # reduced from 0.3: max 10% news boost
            'decay_factors': {'7d': 0.3, '14d': 0.2, '30d': 0.15}
        }

    def predict_direction(self, symbol, sentiment_score=0.0, sentiment_breakdown=None):
        """
        Predict stock direction using backtested sentiment + momentum.

        Approach:
        1. Get cached historical data (1-2 years) - FAST!
        2. Backtest: calculate actual returns for each time horizon
        3. Build prediction model based on sentiment + momentum features
        4. Generate dynamic ranges based on historical volatility
        """
        try:
            # Get cached price data (much faster than API call)
            price_df = self.price_cache.get_prices(symbol, days=730)  # 2 years

            if price_df is None or len(price_df) < 30:
                # Fallback to regular price service if cache fails
                print(f"⚠️  Cache miss for {symbol}, using legacy price service")
                price_data = self.price_service.get_historical_data(symbol, period='1y')
                prices = price_data['data'] if price_data else None
                if not prices or len(prices) < 10:
                    return self._fallback_prediction(symbol, "Insufficient price history")
            else:
                # Convert DataFrame to legacy format for compatibility
                prices = price_df.to_dict('records')

            # Get historical sentiment data (if available)
            historical_sentiment_df = None
            if self.alpha_vantage.is_available():
                historical_sentiment_df = self.alpha_vantage.get_cached_sentiment(
                    symbol,
                    auto_fetch=True  # Auto-fetch if not cached
                )
                if historical_sentiment_df is not None:
                    print(f"✅ Using {len(historical_sentiment_df)} days of historical sentiment for backtest")

            # Extract sentiment and momentum features
            features = self._extract_features(
                symbol,
                prices,
                sentiment_score,
                sentiment_breakdown or {}
            )

            # Backtest to get realistic return distributions
            backtest_results = self._backtest_historical_returns(prices)

            # Evaluate backtest performance (how accurate the model would have been)
            # Now with historical sentiment!
            backtest_performance = self._evaluate_backtest_performance(
                prices,
                backtest_results,
                historical_sentiment_df
            )

            # Make predictions for different time horizons
            predictions = {}
            for horizon in ['1w', '1m', '3m', '6m', '1y']:
                predictions[horizon] = self._predict_horizon(
                    features,
                    horizon,
                    backtest_results
                )

            # GBM 1w Prediction (if available) - simpler, faster for 1w only
            gbm_1w_prediction = None
            if self.use_gbm and price_df is not None and len(price_df) >= 50:
                try:
                    # GBM uses 5-6 features, so fetch extended history for more training samples
                    # More data → better generalization (5 years = ~1260 trading days)
                    gbm_df = self.price_cache.get_prices(symbol, days=1825)  # 5 years
                    if gbm_df is None or len(gbm_df) < 100:
                        gbm_df = price_df  # fallback to 2-year data
                    print(f"🌲 Training GBM 1w model for {symbol} ({len(gbm_df)} days)...")

                    # Get sentiment data if available (for 6th feature)
                    # Try to get cached sentiment even if API is not available
                    sentiment_df = None
                    try:
                        # auto_fetch only works if API key is configured
                        # but we can still get cached data even without API key
                        auto_fetch = self.alpha_vantage.is_available()
                        sentiment_df = self.alpha_vantage.get_cached_sentiment(symbol, auto_fetch=auto_fetch)
                        if sentiment_df is not None and not sentiment_df.empty:
                            print(f"  📊 Using {len(sentiment_df)} days of cached sentiment for GBM training")
                        else:
                            print(f"  ⚠️  No cached sentiment data available for {symbol}")
                    except Exception as e:
                        print(f"  ⚠️  Failed to get sentiment data: {e}")

                    gbm_1w_prediction = self._get_1w_gbm_prediction(gbm_df, sentiment_df, symbol)

                    if gbm_1w_prediction:
                        print(f"✅ GBM 1w prediction generated for {symbol}")
                except Exception as e:
                    print(f"⚠️  GBM 1w prediction failed for {symbol}: {e}")
                    import traceback
                    traceback.print_exc()

            # LSTM Predictions (if available) - for 1m-1y horizons
            lstm_predictions = None
            ensemble_predictions = None
            model_name = 'Backtested: Sentiment + Momentum (v1.0)'

            if self.use_lstm and price_df is not None and len(price_df) >= 100:
                try:
                    # Fetch extended history for LSTM training (5 years = ~1260 trading days)
                    # More data → more training sequences → less overfitting
                    lstm_df = self.price_cache.get_prices(symbol, days=1825)  # ~5 years
                    if lstm_df is None or len(lstm_df) < 100:
                        lstm_df = price_df  # fallback to 2-year data
                    print(f"🤖 Training LSTM model for {symbol} ({len(lstm_df)} days)...")

                    lstm_predictions = self._get_lstm_predictions(lstm_df, {}, symbol)

                    if lstm_predictions:
                        # Ensemble LSTM + Heuristic predictions
                        ensemble_predictions = self.lstm_ensemble.combine_predictions(
                            lstm_predictions,
                            predictions
                        )
                        # Merge ensemble result into predictions for frontend display
                        for h, ep in ensemble_predictions.items():
                            if h in predictions:
                                ret = ep['predicted_return']
                                predictions[h]['expected_return'] = ret
                                predictions[h]['lstm_return'] = ep['lstm_return']
                                predictions[h]['heuristic_return'] = ep['heuristic_return']
                                predictions[h]['confidence'] = ep['confidence']
                                predictions[h]['direction'] = ep['direction']
                                predictions[h]['lstm_weight'] = ep['lstm_weight']
                        model_name = 'Ensemble: LSTM (PyTorch) + Sentiment + Momentum (v2.0)'
                        print(f"✅ LSTM predictions generated for {symbol}")
                except Exception as e:
                    print(f"⚠️  LSTM prediction failed for {symbol}: {e}")
                    import traceback
                    traceback.print_exc()

            # Use GBM for 1w if available (override LSTM/heuristic for 1w)
            if gbm_1w_prediction:
                # GBM provides: predicted_return, direction, confidence, prob_up, prob_down
                predictions['1w']['expected_return'] = gbm_1w_prediction['predicted_return']
                predictions['1w']['direction'] = gbm_1w_prediction['direction']
                predictions['1w']['confidence'] = gbm_1w_prediction['confidence']
                predictions['1w']['gbm_prob_up'] = gbm_1w_prediction['prob_up']
                predictions['1w']['gbm_prob_down'] = gbm_1w_prediction['prob_down']
                predictions['1w']['gbm_val_accuracy'] = gbm_1w_prediction.get('val_accuracy', 0)
                predictions['1w']['model'] = 'GBM (Gradient Boosting)'
                model_name = 'Hybrid: GBM (1w) + LSTM (1m-1y) + Sentiment + Momentum (v3.0)'

            response = {
                'symbol': symbol,
                'predictions': predictions,
                'features': features,
                'backtest_summary': self._summarize_backtest(backtest_results),
                'backtest_performance': backtest_performance,
                'model': model_name,
                'parameters': self.params,
                'generated_at': datetime.now().isoformat()
            }

            # Add GBM predictions if available
            if gbm_1w_prediction:
                response['gbm_1w_prediction'] = gbm_1w_prediction

            # Add LSTM predictions if available
            if lstm_predictions:
                response['lstm_predictions'] = lstm_predictions
                response['ensemble_predictions'] = ensemble_predictions

            # Build prediction methods description
            if gbm_1w_prediction or lstm_predictions:
                methods = {'heuristic': 'Sentiment + Momentum'}
                if gbm_1w_prediction:
                    methods['gbm_1w'] = 'Gradient Boosting for 1-week (5 features)'
                if lstm_predictions:
                    methods['lstm'] = 'Deep Learning Time Series (PyTorch)'
                    methods['ensemble'] = 'Weighted average (60% LSTM, 40% Heuristic)'
                response['prediction_methods'] = methods

            return response

        except Exception as e:
            print(f"Prediction error for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return self._fallback_prediction(symbol, str(e))

    def _backtest_historical_returns(self, prices):
        """
        Backtest historical returns to understand actual performance ranges.
        Returns statistics about past returns for different time horizons.
        """
        results = {
            '1w': [],
            '1m': [],
            '3m': [],
            '6m': [],
            '1y': []
        }

        # Map horizons to trading days (approximate)
        horizon_days = {
            '1w': 5,
            '1m': 21,
            '3m': 63,
            '6m': 126,
            '1y': 252
        }

        # Calculate returns for each available period
        for i in range(len(prices)):
            for horizon, days in horizon_days.items():
                if i + days < len(prices):
                    start_price = prices[i]['close']
                    end_price = prices[i + days]['close']
                    return_pct = ((end_price / start_price) - 1) * 100
                    results[horizon].append(return_pct)

        # Calculate statistics for each horizon
        stats = {}
        for horizon, returns in results.items():
            if returns:
                stats[horizon] = {
                    'mean': np.mean(returns),
                    'std': np.std(returns),
                    'median': np.median(returns),
                    'min': np.min(returns),
                    'max': np.max(returns),
                    'percentiles': {
                        'p10': np.percentile(returns, 10),
                        'p25': np.percentile(returns, 25),
                        'p75': np.percentile(returns, 75),
                        'p90': np.percentile(returns, 90)
                    },
                    'count': len(returns)
                }
            else:
                stats[horizon] = None

        return stats

    def _extract_features(self, symbol, prices, sentiment_score, sentiment_breakdown):
        """Extract predictive features from available data"""

        # Price momentum features
        recent_prices = [p['close'] for p in prices[-60:]] if len(prices) >= 60 else [p['close'] for p in prices]
        current_price = recent_prices[-1]

        # Calculate momentum: exact point-to-point period return
        # -8:-7 elements → price[T-7] to price[T] = true 7-day return (need N+1 points for N-day return)
        momentum_7d  = self._calculate_weighted_return(recent_prices[-8:])  if len(recent_prices) >= 8  else 0
        momentum_14d = self._calculate_weighted_return(recent_prices[-15:]) if len(recent_prices) >= 15 else 0
        momentum_30d = self._calculate_weighted_return(recent_prices[-31:]) if len(recent_prices) >= 31 else 0

        # Volume trend with exponential weighting (more weight to recent days)
        volumes = [p.get('volume', 0) for p in prices[-30:]]
        if volumes and len(volumes) >= 7:
            # Exponentially weighted recent volume (last 7 days)
            recent_vols = volumes[-7:]
            weights = np.array([np.exp(0.3 * i) for i in range(len(recent_vols))])
            weights = weights / weights.sum()
            recent_volume = np.average(recent_vols, weights=weights)
            avg_volume = np.mean(volumes)
            volume_trend = (recent_volume / avg_volume - 1) if avg_volume > 0 else 0
        else:
            volume_trend = 0

        # Volatility (price standard deviation)
        volatility = np.std(recent_prices) / np.mean(recent_prices) if len(recent_prices) > 1 else 0.02

        # News sentiment features
        sentiment_strength = abs(sentiment_score)
        sentiment_positive_ratio = sentiment_breakdown.get('positive', 0.33)
        sentiment_negative_ratio = sentiment_breakdown.get('negative', 0.33)

        # Get news count
        articles = self.vector_store.get_all_articles(symbol, limit=100)
        news_count = len(articles)

        # Recent news activity
        recent_news_count = 0
        cutoff_date = datetime.now() - timedelta(days=7)
        for article in articles:
            pub_date_str = article.get('published_date', '')
            try:
                pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                if pub_date > cutoff_date:
                    recent_news_count += 1
            except:
                pass

        return {
            'sentiment_score': sentiment_score,
            'sentiment_strength': sentiment_strength,
            'sentiment_positive_ratio': sentiment_positive_ratio,
            'sentiment_negative_ratio': sentiment_negative_ratio,
            'momentum_7d': momentum_7d,
            'momentum_14d': momentum_14d,
            'momentum_30d': momentum_30d,
            'volume_trend': volume_trend,
            'volatility': volatility,
            'news_count': news_count,
            'recent_news_count': recent_news_count,
            'current_price': current_price
        }

    def _calculate_return(self, prices):
        """Calculate percentage return from price series"""
        if len(prices) < 2:
            return 0
        return (prices[-1] / prices[0] - 1) * 100

    def _calculate_weighted_return(self, prices, decay=0.2):
        """
        Point-to-point percentage return over the window.
        e.g. prices[-7:] → (price[today] / price[7d_ago] - 1) * 100

        The `decay` parameter is kept for API compatibility but is no longer
        used — we use exact period returns, not exponential smoothing.
        """
        if len(prices) < 2:
            return 0
        start = prices[0]
        end = prices[-1]
        if start == 0:
            return 0
        return (end / start - 1) * 100

    def _predict_horizon(self, features, horizon, backtest_stats):
        """
        Predict using backtested model.
        Uses actual historical return distributions adjusted by current signals.
        """

        # Get backtested statistics for this horizon
        stats = backtest_stats.get(horizon)
        if not stats:
            return self._neutral_prediction(horizon)

        # Calculate expected return based on sentiment + momentum
        # Base expectation from historical median
        base_return = stats['median']

        # Adjust based on sentiment (stronger signal = more deviation from median)
        sentiment_adjustment = features['sentiment_score'] * stats['std'] * self.params['sentiment_multiplier']

        # Adjust based on momentum with stronger weight to recent periods
        if horizon in ['1w', '1m']:
            # Short-term: heavily weight recent 7d momentum
            weights = self.params['momentum_weights']['short_term']
            momentum_adjustment = (features['momentum_7d'] * weights['7d'] +
                                 features['momentum_14d'] * weights['14d'] +
                                 features['momentum_30d'] * weights['30d'])
        elif horizon == '3m':
            # Medium-term: blend recent and longer momentum
            weights = self.params['momentum_weights']['medium_term']
            momentum_adjustment = (features['momentum_7d'] * weights['7d'] +
                                 features['momentum_14d'] * weights['14d'] +
                                 features['momentum_30d'] * weights['30d'])
        else:
            # Long-term: still favor recent but include longer trends
            weights = self.params['momentum_weights']['long_term']
            momentum_adjustment = (features['momentum_7d'] * weights['7d'] +
                                 features['momentum_14d'] * weights['14d'] +
                                 features['momentum_30d'] * weights['30d'])

        # Volume and news boosts
        volume_boost = 1.0 + (features['volume_trend'] * self.params['volume_boost_factor'])
        news_boost = 1.0 + min(features['recent_news_count'] / 30, self.params['news_boost_max'])

        # Combined expected return
        expected_return = (
            base_return +
            sentiment_adjustment +
            momentum_adjustment
        ) * volume_boost * news_boost

        # Calculate uncertainty (wider for volatile stocks)
        uncertainty = stats['std'] * (1 + features['volatility'] * 2)

        # Create dynamic ranges based on percentiles and expected return
        ranges = self._create_dynamic_ranges(expected_return, uncertainty, stats)

        # Calculate probabilities for each range
        probabilities = self._calculate_probabilities(expected_return, uncertainty, ranges)

        # Determine most likely range
        likely_range = max(probabilities, key=probabilities.get)
        confidence = probabilities[likely_range]

        return {
            'horizon': horizon,
            'likely_range': likely_range,
            'expected_return': round(expected_return, 2),
            'confidence': round(confidence * 100, 1),
            'probabilities': {k: round(v * 100, 1) for k, v in probabilities.items()},
            'ranges': ranges,
            'explanation': self._generate_explanation(features, expected_return, horizon, stats)
        }

    def _create_dynamic_ranges(self, expected_return, uncertainty, stats):
        """
        Create dynamic percentage ranges based on historical data.
        Ranges adapt to the stock's actual volatility and return patterns.
        """

        # Use percentiles to create realistic ranges
        ranges = {}

        # For highly volatile stocks, use wider ranges
        # For stable stocks, use narrower ranges

        if stats['std'] > 10:  # High volatility
            ranges = {
                'strong_down': (stats['min'], stats['percentiles']['p10']),
                'down': (stats['percentiles']['p10'], stats['percentiles']['p25']),
                'slight_down': (stats['percentiles']['p25'], 0),
                'neutral': (0, stats['median']),
                'slight_up': (stats['median'], stats['percentiles']['p75']),
                'up': (stats['percentiles']['p75'], stats['percentiles']['p90']),
                'strong_up': (stats['percentiles']['p90'], stats['max'])
            }
        elif stats['std'] > 5:  # Medium volatility
            ranges = {
                'strong_down': (stats['min'], -stats['std'] * 1.5),
                'down': (-stats['std'] * 1.5, -stats['std'] * 0.5),
                'slight_down': (-stats['std'] * 0.5, 0),
                'neutral': (0, stats['std'] * 0.5),
                'slight_up': (stats['std'] * 0.5, stats['std'] * 1.5),
                'up': (stats['std'] * 1.5, stats['std'] * 2.5),
                'strong_up': (stats['std'] * 2.5, stats['max'])
            }
        else:  # Low volatility
            ranges = {
                'strong_down': (stats['min'], -5),
                'down': (-5, -2),
                'slight_down': (-2, 0),
                'neutral': (0, 2),
                'slight_up': (2, 5),
                'up': (5, 10),
                'strong_up': (10, stats['max'])
            }

        return ranges

    def _calculate_probabilities(self, expected_return, uncertainty, ranges):
        """
        Calculate probability for each range using normal distribution approximation.
        """
        probabilities = {}
        total = 0

        for range_name, (low, high) in ranges.items():
            # Calculate probability mass in this range
            # Using simplified normal distribution centered on expected_return
            mid = (low + high) / 2
            distance = abs(expected_return - mid)

            # Probability decreases with distance from expected return
            prob = max(0, 1 - (distance / (uncertainty * 2)))

            # Boost if expected return is within the range
            if low <= expected_return <= high:
                prob *= 2.0

            probabilities[range_name] = prob
            total += prob

        # Normalize
        if total > 0:
            probabilities = {k: v/total for k, v in probabilities.items()}
        else:
            # Fallback to neutral distribution
            probabilities = {k: 1.0/len(ranges) for k in ranges}

        return probabilities

    def _generate_explanation(self, features, expected_return, horizon, stats):
        """Generate human-readable explanation"""

        parts = []

        # Sentiment
        if features['sentiment_score'] > 0.3:
            parts.append("strong positive sentiment")
        elif features['sentiment_score'] > 0.1:
            parts.append("positive sentiment")
        elif features['sentiment_score'] < -0.3:
            parts.append("strong negative sentiment")
        elif features['sentiment_score'] < -0.1:
            parts.append("negative sentiment")

        # Momentum
        if horizon in ['1w', '1m']:
            momentum = features['momentum_7d']
        else:
            momentum = features['momentum_30d']

        if momentum > 5:
            parts.append("strong upward momentum")
        elif momentum > 2:
            parts.append("positive momentum")
        elif momentum < -5:
            parts.append("strong downward momentum")
        elif momentum < -2:
            parts.append("negative momentum")

        # Historical context
        if stats:
            parts.append(f"historical avg: {stats['median']:.1f}%")

        if parts:
            return f"Based on {', '.join(parts[:4])}"
        return f"Expected: {expected_return:+.1f}%"

    def _neutral_prediction(self, horizon):
        """Return neutral prediction when backtest data unavailable"""
        return {
            'horizon': horizon,
            'likely_range': 'neutral',
            'expected_return': 0.0,
            'confidence': 50.0,
            'probabilities': {
                'strong_down': 10.0,
                'down': 15.0,
                'slight_down': 15.0,
                'neutral': 20.0,
                'slight_up': 15.0,
                'up': 15.0,
                'strong_up': 10.0
            },
            'ranges': {
                'strong_down': (-999999, -10),
                'down': (-10, -5),
                'slight_down': (-5, 0),
                'neutral': (0, 5),
                'slight_up': (5, 10),
                'up': (10, 20),
                'strong_up': (20, 999999)
            },
            'explanation': 'Limited historical data available'
        }

    def _summarize_backtest(self, backtest_results):
        """Create summary of backtest results"""
        summary = {}
        for horizon, stats in backtest_results.items():
            if stats:
                summary[horizon] = {
                    'avg_return': round(stats['mean'], 2),
                    'volatility': round(stats['std'], 2),
                    'best': round(stats['max'], 2),
                    'worst': round(stats['min'], 2),
                    'samples': stats['count']
                }
        return summary

    def _fallback_prediction(self, symbol, error):
        """Return neutral prediction when analysis fails"""
        neutral_pred = self._neutral_prediction('1m')

        return {
            'symbol': symbol,
            'predictions': {
                '1w': {**self._neutral_prediction('1w')},
                '1m': {**neutral_pred},
                '3m': {**self._neutral_prediction('3m')},
                '6m': {**self._neutral_prediction('6m')},
                '1y': {**self._neutral_prediction('1y')}
            },
            'features': {},
            'backtest_summary': {},
            'backtest_performance': {},
            'model': 'Fallback (neutral)',
            'error': error,
            'generated_at': datetime.now().isoformat()
        }

    def _evaluate_backtest_performance(self, prices, backtest_results, historical_sentiment_df=None):
        """
        Evaluate how accurate the model would have been on historical data.
        Simulates making predictions at each historical point and measuring accuracy.
        NOW WITH HISTORICAL SENTIMENT DATA!
        """
        performance = {}
        horizon_days = {'1w': 5, '1m': 21, '3m': 63, '6m': 126, '1y': 252}

        # Convert sentiment to dict for fast lookup by date
        sentiment_by_date = {}
        if historical_sentiment_df is not None and not historical_sentiment_df.empty:
            sentiment_by_date = historical_sentiment_df.set_index('date')['sentiment_score'].to_dict()
            print(f"   📊 Backtesting with {len(sentiment_by_date)} days of historical sentiment")

        for horizon, days in horizon_days.items():
            if not backtest_results.get(horizon):
                continue

            errors = []
            directional_correct = 0
            total_predictions = 0

            # Simulate predictions at historical points
            for i in range(len(prices) - days - 30):  # Leave some buffer
                try:
                    # Get historical prices up to this point
                    hist_prices = prices[:i+30]
                    future_prices = prices[i+30:i+30+days]

                    if len(future_prices) < days:
                        continue

                    # Calculate actual return
                    actual_return = ((future_prices[-1]['close'] / hist_prices[-1]['close']) - 1) * 100

                    # Extract features at this historical point
                    recent = [p['close'] for p in hist_prices[-60:]] if len(hist_prices) >= 60 else [p['close'] for p in hist_prices]

                    if len(recent) < 7:
                        continue

                    momentum_7d  = self._calculate_weighted_return(recent[-8:])  if len(recent) >= 8  else 0
                    momentum_14d = self._calculate_weighted_return(recent[-15:]) if len(recent) >= 15 else 0
                    momentum_30d = self._calculate_weighted_return(recent[-31:]) if len(recent) >= 31 else 0

                    # Get historical sentiment for this date (if available)
                    prediction_date = hist_prices[-1].get('date', '')
                    historical_sentiment = sentiment_by_date.get(prediction_date, 0.0)

                    # Build prediction with sentiment + momentum (if sentiment available)
                    stats = backtest_results[horizon]
                    base_return = stats['median']

                    # Sentiment adjustment
                    sentiment_adjustment = historical_sentiment * stats['std'] * self.params['sentiment_multiplier']

                    # Momentum adjustment
                    if horizon in ['1w', '1m']:
                        weights = self.params['momentum_weights']['short_term']
                    elif horizon == '3m':
                        weights = self.params['momentum_weights']['medium_term']
                    else:
                        weights = self.params['momentum_weights']['long_term']

                    momentum_adjustment = (momentum_7d * weights['7d'] +
                                         momentum_14d * weights['14d'] +
                                         momentum_30d * weights['30d'])

                    # Combined prediction (NOW WITH SENTIMENT!)
                    predicted_return = base_return + sentiment_adjustment + momentum_adjustment

                    # Calculate error
                    error = abs(predicted_return - actual_return)
                    errors.append(error)

                    # Check directional accuracy
                    if (predicted_return > 0 and actual_return > 0) or (predicted_return < 0 and actual_return < 0):
                        directional_correct += 1
                    total_predictions += 1

                except Exception as e:
                    continue

            if errors and total_predictions > 0:
                performance[horizon] = {
                    'mae': round(np.mean(errors), 2),  # Mean Absolute Error
                    'rmse': round(np.sqrt(np.mean([e**2 for e in errors])), 2),  # Root Mean Squared Error
                    'directional_accuracy': round((directional_correct / total_predictions) * 100, 1),
                    'total_predictions': total_predictions
                }
            else:
                performance[horizon] = {
                    'mae': None,
                    'rmse': None,
                    'directional_accuracy': None,
                    'total_predictions': 0
                }

        return performance

    def _get_lstm_predictions(self, df: pd.DataFrame, technical_features: dict, symbol: str) -> dict:
        """
        Generate predictions using LSTM model (PyTorch)

        Args:
            df: Price DataFrame with OHLCV data
            technical_features: Dict of technical indicators
            symbol: Stock symbol

        Returns:
            Dict of LSTM predictions by horizon
        """
        try:
            # Check if LSTM is available
            if LSTMStockPredictor is None:
                return None

            today = datetime.now().date()
            cached = self._lstm_cache.get(symbol)

            if cached and cached['trained_at'] == today and cached['predictor'] is not None:
                # Use cached model — just run prediction, no retraining
                print(f"  ⚡ Using cached LSTM model for {symbol} (trained today)")
                self.lstm_predictor = cached['predictor']
                training_history = cached['history']
            else:
                # Train fresh model
                self.lstm_predictor = LSTMStockPredictor(lookback_days=60)
                print(f"  📊 Training LSTM on {len(df)} days of data...")
                training_history = self.lstm_predictor.train(
                    df,
                    technical_features,
                    epochs=50,
                    batch_size=32,
                    validation_split=0.2
                )
                val_acc = training_history.get('val_directional_accuracy', {})
                acc_str = ' | '.join(f"{h}:{v}%" for h, v in val_acc.items())
                print(f"  ✅ Training complete - Loss: {training_history['loss']:.4f}, "
                      f"Val Loss: {training_history['val_loss']:.4f}, "
                      f"Val Dir Acc: [{acc_str}], Epochs: {training_history['epochs_trained']}")
                # Cache for today
                self._lstm_cache[symbol] = {
                    'predictor': self.lstm_predictor,
                    'trained_at': today,
                    'history': training_history
                }

            # Make predictions with most recent data (always use latest df)
            lstm_preds = self.lstm_predictor.predict(
                df,
                technical_features,
                horizons=['1w', '1m', '3m', '6m', '1y']
            )

            # Attach val accuracy to each prediction for the response
            val_acc = training_history.get('val_directional_accuracy', {})
            for h, preds in lstm_preds.items():
                preds['val_directional_accuracy'] = val_acc.get(h)

            return lstm_preds

        except Exception as e:
            print(f"  ❌ LSTM prediction error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_1w_gbm_prediction(self, df: pd.DataFrame, sentiment_df: pd.DataFrame, symbol: str) -> dict:
        """
        Generate 1-week prediction using lightweight GBM model

        Args:
            df: Price DataFrame with OHLCV data
            sentiment_df: Optional sentiment DataFrame with columns ['date', 'sentiment_score']
            symbol: Stock symbol

        Returns:
            Dict with GBM prediction for 1w horizon
        """
        try:
            # Check if GBM is available
            if GBM1WeekPredictor is None:
                return None

            today = datetime.now().date()
            cached = self._gbm_cache.get(symbol)

            # Include sentiment availability in cache key (retrain if sentiment becomes available)
            has_sentiment = sentiment_df is not None and not sentiment_df.empty
            cache_key = f"{symbol}_{has_sentiment}"

            if cached and cached['trained_at'] == today and cached.get('has_sentiment') == has_sentiment:
                # Use cached model
                print(f"  ⚡ Using cached GBM 1w model for {symbol} (trained today)")
                self.gbm_predictor = cached['predictor']
                training_stats = cached['stats']
            else:
                # Train fresh GBM model with sentiment if available
                self.gbm_predictor = GBM1WeekPredictor(use_sentiment=has_sentiment)
                print(f"  🌲 Training GBM 1w model for {symbol} ({len(df)} days, sentiment={has_sentiment})...")
                training_stats = self.gbm_predictor.train(df, sentiment_df, n_estimators=100)

                print(f"  ✅ GBM training complete - Train Acc: {training_stats['train_accuracy']}%, "
                      f"Val Acc: {training_stats['val_accuracy']}%, "
                      f"Samples: {training_stats['train_samples']}/{training_stats['val_samples']}")

                # Cache for today
                self._gbm_cache[symbol] = {
                    'predictor': self.gbm_predictor,
                    'trained_at': today,
                    'stats': training_stats,
                    'has_sentiment': has_sentiment
                }

            # Make prediction with sentiment data
            gbm_pred = self.gbm_predictor.predict(df, sentiment_df)

            # Attach training stats for transparency
            gbm_pred['train_accuracy'] = training_stats['train_accuracy']
            gbm_pred['val_accuracy'] = training_stats['val_accuracy']
            gbm_pred['feature_importances'] = training_stats['feature_importances']

            return gbm_pred

        except Exception as e:
            print(f"  ❌ GBM prediction error: {e}")
            import traceback
            traceback.print_exc()
            return None
