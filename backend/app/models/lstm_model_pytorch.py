"""
LSTM Model for Stock Price Prediction (PyTorch Implementation)
Multi-target architecture: one output per horizon (1w, 1m, 3m, 6m, 1y)
Each horizon is trained on its specific future return, eliminating the
identical 1w/1m prediction problem.
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
import pickle

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    from sklearn.preprocessing import MinMaxScaler, StandardScaler
    PYTORCH_AVAILABLE = True

    if torch.backends.mps.is_available():
        DEVICE = torch.device("mps")
        print("✅ Using Apple Metal (MPS) for LSTM acceleration")
    elif torch.cuda.is_available():
        DEVICE = torch.device("cuda")
        print("✅ Using CUDA GPU for LSTM acceleration")
    else:
        DEVICE = torch.device("cpu")
        print("⚠️  Using CPU for LSTM (slower)")

except ImportError:
    PYTORCH_AVAILABLE = False
    DEVICE = None
    print("⚠️  PyTorch not available. LSTM predictions will be disabled.")
    print("   Install with: pip install torch")


# Horizon definitions — order matters (maps to output neuron index)
HORIZONS = ['1w', '1m', '3m', '6m', '1y']
HORIZON_DAYS = {'1w': 5, '1m': 21, '3m': 63, '6m': 126, '1y': 252}
N_HORIZONS = len(HORIZONS)


class LSTMNetwork(nn.Module):
    """
    Multi-target LSTM Network.
    Outputs one predicted return per horizon simultaneously.
    """

    def __init__(self, input_size: int, hidden_size: int = 64,
                 num_layers: int = 3, dropout: float = 0.2,
                 n_outputs: int = N_HORIZONS):
        super(LSTMNetwork, self).__init__()

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True
        )
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(hidden_size, 32)
        self.relu = nn.ReLU()
        # One output per horizon: [1w, 1m, 3m, 6m, 1y]
        self.fc2 = nn.Linear(32, n_outputs)

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        out = self.dropout(lstm_out[:, -1, :])
        out = self.relu(self.fc1(out))
        return self.fc2(out)  # shape: [batch, n_horizons]


class LSTMStockPredictor:
    """LSTM-based stock price prediction with separate output per horizon"""

    def __init__(self, lookback_days: int = 60, seed: int = 42):
        if not PYTORCH_AVAILABLE:
            raise ImportError("PyTorch is required for LSTM predictions")

        # Seed for reproducible training
        torch.manual_seed(seed)
        np.random.seed(seed)

        self.lookback_days = lookback_days
        self.model = None
        self.feature_scaler = MinMaxScaler(feature_range=(0, 1))
        # Separate scalers per horizon so each return is normalised independently
        self.target_scalers = {h: StandardScaler() for h in HORIZONS}

        self.feature_columns = [
            'close', 'volume',
            'rsi', 'macd_histogram', 'bb_position', 'price_vs_sma50', 'obv',
            'ret_1d', 'ret_5d', 'ret_20d', 'volatility_10d',
            'atr', 'high_low_range', 'volume_spike', 'bb_width'
        ]
        self.device = DEVICE

    # ------------------------------------------------------------------
    # Data preparation
    # ------------------------------------------------------------------

    def _compute_returns(self, prices: np.ndarray, days: int) -> np.ndarray:
        """Compute future percentage returns for a given number of days."""
        n = len(prices)
        returns = np.full(n, np.nan)
        for i in range(n - days):
            if prices[i] > 0:
                returns[i] = (prices[i + days] - prices[i]) / prices[i] * 100
        return returns

    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute real technical indicators from OHLCV data for every row."""
        close = df['close']
        volume = df['volume']

        # RSI (14-period)
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = (100 - 100 / (1 + rs)).fillna(50)

        # MACD histogram (12/26 EMA diff, 9-period signal)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal = macd_line.ewm(span=9, adjust=False).mean()
        df['macd_histogram'] = macd_line - signal

        # Bollinger Band position (0=lower band, 1=upper band)
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        upper = sma20 + 2 * std20
        lower = sma20 - 2 * std20
        band_range = (upper - lower).replace(0, np.nan)
        df['bb_position'] = ((close - lower) / band_range).fillna(0.5).clip(0, 1)

        # Price vs SMA50 (% deviation)
        sma50 = close.rolling(50).mean()
        df['price_vs_sma50'] = ((close - sma50) / sma50 * 100).fillna(0)

        # On-Balance Volume (normalised to z-score so scale is comparable to other features)
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        obv_mean = obv.rolling(50, min_periods=10).mean()
        obv_std = obv.rolling(50, min_periods=10).std().replace(0, 1)
        df['obv'] = ((obv - obv_mean) / obv_std).fillna(0)

        # Return-based features (regime-agnostic, more stationary than price levels)
        df['ret_1d'] = close.pct_change(1).fillna(0) * 100
        df['ret_5d'] = close.pct_change(5).fillna(0) * 100
        df['ret_20d'] = close.pct_change(20).fillna(0) * 100
        df['volatility_10d'] = close.pct_change(1).rolling(10).std().fillna(0) * 100

        # Volatility features (critical for 1w predictions)
        # ATR (Average True Range) - 14-period volatility measure
        if 'high' in df.columns and 'low' in df.columns:
            high = df['high']
            low = df['low']
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            df['atr'] = true_range.rolling(14).mean().fillna(0)

            # High-Low range as % of close (intraday volatility)
            df['high_low_range'] = ((high - low) / close * 100).fillna(0)
        else:
            # Fallback if OHLC data unavailable
            df['atr'] = df['volatility_10d']
            df['high_low_range'] = df['volatility_10d']

        # Volume spike detection (volume / 20-day average)
        vol_ma20 = volume.rolling(20, min_periods=5).mean().replace(0, np.nan)
        df['volume_spike'] = (volume / vol_ma20).fillna(1.0)

        # Bollinger Band width (volatility regime indicator)
        df['bb_width'] = (band_range / sma20 * 100).fillna(0)

        return df

    def prepare_data(
        self,
        df: pd.DataFrame,
        technical_features: Dict
    ) -> Tuple[np.ndarray, np.ndarray, int]:
        """
        Prepare sequences (X) and multi-horizon targets (y).

        Returns:
            X: shape [n_samples, lookback, n_features]
            y: shape [n_samples, n_horizons]  — one column per horizon
            n_valid: number of valid (fully-labelled) samples
        """
        required = ['close', 'volume']
        if not all(c in df.columns for c in required):
            raise ValueError(f"DataFrame must contain: {required}")

        # Compute real technical indicators from price/volume history
        df = df.copy()
        df = self._add_technical_indicators(df)

        df = df[self.feature_columns].ffill().bfill()
        scaled_features = self.feature_scaler.fit_transform(df)

        prices = df['close'].values
        max_future = max(HORIZON_DAYS.values())  # 252

        # Compute future returns for each horizon
        all_returns = np.column_stack([
            self._compute_returns(prices, HORIZON_DAYS[h]) for h in HORIZONS
        ])  # shape [n_rows, n_horizons]

        # Build sequences — only keep samples where ALL horizon targets are valid
        X, y = [], []
        for i in range(self.lookback_days, len(scaled_features) - max_future):
            row_targets = all_returns[i]  # returns for this prediction date
            if np.any(np.isnan(row_targets)):
                continue
            X.append(scaled_features[i - self.lookback_days:i])
            y.append(row_targets)

        if not X:
            raise ValueError("Not enough data to create training samples")

        X = np.array(X, dtype=np.float32)
        y = np.array(y, dtype=np.float32)

        # Normalise targets per horizon
        for j, h in enumerate(HORIZONS):
            y[:, j:j+1] = self.target_scalers[h].fit_transform(y[:, j:j+1])

        return X, y, len(X)

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        df: pd.DataFrame,
        technical_features: Dict,
        epochs: int = 50,
        batch_size: int = 32,
        validation_split: float = 0.2,
        learning_rate: float = 0.001
    ) -> Dict:

        X, y, n_valid = self.prepare_data(df, technical_features)
        print(f"  Training samples: {n_valid} sequences × {X.shape[2]} features")

        if n_valid < 50:
            raise ValueError(f"Insufficient training samples ({n_valid} < 50)")

        X_t = torch.FloatTensor(X).to(self.device)
        y_t = torch.FloatTensor(y).to(self.device)

        split = int(n_valid * (1 - validation_split))
        X_tr, X_val = X_t[:split], X_t[split:]
        y_tr, y_val = y_t[:split], y_t[split:]

        loader = DataLoader(TensorDataset(X_tr, y_tr),
                            batch_size=batch_size, shuffle=True)

        self.model = LSTMNetwork(
            input_size=X.shape[2],
            hidden_size=64,
            num_layers=3,
            dropout=0.2,
            n_outputs=N_HORIZONS
        ).to(self.device)

        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate,
                                     weight_decay=1e-5)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, patience=5, factor=0.5)

        best_val_loss = float('inf')
        best_state = None
        patience_counter = 0
        history = {'loss': [], 'val_loss': []}

        for epoch in range(epochs):
            self.model.train()
            batch_losses = []
            for bX, by in loader:
                optimizer.zero_grad()
                loss = criterion(self.model(bX), by)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                batch_losses.append(loss.item())

            self.model.eval()
            with torch.no_grad():
                val_loss = criterion(self.model(X_val), y_val).item()

            avg_train = float(np.mean(batch_losses))
            history['loss'].append(avg_train)
            history['val_loss'].append(val_loss)
            scheduler.step(val_loss)

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = {k: v.clone() for k, v in self.model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= 10:
                    break

        # Restore best weights
        if best_state:
            self.model.load_state_dict(best_state)

        # Compute directional accuracy per horizon on validation set
        # Must inverse-transform to get actual return direction (sign in normalized
        # space ≠ sign in return space because StandardScaler shifts by mean)
        val_dir_acc = {}
        self.model.eval()
        with torch.no_grad():
            val_preds_raw = self.model(X_val).cpu().numpy()  # [val_n, N_HORIZONS]
            y_val_np = y_val.cpu().numpy()                   # [val_n, N_HORIZONS]
            for j, h in enumerate(HORIZONS):
                pred_inv = self.target_scalers[h].inverse_transform(
                    val_preds_raw[:, j:j+1])[:, 0]
                true_inv = self.target_scalers[h].inverse_transform(
                    y_val_np[:, j:j+1])[:, 0]
                acc = float(np.mean(np.sign(pred_inv) == np.sign(true_inv))) * 100
                val_dir_acc[h] = round(acc, 1)

        return {
            'loss': history['loss'][-1],
            'val_loss': best_val_loss,
            'epochs_trained': len(history['loss']),
            'val_directional_accuracy': val_dir_acc
        }

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        df: pd.DataFrame,
        technical_features: Dict,
        horizons: List[str] = None
    ) -> Dict:
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        if horizons is None:
            horizons = HORIZONS

        # Compute real technical indicators (same as in prepare_data)
        df = df.copy()
        df = self._add_technical_indicators(df)

        df_feat = df[self.feature_columns].ffill().bfill()
        scaled = self.feature_scaler.transform(df_feat)

        if len(scaled) < self.lookback_days:
            raise ValueError("Not enough data for prediction sequence")

        seq = torch.FloatTensor(
            scaled[-self.lookback_days:][np.newaxis, ...]
        ).to(self.device)

        self.model.eval()
        with torch.no_grad():
            raw_outputs = self.model(seq).cpu().numpy()[0]  # [n_horizons]

        current_price = float(df['close'].iloc[-1])
        predictions = {}

        for idx, h in enumerate(HORIZONS):
            if h not in horizons:
                continue

            # Inverse-scale the normalised return
            scaled_return = raw_outputs[idx]
            predicted_return = float(
                self.target_scalers[h].inverse_transform([[scaled_return]])[0][0]
            )

            predicted_price = current_price * (1 + predicted_return / 100)

            predictions[h] = {
                'predicted_return': round(predicted_return, 2),
                'predicted_price': round(predicted_price, 2),
                'current_price': round(current_price, 2),
                'confidence': self._calculate_confidence(predicted_return, HORIZON_DAYS[h])
            }

        return predictions

    def _calculate_confidence(self, predicted_return: float, days: int) -> float:
        base = 70
        magnitude_penalty = min(abs(predicted_return) * 0.5, 20)
        horizon_penalty = min(days / 50, 15)
        return round(max(30, min(90, base - magnitude_penalty - horizon_penalty)), 1)

    def save_model(self, path: str):
        if self.model is None:
            raise ValueError("No model to save")
        torch.save(self.model.state_dict(), f"{path}_model.pt")
        with open(f"{path}_scalers.pkl", 'wb') as f:
            pickle.dump({'feature': self.feature_scaler,
                         'targets': self.target_scalers}, f)

    def load_model(self, path: str, input_size: int):
        self.model = LSTMNetwork(input_size=input_size, n_outputs=N_HORIZONS).to(self.device)
        self.model.load_state_dict(torch.load(f"{path}_model.pt"))
        self.model.eval()
        with open(f"{path}_scalers.pkl", 'rb') as f:
            scalers = pickle.load(f)
            self.feature_scaler = scalers['feature']
            self.target_scalers = scalers['targets']

    @staticmethod
    def is_available() -> bool:
        return PYTORCH_AVAILABLE


class LSTMEnsemble:
    """Ensemble: val-accuracy-adaptive LSTM + heuristic weighting.

    LSTM weight is adjusted based on its validation directional accuracy:
    - val_acc >= 60%: full LSTM weight (model is reliable)
    - 50% <= val_acc < 60%: partial weight, scale linearly
    - val_acc < 50%: LSTM is worse than random; if the signal is consistently
      inverted (acc < 40%), we flip sign and use it; otherwise fall back to heuristic.
    """

    BASE_LSTM_WEIGHTS = {'1w': 0.65, '1m': 0.55, '3m': 0.50, '6m': 0.45, '1y': 0.40}

    def _effective_weight(self, h: str, val_acc: Optional[float]) -> Tuple[float, float]:
        """Return (effective_lstm_weight, sign_multiplier)."""
        base_w = self.BASE_LSTM_WEIGHTS.get(h, 0.55)
        if val_acc is None:
            return base_w, 1.0
        if val_acc >= 60:
            # High accuracy — use full base weight
            return base_w, 1.0
        elif val_acc >= 50:
            # Moderate accuracy — scale weight linearly from base → 0.3
            scale = (val_acc - 50) / 10  # 0..1
            return 0.3 + scale * (base_w - 0.3), 1.0
        elif val_acc >= 35:
            # Below-random but not inverted — heavily discount LSTM (small weight)
            return 0.15, 1.0
        else:
            # Well below 50% → signal is consistently inverted; flip and use it
            inv_acc = 100 - val_acc  # treat as if model says opposite
            scale = (inv_acc - 50) / 10 if inv_acc <= 60 else 1.0
            eff_w = min(0.3 + scale * (base_w - 0.3), base_w)
            return eff_w, -1.0

    def combine_predictions(
        self,
        lstm_predictions: Dict,
        heuristic_predictions: Dict
    ) -> Dict:
        ensemble = {}
        for h in lstm_predictions:
            if h not in heuristic_predictions:
                continue
            val_acc = lstm_predictions[h].get('val_directional_accuracy')
            lstm_w, sign_mult = self._effective_weight(h, val_acc)
            heur_w = 1.0 - lstm_w
            lstm_ret = lstm_predictions[h]['predicted_return'] * sign_mult
            heur_ret = heuristic_predictions[h].get('expected_return', 0)
            combined_ret = lstm_ret * lstm_w + heur_ret * heur_w
            lstm_conf = lstm_predictions[h].get('confidence', 50)
            heur_conf = heuristic_predictions[h].get('confidence', 50)
            # Confidence is lower when we had to invert or discount LSTM
            conf_scale = lstm_w / self.BASE_LSTM_WEIGHTS.get(h, 0.55)
            combined_conf = round(lstm_conf * lstm_w * conf_scale + heur_conf * heur_w, 1)
            ensemble[h] = {
                'predicted_return': round(combined_ret, 2),
                'direction': 'up' if combined_ret > 0 else 'down',
                'lstm_return': round(lstm_predictions[h]['predicted_return'], 2),
                'heuristic_return': round(heur_ret, 2),
                'confidence': combined_conf,
                'lstm_weight': lstm_w,
                'lstm_sign': sign_mult,
                'val_accuracy': val_acc,
                'method': 'Ensemble (LSTM + Heuristic)'
            }
        return ensemble
