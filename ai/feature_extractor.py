from typing import Tuple, List, Optional
import pandas as pd
import numpy as np


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Computes Wilder's Smoothed RSI."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    rsi = rsi.where(~((avg_gain == 0) & (avg_loss > 0)), 0.0)
    return rsi.fillna(50.0)


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts 30+ quantitative, momentum, trend, and volatility features
    from raw OHLCV candles for machine learning.
    """
    if df is None or len(df) < 20:
        raise ValueError("At least 20 candles are required for feature extraction.")

    data = df.copy()
    data.columns = [str(c).lower() for c in data.columns]

    close = data["close"]
    open_p = data["open"]
    high = data["high"]
    low = data["low"]
    volume = data["volume"].replace(0, 1)

    feats = pd.DataFrame(index=data.index)

    # 1. Multi-Period RSI Features
    feats["rsi_9"] = compute_rsi(close, 9)
    feats["rsi_14"] = compute_rsi(close, 14)
    feats["rsi_21"] = compute_rsi(close, 21)
    feats["rsi_diff"] = feats["rsi_9"] - feats["rsi_14"]
    feats["rsi_9_slope"] = feats["rsi_9"].diff(3)

    # 2. Moving Average Trend & Cross Features
    ema_20 = close.ewm(span=20, adjust=False).mean()
    ema_50 = close.ewm(span=50, adjust=False).mean()
    feats["price_to_ema20"] = (close - ema_20) / close * 100.0
    feats["price_to_ema50"] = (close - ema_50) / close * 100.0
    feats["ema20_to_ema50"] = (ema_20 - ema_50) / ema_50 * 100.0

    # 3. Intraday VWAP Features
    typical_price = (high + low + close) / 3.0
    if isinstance(data.index, pd.DatetimeIndex):
        day_key = pd.Series(data.index.date, index=data.index)
        cum_pv = (typical_price * volume).groupby(day_key).cumsum()
        cum_vol = volume.groupby(day_key).cumsum()
    else:
        cum_pv = (typical_price * volume).cumsum()
        cum_vol = volume.cumsum()

    vwap = cum_pv / cum_vol.replace(0, np.nan)
    vwap = vwap.fillna(typical_price)
    feats["price_to_vwap"] = (close - vwap) / vwap * 100.0

    # 4. Volatility & Normalized ATR
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    atr_14 = tr.ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean()
    feats["atr_normalized"] = atr_14 / close * 100.0

    # 5. Relative Volume Features
    vol_sma20 = volume.rolling(20, min_periods=1).mean().replace(0, 1)
    feats["volume_ratio"] = volume / vol_sma20
    feats["volume_surge"] = (feats["volume_ratio"] > 1.5).astype(float)

    # 6. Candlestick Price Action
    candle_range = (high - low).replace(0, 0.01)
    feats["body_to_range"] = (close - open_p).abs() / candle_range
    feats["upper_shadow"] = (high - pd.concat([open_p, close], axis=1).max(axis=1)) / candle_range
    feats["lower_shadow"] = (pd.concat([open_p, close], axis=1).min(axis=1) - low) / candle_range

    # 7. Momentum Return Features
    feats["return_1"] = close.pct_change(1) * 100.0
    feats["return_3"] = close.pct_change(3) * 100.0
    feats["return_5"] = close.pct_change(5) * 100.0

    return feats.dropna()


def prepare_training_dataset(
    df: pd.DataFrame,
    forward_periods: int = 2,
    threshold_pct: float = 0.25
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Constructs feature matrix X and target labels y:
      Label 1 = BUY  (Forward return > +threshold_pct)
      Label 2 = SELL (Forward return < -threshold_pct)
      Label 0 = HOLD / WAIT (Price within neutral band)
    """
    feats = extract_features(df)
    close = df.loc[feats.index, "close"]

    # Calculate future forward return
    forward_return = (close.shift(-forward_periods) - close) / close * 100.0

    labels = pd.Series(0, index=feats.index, name="target")
    labels[forward_return > threshold_pct] = 1   # BUY
    labels[forward_return < -threshold_pct] = 2  # SELL

    # Remove the last forward_periods rows because future is unknown
    valid_mask = forward_return.notna()
    X = feats.loc[valid_mask]
    y = labels.loc[valid_mask]

    return X, y

