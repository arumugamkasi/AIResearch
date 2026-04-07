"""
Technical Indicators Library
Implements various technical analysis indicators for stock price analysis
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, Optional, List


class TechnicalIndicators:
    """Calculate technical indicators for stock price analysis"""

    @staticmethod
    def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
        """
        Simple Moving Average

        Args:
            prices: Series of closing prices
            period: Number of periods for average

        Returns:
            Series of SMA values
        """
        return prices.rolling(window=period).mean()

    @staticmethod
    def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
        """
        Exponential Moving Average

        Args:
            prices: Series of closing prices
            period: Number of periods for average

        Returns:
            Series of EMA values
        """
        return prices.ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Relative Strength Index

        Args:
            prices: Series of closing prices
            period: RSI period (default 14)

        Returns:
            Series of RSI values (0-100)
        """
        # Calculate price changes
        delta = prices.diff()

        # Separate gains and losses
        gains = delta.where(delta > 0, 0.0)
        losses = -delta.where(delta < 0, 0.0)

        # Calculate average gains and losses
        avg_gains = gains.rolling(window=period).mean()
        avg_losses = losses.rolling(window=period).mean()

        # Calculate RS and RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def calculate_rci(prices: pd.Series, period: int = 9) -> pd.Series:
        """
        Rank Correlation Index (Spearman's Rank Correlation)

        Args:
            prices: Series of closing prices
            period: RCI period (default 9, common: 9, 12, 26)

        Returns:
            Series of RCI values (-100 to +100)
        """
        def rci_window(window):
            if len(window) < period:
                return np.nan

            # Create ranks for position (newest = 1, oldest = period)
            position_ranks = np.arange(1, period + 1)

            # Create ranks for prices (highest = 1, lowest = period)
            price_ranks = pd.Series(window).rank(ascending=False, method='average').values

            # Calculate sum of squared differences
            d_squared = np.sum((position_ranks - price_ranks) ** 2)

            # RCI formula
            rci = (1 - (6 * d_squared / (period * (period ** 2 - 1)))) * 100

            return rci

        return prices.rolling(window=period).apply(rci_window, raw=False)

    @staticmethod
    def calculate_macd(
        prices: pd.Series,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Moving Average Convergence Divergence

        Args:
            prices: Series of closing prices
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line EMA period (default 9)

        Returns:
            Tuple of (MACD line, Signal line, Histogram)
        """
        # Calculate EMAs
        ema_fast = TechnicalIndicators.calculate_ema(prices, fast_period)
        ema_slow = TechnicalIndicators.calculate_ema(prices, slow_period)

        # MACD line
        macd_line = ema_fast - ema_slow

        # Signal line
        signal_line = TechnicalIndicators.calculate_ema(macd_line, signal_period)

        # Histogram
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def calculate_bollinger_bands(
        prices: pd.Series,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Bollinger Bands

        Args:
            prices: Series of closing prices
            period: Moving average period (default 20)
            std_dev: Number of standard deviations (default 2.0)

        Returns:
            Tuple of (Upper band, Middle band, Lower band)
        """
        # Middle band (SMA)
        middle_band = TechnicalIndicators.calculate_sma(prices, period)

        # Standard deviation
        rolling_std = prices.rolling(window=period).std()

        # Upper and lower bands
        upper_band = middle_band + (rolling_std * std_dev)
        lower_band = middle_band - (rolling_std * std_dev)

        return upper_band, middle_band, lower_band

    @staticmethod
    def calculate_stochastic(
        highs: pd.Series,
        lows: pd.Series,
        closes: pd.Series,
        period: int = 14,
        smooth_k: int = 3,
        smooth_d: int = 3
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Stochastic Oscillator

        Args:
            highs: Series of high prices
            lows: Series of low prices
            closes: Series of closing prices
            period: Lookback period (default 14)
            smooth_k: %K smoothing period (default 3)
            smooth_d: %D smoothing period (default 3)

        Returns:
            Tuple of (%K, %D)
        """
        # Get highest high and lowest low over period
        highest_high = highs.rolling(window=period).max()
        lowest_low = lows.rolling(window=period).min()

        # Calculate raw %K
        raw_k = 100 * (closes - lowest_low) / (highest_high - lowest_low)

        # Smooth %K
        k = raw_k.rolling(window=smooth_k).mean()

        # Calculate %D (SMA of %K)
        d = k.rolling(window=smooth_d).mean()

        return k, d

    @staticmethod
    def calculate_atr(
        highs: pd.Series,
        lows: pd.Series,
        closes: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        Average True Range

        Args:
            highs: Series of high prices
            lows: Series of low prices
            closes: Series of closing prices
            period: ATR period (default 14)

        Returns:
            Series of ATR values
        """
        # Calculate True Range components
        high_low = highs - lows
        high_close = np.abs(highs - closes.shift())
        low_close = np.abs(lows - closes.shift())

        # True Range is the maximum of the three
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # ATR is the moving average of True Range
        atr = true_range.rolling(window=period).mean()

        return atr

    @staticmethod
    def calculate_obv(closes: pd.Series, volumes: pd.Series) -> pd.Series:
        """
        On-Balance Volume

        Args:
            closes: Series of closing prices
            volumes: Series of volumes

        Returns:
            Series of OBV values
        """
        # Determine direction: 1 if price up, -1 if price down, 0 if unchanged
        direction = np.where(closes > closes.shift(), 1,
                           np.where(closes < closes.shift(), -1, 0))

        # Cumulative sum of (direction * volume)
        obv = (direction * volumes).cumsum()

        return pd.Series(obv, index=closes.index)

    @staticmethod
    def calculate_volume_roc(volumes: pd.Series, period: int = 12) -> pd.Series:
        """
        Volume Rate of Change

        Args:
            volumes: Series of volumes
            period: Period for ROC calculation (default 12)

        Returns:
            Series of Volume ROC values (percentage)
        """
        volume_roc = ((volumes - volumes.shift(period)) / volumes.shift(period)) * 100
        return volume_roc

    @staticmethod
    def calculate_williams_r(
        highs: pd.Series,
        lows: pd.Series,
        closes: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        Williams %R

        Args:
            highs: Series of high prices
            lows: Series of low prices
            closes: Series of closing prices
            period: Lookback period (default 14)

        Returns:
            Series of Williams %R values (-100 to 0)
        """
        highest_high = highs.rolling(window=period).max()
        lowest_low = lows.rolling(window=period).min()

        williams_r = -100 * (highest_high - closes) / (highest_high - lowest_low)

        return williams_r

    @staticmethod
    def extract_all_features(df: pd.DataFrame) -> Dict:
        """
        Extract all technical indicator features from price data

        Args:
            df: DataFrame with columns: date, open, high, low, close, volume

        Returns:
            Dictionary of technical indicator values (most recent)
        """
        if df is None or len(df) < 50:
            return {}

        closes = df['close']
        highs = df['high']
        lows = df['low']
        volumes = df['volume']

        features = {}

        try:
            # Moving Averages
            features['sma_5'] = TechnicalIndicators.calculate_sma(closes, 5).iloc[-1]
            features['sma_10'] = TechnicalIndicators.calculate_sma(closes, 10).iloc[-1]
            features['sma_20'] = TechnicalIndicators.calculate_sma(closes, 20).iloc[-1]
            features['sma_50'] = TechnicalIndicators.calculate_sma(closes, 50).iloc[-1]

            if len(df) >= 200:
                features['sma_200'] = TechnicalIndicators.calculate_sma(closes, 200).iloc[-1]
            else:
                features['sma_200'] = None

            # Current price vs MAs
            current_price = closes.iloc[-1]
            features['price_vs_sma5'] = ((current_price - features['sma_5']) / features['sma_5']) * 100 if features['sma_5'] else 0
            features['price_vs_sma10'] = ((current_price - features['sma_10']) / features['sma_10']) * 100 if features['sma_10'] else 0
            features['price_vs_sma20'] = ((current_price - features['sma_20']) / features['sma_20']) * 100 if features['sma_20'] else 0
            features['price_vs_sma50'] = ((current_price - features['sma_50']) / features['sma_50']) * 100 if features['sma_50'] else 0

            if features['sma_200']:
                features['price_vs_sma200'] = ((current_price - features['sma_200']) / features['sma_200']) * 100
                features['sma50_vs_sma200'] = ((features['sma_50'] - features['sma_200']) / features['sma_200']) * 100
            else:
                features['price_vs_sma200'] = 0
                features['sma50_vs_sma200'] = 0

            # RSI
            rsi = TechnicalIndicators.calculate_rsi(closes)
            features['rsi'] = rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50

            # RCI
            rci_9 = TechnicalIndicators.calculate_rci(closes, 9)
            rci_26 = TechnicalIndicators.calculate_rci(closes, 26)
            features['rci_9'] = rci_9.iloc[-1] if not np.isnan(rci_9.iloc[-1]) else 0
            features['rci_26'] = rci_26.iloc[-1] if not np.isnan(rci_26.iloc[-1]) else 0

            # MACD
            macd_line, signal_line, histogram = TechnicalIndicators.calculate_macd(closes)
            features['macd'] = macd_line.iloc[-1] if not np.isnan(macd_line.iloc[-1]) else 0
            features['macd_signal'] = signal_line.iloc[-1] if not np.isnan(signal_line.iloc[-1]) else 0
            features['macd_histogram'] = histogram.iloc[-1] if not np.isnan(histogram.iloc[-1]) else 0

            # Bollinger Bands
            upper_bb, middle_bb, lower_bb = TechnicalIndicators.calculate_bollinger_bands(closes)
            features['bb_upper'] = upper_bb.iloc[-1]
            features['bb_middle'] = middle_bb.iloc[-1]
            features['bb_lower'] = lower_bb.iloc[-1]
            bb_width = upper_bb.iloc[-1] - lower_bb.iloc[-1]
            features['bb_width'] = (bb_width / middle_bb.iloc[-1]) * 100 if middle_bb.iloc[-1] else 0
            features['bb_position'] = ((current_price - lower_bb.iloc[-1]) / bb_width) if bb_width > 0 else 0.5

            # Stochastic
            stoch_k, stoch_d = TechnicalIndicators.calculate_stochastic(highs, lows, closes)
            features['stoch_k'] = stoch_k.iloc[-1] if not np.isnan(stoch_k.iloc[-1]) else 50
            features['stoch_d'] = stoch_d.iloc[-1] if not np.isnan(stoch_d.iloc[-1]) else 50

            # ATR
            atr = TechnicalIndicators.calculate_atr(highs, lows, closes)
            features['atr'] = atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 0
            features['atr_percent'] = (atr.iloc[-1] / current_price) * 100 if current_price else 0

            # OBV
            obv = TechnicalIndicators.calculate_obv(closes, volumes)
            features['obv'] = obv.iloc[-1]
            # OBV trend (compare recent OBV to average)
            recent_obv = obv.iloc[-10:].mean()
            older_obv = obv.iloc[-30:-10].mean()
            features['obv_trend'] = 'rising' if recent_obv > older_obv else 'falling'

            # Volume ROC
            vroc = TechnicalIndicators.calculate_volume_roc(volumes)
            features['volume_roc'] = vroc.iloc[-1] if not np.isnan(vroc.iloc[-1]) else 0

        except Exception as e:
            print(f"Error extracting technical features: {e}")

        # Convert numpy types to native Python types for JSON serialization
        features = {k: (float(v) if isinstance(v, (np.integer, np.floating)) else v)
                   for k, v in features.items()}

        return features

    @staticmethod
    def generate_signals(features: Dict) -> List[str]:
        """
        Generate trading signals based on technical indicators

        Args:
            features: Dictionary of technical indicator values

        Returns:
            List of signal strings
        """
        signals = []

        if not features:
            return signals

        try:
            # Moving Average Signals
            if features.get('price_vs_sma50', 0) > 0 and features.get('price_vs_sma200', 0) > 0:
                signals.append("Price above major MAs (bullish)")
            elif features.get('price_vs_sma50', 0) < 0 and features.get('price_vs_sma200', 0) < 0:
                signals.append("Price below major MAs (bearish)")

            # Golden Cross / Death Cross
            if features.get('sma50_vs_sma200', 0) > 2:
                signals.append("Golden Cross (50 MA > 200 MA)")
            elif features.get('sma50_vs_sma200', 0) < -2:
                signals.append("Death Cross (50 MA < 200 MA)")

            # RSI Signals
            rsi = features.get('rsi', 50)
            if rsi > 70:
                signals.append(f"RSI overbought ({rsi:.1f})")
            elif rsi < 30:
                signals.append(f"RSI oversold ({rsi:.1f})")
            else:
                signals.append(f"RSI neutral ({rsi:.1f})")

            # MACD Signals
            if features.get('macd_histogram', 0) > 0:
                signals.append("MACD positive (bullish)")
            elif features.get('macd_histogram', 0) < 0:
                signals.append("MACD negative (bearish)")

            # Bollinger Bands
            bb_pos = features.get('bb_position', 0.5)
            if bb_pos > 0.8:
                signals.append("Near upper Bollinger Band (overbought)")
            elif bb_pos < 0.2:
                signals.append("Near lower Bollinger Band (oversold)")

            # Volume confirmation
            if features.get('obv_trend') == 'rising' and features.get('volume_roc', 0) > 0:
                signals.append("Volume supporting uptrend")
            elif features.get('obv_trend') == 'falling' and features.get('volume_roc', 0) < 0:
                signals.append("Volume supporting downtrend")

        except Exception as e:
            print(f"Error generating signals: {e}")

        return signals
