from typing import Dict, Any


def generate_decision_reason(prediction: Dict[str, Any]) -> str:
    """
    Generates a clear, explainable plain-English justification for why the AI
    recommends BUY, SELL, or HOLD.
    """
    signal = prediction.get("signal", "HOLD")
    raw_signal = prediction.get("raw_signal", signal)
    conf = prediction.get("confidence", 50.0)
    price = prediction.get("latest_price", 0.0)
    feats = prediction.get("feature_snapshot", {})

    r9 = feats.get("rsi_9", 50.0)
    r14 = feats.get("rsi_14", 50.0)
    p_vwap = feats.get("price_to_vwap", 0.0)
    p_ema20 = feats.get("price_to_ema20", 0.0)
    vol_ratio = feats.get("volume_ratio", 1.0)
    atr_norm = feats.get("atr_normalized", 1.0)

    reasons = []

    if signal == "BUY":
        reasons.append(f"Bullish momentum surge: Fast RSI 9 ({r9:.1f}) is leading above RSI 14 ({r14:.1f})")
        if p_vwap > 0:
            reasons.append(f"Price (₹{price:.2f}) is holding {p_vwap:.2f}% above Intraday VWAP")
        if p_ema20 > 0:
            reasons.append(f"Trading above EMA20 by +{p_ema20:.2f}%")
        if vol_ratio >= 1.2:
            reasons.append(f"Volume expansion confirmed ({vol_ratio:.1f}x of 20-period average)")
        reasons.append(f"AI Model probability of upward continuation is {conf:.1f}%.")
        return ". ".join(reasons)

    elif signal == "SELL":
        reasons.append(f"Bearish breakdown: Fast RSI 9 ({r9:.1f}) is trailing below RSI 14 ({r14:.1f})")
        if p_vwap < 0:
            reasons.append(f"Price (₹{price:.2f}) broke below Intraday VWAP by {p_vwap:.2f}%")
        if p_ema20 < 0:
            reasons.append(f"Trading below EMA20 by {p_ema20:.2f}%")
        if vol_ratio >= 1.2:
            reasons.append(f"High selling volume pressure ({vol_ratio:.1f}x average)")
        reasons.append(f"AI Model probability of downward drop is {conf:.1f}%.")
        return ". ".join(reasons)

    else:  # HOLD / WAIT (Do nothing)
        hold_reasons = []
        if conf < 60.0:
            hold_reasons.append(f"Low market conviction: Model confidence ({conf:.1f}%) is below the 60% trade entry threshold")
        
        if abs(r9 - 50) < 6 and abs(r14 - 50) < 6:
            hold_reasons.append(f"RSI is neutral (RSI9: {r9:.1f}, RSI14: {r14:.1f}), indicating sideways range-bound chop")
        elif r9 >= 75:
            hold_reasons.append(f"RSI 9 ({r9:.1f}) is in extreme overbought territory — high risk of pull-back")
        elif r9 <= 25:
            hold_reasons.append(f"RSI 9 ({r9:.1f}) is in extreme oversold territory — wait for confirmed reversal")

        if abs(p_vwap) < 0.2:
            hold_reasons.append("Price is oscillating right at VWAP with no directional expansion")

        if not hold_reasons:
            hold_reasons.append("Signals across multi-timeframe indicators do not align sufficiently for a high-probability trade")

        hold_reasons.append("Recommended action: Stay in cash / hold position and wait for clear volume breakout.")
        return ". ".join(hold_reasons)

