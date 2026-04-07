"""
LSTM Model for Stock Price Prediction
Uses TensorFlow/Keras to build time series forecasting model
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
import pickle
import os

# Try to import TensorFlow, fall back gracefully if not available
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from sklearn.preprocessing import MinMaxScaler
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    print("⚠️  TensorFlow not available. LSTM predictions will be disabled.")
    print("   Install with: pip install tensorflow")


class LSTMStockPredictor:
    """LSTM-based stock price prediction model"""

    def __init__(self, lookback_days: int = 60):
        """
        Initialize LSTM predictor

        Args:
            lookback_days: Number of historical days to use for prediction
        """
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow is required for LSTM predictions")

        self.lookback_days = lookback_days
        self.model = None
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.feature_columns = [
            'close', 'volume', 'rsi', 'macd_histogram',
            'bb_position', 'price_vs_sma50', 'obv'
        ]

    def build_model(self, input_shape: Tuple[int, int]) -> Sequential:
        """
        Build LSTM model architecture

        Args:
            input_shape: (lookback_days, n_features)

        Returns:
            Compiled Keras model
        """
        model = Sequential([
            # First LSTM layer with 50 units
            LSTM(50, return_sequences=True, input_shape=input_shape),
            Dropout(0.2),

            # Second LSTM layer with 50 units
            LSTM(50, return_sequences=True),
            Dropout(0.2),

            # Third LSTM layer
            LSTM(50, return_sequences=False),
            Dropout(0.2),

            # Dense layers
            Dense(25, activation='relu'),
            Dense(1)  # Output: predicted price change
        ])

        model.compile(
            optimizer='adam',
            loss='mean_squared_error',
            metrics=['mae']
        )

        return model

    def prepare_data(
        self,
        df: pd.DataFrame,
        technical_features: Dict
    ) -> Tuple[np.ndarray, np.ndarray, pd.Series]:
        """
        Prepare data for LSTM training

        Args:
            df: DataFrame with price history
            technical_features: Dict of technical indicators

        Returns:
            Tuple of (X, y, prices) where:
                X: Input sequences (lookback_days, n_features)
                y: Target values (future returns)
                prices: Price series for reference
        """
        # Ensure we have required columns
        required = ['close', 'volume']
        if not all(col in df.columns for col in required):
            raise ValueError(f"DataFrame must have columns: {required}")

        # Add technical indicators to dataframe
        for key, value in technical_features.items():
            if key in self.feature_columns and value is not None:
                # Broadcast scalar to entire column
                df[key] = value

        # Fill missing values with forward fill then backward fill
        df = df[self.feature_columns].fillna(method='ffill').fillna(method='bfill')

        # Normalize the data
        scaled_data = self.scaler.fit_transform(df)

        # Create sequences
        X, y = [], []
        for i in range(self.lookback_days, len(scaled_data)):
            X.append(scaled_data[i-self.lookback_days:i])
            # Target: next day's price change
            y.append(scaled_data[i, 0])  # close price

        X = np.array(X)
        y = np.array(y)

        return X, y, df['close']

    def train(
        self,
        df: pd.DataFrame,
        technical_features: Dict,
        epochs: int = 50,
        batch_size: int = 32,
        validation_split: float = 0.2
    ) -> Dict:
        """
        Train LSTM model on historical data

        Args:
            df: DataFrame with price history
            technical_features: Technical indicators
            epochs: Number of training epochs
            batch_size: Training batch size
            validation_split: Fraction of data for validation

        Returns:
            Training history
        """
        # Prepare data
        X, y, prices = self.prepare_data(df, technical_features)

        if len(X) < 100:
            raise ValueError("Insufficient data for training (need at least 100 samples)")

        # Build model
        input_shape = (X.shape[1], X.shape[2])
        self.model = self.build_model(input_shape)

        # Train model
        history = self.model.fit(
            X, y,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            verbose=0,
            callbacks=[
                keras.callbacks.EarlyStopping(
                    monitor='val_loss',
                    patience=10,
                    restore_best_weights=True
                )
            ]
        )

        return {
            'loss': float(history.history['loss'][-1]),
            'val_loss': float(history.history['val_loss'][-1]),
            'mae': float(history.history['mae'][-1]),
            'epochs_trained': len(history.history['loss'])
        }

    def predict(
        self,
        df: pd.DataFrame,
        technical_features: Dict,
        horizons: list = ['1w', '1m', '3m', '6m', '1y']
    ) -> Dict:
        """
        Make predictions for different time horizons

        Args:
            df: Recent price history
            technical_features: Current technical indicators
            horizons: List of prediction horizons

        Returns:
            Dictionary of predictions by horizon
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        # Prepare input sequence
        X, _, prices = self.prepare_data(df, technical_features)

        if len(X) == 0:
            raise ValueError("Insufficient data for prediction")

        # Use the most recent sequence
        last_sequence = X[-1:].reshape(1, self.lookback_days, len(self.feature_columns))

        predictions = {}

        # Map horizons to trading days
        horizon_days = {
            '1w': 5,
            '1m': 21,
            '3m': 63,
            '6m': 126,
            '1y': 252
        }

        current_price = prices.iloc[-1]

        for horizon in horizons:
            days = horizon_days.get(horizon, 21)

            # Predict future price
            # For longer horizons, make iterative predictions
            if days <= 21:
                # Direct prediction for short horizons
                predicted_scaled = self.model.predict(last_sequence, verbose=0)[0][0]
            else:
                # Iterative prediction for longer horizons
                # (simplified - could be enhanced with recursive forecasting)
                predicted_scaled = self.model.predict(last_sequence, verbose=0)[0][0]
                # Adjust for longer horizon
                predicted_scaled *= (days / 21) * 0.8  # Scale with time

            # Inverse transform to get actual price
            dummy = np.zeros((1, len(self.feature_columns)))
            dummy[0, 0] = predicted_scaled
            predicted_price = self.scaler.inverse_transform(dummy)[0, 0]

            # Calculate return percentage
            predicted_return = ((predicted_price - current_price) / current_price) * 100

            predictions[horizon] = {
                'predicted_return': float(predicted_return),
                'predicted_price': float(predicted_price),
                'current_price': float(current_price),
                'confidence': self._calculate_confidence(predicted_return, days)
            }

        return predictions

    def _calculate_confidence(self, predicted_return: float, days: int) -> float:
        """
        Calculate confidence score based on prediction magnitude and horizon

        Args:
            predicted_return: Predicted return percentage
            days: Number of days in horizon

        Returns:
            Confidence score (0-100)
        """
        # Lower confidence for more extreme predictions
        # Lower confidence for longer horizons
        base_confidence = 70

        # Penalty for extreme predictions
        magnitude_penalty = min(abs(predicted_return) * 0.5, 20)

        # Penalty for longer horizons
        horizon_penalty = min(days / 50, 15)

        confidence = base_confidence - magnitude_penalty - horizon_penalty
        return max(30, min(90, confidence))

    def save_model(self, path: str):
        """Save model and scaler to disk"""
        if self.model is None:
            raise ValueError("No model to save")

        # Save Keras model
        self.model.save(f"{path}_model.h5")

        # Save scaler
        with open(f"{path}_scaler.pkl", 'wb') as f:
            pickle.dump(self.scaler, f)

    def load_model(self, path: str):
        """Load model and scaler from disk"""
        # Load Keras model
        self.model = load_model(f"{path}_model.h5")

        # Load scaler
        with open(f"{path}_scaler.pkl", 'rb') as f:
            self.scaler = pickle.load(f)

    @staticmethod
    def is_available() -> bool:
        """Check if TensorFlow is available"""
        return TENSORFLOW_AVAILABLE


class LSTMEnsemble:
    """Ensemble combining LSTM and heuristic predictions"""

    def __init__(self):
        self.lstm_weight = 0.6  # 60% LSTM, 40% heuristic
        self.heuristic_weight = 0.4

    def combine_predictions(
        self,
        lstm_predictions: Dict,
        heuristic_predictions: Dict
    ) -> Dict:
        """
        Combine LSTM and heuristic predictions

        Args:
            lstm_predictions: Predictions from LSTM model
            heuristic_predictions: Predictions from heuristic model

        Returns:
            Combined ensemble predictions
        """
        ensemble = {}

        for horizon in lstm_predictions.keys():
            if horizon not in heuristic_predictions:
                continue

            lstm_return = lstm_predictions[horizon]['predicted_return']
            heuristic_return = heuristic_predictions[horizon].get('expected_return', 0)

            # Weighted average
            combined_return = (
                lstm_return * self.lstm_weight +
                heuristic_return * self.heuristic_weight
            )

            # Combined confidence (average)
            lstm_conf = lstm_predictions[horizon].get('confidence', 50)
            heuristic_conf = heuristic_predictions[horizon].get('confidence', 50)
            combined_confidence = (lstm_conf + heuristic_conf) / 2

            ensemble[horizon] = {
                'predicted_return': combined_return,
                'lstm_return': lstm_return,
                'heuristic_return': heuristic_return,
                'confidence': combined_confidence,
                'method': 'Ensemble (LSTM + Heuristic)'
            }

        return ensemble

    def get_best_prediction(
        self,
        lstm_predictions: Dict,
        heuristic_predictions: Dict
    ) -> Dict:
        """
        Select best prediction based on confidence scores

        Args:
            lstm_predictions: LSTM predictions
            heuristic_predictions: Heuristic predictions

        Returns:
            Best predictions per horizon
        """
        best = {}

        for horizon in lstm_predictions.keys():
            if horizon not in heuristic_predictions:
                best[horizon] = lstm_predictions[horizon]
                continue

            lstm_conf = lstm_predictions[horizon].get('confidence', 0)
            heuristic_conf = heuristic_predictions[horizon].get('confidence', 0)

            # Choose model with higher confidence
            if lstm_conf > heuristic_conf:
                best[horizon] = {
                    **lstm_predictions[horizon],
                    'selected_model': 'LSTM',
                    'alternative_return': heuristic_predictions[horizon].get('expected_return', 0)
                }
            else:
                best[horizon] = {
                    'predicted_return': heuristic_predictions[horizon].get('expected_return', 0),
                    'confidence': heuristic_conf,
                    'selected_model': 'Heuristic',
                    'alternative_return': lstm_predictions[horizon]['predicted_return']
                }

        return best
