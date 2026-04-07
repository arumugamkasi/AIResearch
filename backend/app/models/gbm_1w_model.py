"""
Gradient Boosting Model for 1-Week Predictions
Simple, fast model optimized for short-term directional accuracy.
Uses only the most predictive technical features.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from typing import Dict, Optional


class GBM1WeekPredictor:
    """Lightweight gradient boosting model for 1-week direction prediction"""

    def __init__(self, use_sentiment=True):
        self.model = None
        self.scaler = StandardScaler()
        self.use_sentiment = use_sentiment

        # Top features for 1w prediction
        self.feature_names = [
            'momentum_7d',   # Recent momentum
            'rsi',           # Overbought/oversold
            'volatility',    # Recent volatility
            'volume_trend',  # Volume momentum
            'bb_position'    # Bollinger band position
        ]

        # Add sentiment if enabled
        if self.use_sentiment:
            self.feature_names.append('sentiment_1w_avg')  # 1-week avg sentiment

    def _compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute the 5 key features from OHLCV data"""
        features_df = pd.DataFrame(index=df.index)
        close = df['close']
        volume = df['volume']

        # 1. Momentum 7d (simple point-to-point return)
        features_df['momentum_7d'] = close.pct_change(7) * 100

        # 2. RSI (14-period)
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        features_df['rsi'] = (100 - 100 / (1 + rs)).fillna(50)

        # 3. Volatility (10-day rolling std of returns)
        features_df['volatility'] = close.pct_change(1).rolling(10).std() * 100

        # 4. Volume trend (volume vs 20-day average)
        vol_ma = volume.rolling(20).mean().replace(0, np.nan)
        features_df['volume_trend'] = (volume / vol_ma).fillna(1.0)

        # 5. Bollinger Band position
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        upper = sma20 + 2 * std20
        lower = sma20 - 2 * std20
        band_range = (upper - lower).replace(0, np.nan)
        features_df['bb_position'] = ((close - lower) / band_range).fillna(0.5).clip(0, 1)

        return features_df.ffill().fillna(0)

    def train(self, df: pd.DataFrame, sentiment_df: Optional[pd.DataFrame] = None,
              n_estimators: int = 100, use_sentiment_windows: bool = True) -> Dict:
        """
        Train the gradient boosting classifier

        Args:
            df: DataFrame with OHLCV data (must have 'close', 'volume')
            sentiment_df: Optional DataFrame with columns ['date', 'sentiment_score']
            n_estimators: Number of boosting iterations

        Returns:
            Training statistics dict
        """
        # Compute features
        features_df = self._compute_features(df)

        # Add sentiment feature if available
        if self.use_sentiment and sentiment_df is not None and not sentiment_df.empty:
            # Merge sentiment data by date
            # Calculate 1-week rolling average sentiment
            sentiment_df = sentiment_df.copy()
            sentiment_df['sentiment_1w_avg'] = sentiment_df['sentiment_score'].rolling(7, min_periods=1).mean()

            # Prepare price DataFrame with date column
            if 'date' in df.columns:
                df_dates = pd.to_datetime(df['date'])
            else:
                # Date is in the index
                df_dates = pd.to_datetime(df.index)

            # Convert to date objects (no time component)
            df_dates_only = pd.Series(df_dates.dt.date, index=df.index)

            # Ensure sentiment dates are also date objects
            sentiment_df['date'] = pd.to_datetime(sentiment_df['date']).dt.date

            # DEBUG: Print date ranges
            print(f"  🔍 Price data: {df_dates_only.min()} to {df_dates_only.max()} ({len(df_dates_only)} days)")
            print(f"  🔍 Sentiment data: {sentiment_df['date'].min()} to {sentiment_df['date'].max()} ({len(sentiment_df)} days)")

            # Create a mapping dict for fast lookup
            sentiment_dict = sentiment_df.set_index('date')['sentiment_1w_avg'].to_dict()

            # Map sentiment to price DataFrame dates
            features_df['sentiment_1w_avg'] = df_dates_only.map(sentiment_dict).fillna(0).values

            # Count how many non-zero sentiment values we have
            sentiment_count = (features_df['sentiment_1w_avg'] != 0).sum()
            matched_count = df_dates_only.isin(sentiment_df['date'].values).sum()
            print(f"  📊 Matched {matched_count} dates, {sentiment_count}/{len(features_df)} days with non-zero sentiment")
        elif self.use_sentiment:
            # No sentiment data available, use zeros
            features_df['sentiment_1w_avg'] = 0
            print(f"  ⚠️  No sentiment data available, using zeros for sentiment feature")

        # Compute 1w forward returns (target)
        future_returns = df['close'].pct_change(5).shift(-5) * 100  # 5 trading days ahead

        # Create binary labels: 1 = up, 0 = down
        labels = (future_returns > 0).astype(int)

        # SLIDING WINDOW APPROACH for sentiment data
        # If we have sentiment, create multiple training samples by sliding through sentiment period
        # Each day with sentiment becomes a prediction point (features) with 1w forward target
        if self.use_sentiment and use_sentiment_windows and sentiment_count > 20:
            # Filter to only use data where we have sentiment
            has_sentiment_mask = features_df['sentiment_1w_avg'] != 0
            sentiment_period_features = features_df[has_sentiment_mask]
            sentiment_period_labels = labels[has_sentiment_mask]

            # Remove NaN rows
            valid_mask_sentiment = ~(sentiment_period_features[self.feature_names].isna().any(axis=1) | sentiment_period_labels.isna())
            X_sentiment = sentiment_period_features.loc[valid_mask_sentiment, self.feature_names].values
            y_sentiment = sentiment_period_labels[valid_mask_sentiment].values

            # Also get non-sentiment samples for diversity (use 50% of historical data)
            no_sentiment_mask = features_df['sentiment_1w_avg'] == 0
            no_sentiment_features = features_df[no_sentiment_mask]
            no_sentiment_labels = labels[no_sentiment_mask]
            valid_mask_no_sent = ~(no_sentiment_features[self.feature_names].isna().any(axis=1) | no_sentiment_labels.isna())
            X_no_sentiment = no_sentiment_features.loc[valid_mask_no_sent, self.feature_names].values
            y_no_sentiment = no_sentiment_labels[valid_mask_no_sent].values

            # Subsample non-sentiment data to balance with sentiment data
            if len(X_no_sentiment) > len(X_sentiment) * 2:
                # Take random 2x sentiment samples from non-sentiment period
                import random
                indices = random.sample(range(len(X_no_sentiment)), min(len(X_sentiment) * 2, len(X_no_sentiment)))
                X_no_sentiment = X_no_sentiment[indices]
                y_no_sentiment = y_no_sentiment[indices]

            # Combine sentiment and non-sentiment samples
            X = np.vstack([X_sentiment, X_no_sentiment])
            y = np.concatenate([y_sentiment, y_no_sentiment])

            print(f"  🎯 Sliding window: {len(X_sentiment)} sentiment samples + {len(X_no_sentiment)} historical samples = {len(X)} total")
        else:
            # Standard approach: use all available data
            valid_mask = ~(features_df[self.feature_names].isna().any(axis=1) | labels.isna())
            X = features_df.loc[valid_mask, self.feature_names].values
            y = labels[valid_mask].values

        if len(X) < 50:
            raise ValueError(f"Insufficient training samples ({len(X)} < 50)")

        # Train/val split (last 20% for validation)
        split = int(len(X) * 0.8)
        X_train, X_val = X[:split], X[split:]
        y_train, y_val = y[:split], y[split:]

        # Standardize features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)

        # Train gradient boosting classifier
        self.model = GradientBoostingClassifier(
            n_estimators=n_estimators,
            learning_rate=0.1,
            max_depth=3,
            min_samples_split=20,
            min_samples_leaf=10,
            subsample=0.8,
            random_state=42,
            verbose=0
        )

        self.model.fit(X_train_scaled, y_train)

        # Evaluate
        train_acc = self.model.score(X_train_scaled, y_train)
        val_acc = self.model.score(X_val_scaled, y_val)

        # Get feature importances
        importances = dict(zip(self.feature_names, self.model.feature_importances_))

        return {
            'train_accuracy': round(train_acc * 100, 1),
            'val_accuracy': round(val_acc * 100, 1),
            'train_samples': len(X_train),
            'val_samples': len(X_val),
            'feature_importances': {k: round(v, 3) for k, v in importances.items()}
        }

    def predict(self, df: pd.DataFrame, sentiment_df: Optional[pd.DataFrame] = None) -> Dict:
        """
        Predict 1-week direction

        Args:
            df: DataFrame with recent OHLCV data
            sentiment_df: Optional DataFrame with recent sentiment data

        Returns:
            Prediction dict with direction, confidence, predicted_return
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        # Compute features for the most recent data point
        features_df = self._compute_features(df)

        # Add sentiment feature if available and model uses it
        if self.use_sentiment:
            if sentiment_df is not None and not sentiment_df.empty:
                # Calculate 1-week average sentiment from most recent data
                recent_sentiment = sentiment_df['sentiment_score'].tail(7).mean()
                features_df['sentiment_1w_avg'] = recent_sentiment
            else:
                features_df['sentiment_1w_avg'] = 0

        X = features_df[self.feature_names].iloc[[-1]].values

        # Standardize
        X_scaled = self.scaler.transform(X)

        # Predict probability
        proba = self.model.predict_proba(X_scaled)[0]
        prob_up = proba[1]
        prob_down = proba[0]

        # Direction and confidence
        direction = 'up' if prob_up > prob_down else 'down'
        confidence = max(prob_up, prob_down)

        # Estimate return magnitude (simple heuristic based on momentum and confidence)
        momentum = float(features_df['momentum_7d'].iloc[-1])
        # Scale the momentum by confidence (confident predictions extend the trend)
        predicted_return = momentum * confidence * 0.5  # Dampen the prediction

        return {
            'predicted_return': round(predicted_return, 2),
            'direction': direction,
            'confidence': round(confidence * 100, 1),
            'prob_up': round(prob_up * 100, 1),
            'prob_down': round(prob_down * 100, 1)
        }
