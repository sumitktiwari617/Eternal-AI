from typing import Dict, Any, Optional
import pandas as pd
from config import Settings, settings as default_settings


def evaluate_signal(
    row: pd.Series,
    config: Optional[Settings] = None
) -> Dict[str, Any]:
    """
    Evaluates trading conditions for the given candle row.

    Rules:
      BUY BIAS:
        - Price > EMA_fast
        - EMA_fast > EMA_slow
        - Price > VWAP
        - rsi_buy_min <= RSI < rsi_buy_max

      SELL BIAS:
        - Price < EMA_fast
        - EMA_fast < EMA_slow
        - Price < VWAP
        - rsi_sell_min < RSI <= rsi_sell_max

      WAIT:
        - Conditions not met (provides detailed diagnostics)
    """
    cfg = config or default_settings

    price = float(row.get("close", 0.0))
    ema_fast_col = f"EMA{cfg.ema_fast}"
    ema_slow_col = f"EMA{cfg.ema_slow}"
    rsi_col = f"RSI{cfg.rsi_period}"
    atr_col = f"ATR{cfg.atr_period}"

    ema_fast = float(row.get(ema_fast_col, 0.0))
    ema_slow = float(row.get(ema_slow_col, 0.0))
    vwap = float(row.get("VWAP", 0.0))
    rsi = float(row.get(rsi_col, 50.0))
    atr = float(row.get(atr_col, 0.0))

    timestamp = str(row.name) if hasattr(row, "name") else None

    indicators = {
        "price": round(price, 2),
        "ema_fast": round(ema_fast, 2),
        "ema_slow": round(ema_slow, 2),
        "vwap": round(vwap, 2),
        "rsi": round(rsi, 2),
        "atr": round(atr, 2),
        "timestamp": timestamp,
    }

    # Evaluate BUY
    is_buy_trend = (price > ema_fast) and (ema_fast > ema_slow)
    is_buy_vwap = price > vwap
    is_buy_rsi = cfg.rsi_buy_min <= rsi < cfg.rsi_buy_max

    if is_buy_trend and is_buy_vwap and is_buy_rsi:
        return {
            "signal": "BUY",
            "action": "BUY BIAS",
            "reason": (
                f"Bullish alignment: Price (₹{price:.2f}) > EMA{cfg.ema_fast} (₹{ema_fast:.2f}) > "
                f"EMA{cfg.ema_slow} (₹{ema_slow:.2f}), above VWAP (₹{vwap:.2f}), and RSI is strong ({rsi:.1f})."
            ),
            "indicators": indicators,
        }

    # Evaluate SELL
    is_sell_trend = (price < ema_fast) and (ema_fast < ema_slow)
    is_sell_vwap = price < vwap
    is_sell_rsi = cfg.rsi_sell_min < rsi <= cfg.rsi_sell_max

    if is_sell_trend and is_sell_vwap and is_sell_rsi:
        return {
            "signal": "SELL",
            "action": "SELL BIAS",
            "reason": (
                f"Bearish alignment: Price (₹{price:.2f}) < EMA{cfg.ema_fast} (₹{ema_fast:.2f}) < "
                f"EMA{cfg.ema_slow} (₹{ema_slow:.2f}), below VWAP (₹{vwap:.2f}), and RSI is weak ({rsi:.1f})."
            ),
            "indicators": indicators,
        }

    # WAIT - Diagnosing why
    reasons = []
    if price > ema_fast and ema_fast > ema_slow:
        if not is_buy_vwap:
            reasons.append(f"Price is below VWAP (₹{vwap:.2f})")
        if rsi >= cfg.rsi_buy_max:
            reasons.append(f"RSI is overbought ({rsi:.1f} >= {cfg.rsi_buy_max})")
        elif rsi < cfg.rsi_buy_min:
            reasons.append(f"RSI momentum too low for buy ({rsi:.1f} < {cfg.rsi_buy_min})")
    elif price < ema_fast and ema_fast < ema_slow:
        if not is_sell_vwap:
            reasons.append(f"Price is above VWAP (₹{vwap:.2f})")
        if rsi <= cfg.rsi_sell_min:
            reasons.append(f"RSI is oversold ({rsi:.1f} <= {cfg.rsi_sell_min})")
        elif rsi > cfg.rsi_sell_max:
            reasons.append(f"RSI momentum too high for sell ({rsi:.1f} > {cfg.rsi_sell_max})")
    else:
        reasons.append("Moving averages in transition or consolidation")

    wait_reason = "; ".join(reasons) if reasons else "Conditions do not sufficiently align for high-probability entry."

    return {
        "signal": "WAIT",
        "action": "WAIT",
        "reason": wait_reason,
        "indicators": indicators,
    }

