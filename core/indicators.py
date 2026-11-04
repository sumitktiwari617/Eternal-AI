import pandas as pd
import numpy as np
from typing import Optional


def calculate_indicators(
    df: pd.DataFrame,
    ema_fast: int = 20,
    ema_slow: int = 50,
    rsi_period: int = 14,
    atr_period: int = 14,
) -> pd.DataFrame:
    """
    Computes technical indicators for the ETERNAL trading system:
      - EMA Fast (default 20)
      - EMA Slow (default 50)
      - Intraday VWAP (Volume Weighted Average Price with daily reset)
      - RSI (Wilder's smoothed Relative Strength Index)
      - ATR (Average True Range for volatility-based stops)

    Input requirements:
      Columns: open, high, low, close, volume (case-insensitive)
      Index: preferably DatetimeIndex (for intraday daily VWAP reset)
    """
    if df is None or df.empty:
        raise ValueError("Cannot calculate indicators on empty or None DataFrame.")

    data = df.copy()
    data.columns = [str(c).lower() for c in data.columns]

    required = {"high", "low", "close", "volume"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Missing required columns in DataFrame: {sorted(missing)}")

    # Clean numeric types and sort
    for col in ["open", "high", "low", "close", "volume"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    # Drop rows where crucial OHLCV are NaN
    data = data.dropna(subset=["high", "low", "close", "volume"])

    if len(data) < 2:
        raise ValueError("At least 2 valid candles are required to calculate indicators.")

    close = data["close"]
    high = data["high"]
    low = data["low"]
    volume = data["volume"]

    # 1. Exponential Moving Averages
    data[f"EMA{ema_fast}"] = close.ewm(span=ema_fast, adjust=False).mean()
    data[f"EMA{ema_slow}"] = close.ewm(span=ema_slow, adjust=False).mean()

    # 2. Intraday VWAP (with Daily Reset)
    typical_price = (high + low + close) / 3.0
    if isinstance(data.index, pd.DatetimeIndex):
        day_key = pd.Series(data.index.date, index=data.index)
        cum_pv = (typical_price * volume).groupby(day_key).cumsum()
        cum_vol = volume.groupby(day_key).cumsum()
    else:
        cum_pv = (typical_price * volume).cumsum()
        cum_vol = volume.cumsum()

    data["VWAP"] = cum_pv / cum_vol.replace(0, np.nan)
    # If initial volume is 0, fallback to typical price
    data["VWAP"] = data["VWAP"].fillna(typical_price)

    # 3. Wilder's Smoothed RSI
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1.0 / rsi_period, min_periods=rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / rsi_period, min_periods=rsi_period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    # Handle edge conditions
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    rsi = rsi.where(~((avg_gain == 0) & (avg_loss > 0)), 0.0)
    rsi = rsi.fillna(50.0)  # Default neutral for early warmup bars
    data[f"RSI{rsi_period}"] = rsi

    # 4. Average True Range (ATR)
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)

    data[f"ATR{atr_period}"] = tr.ewm(alpha=1.0 / atr_period, min_periods=atr_period, adjust=False).mean()
    data[f"ATR{atr_period}"] = data[f"ATR{atr_period}"].fillna(high - low)

    return data

