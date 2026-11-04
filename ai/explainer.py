from typing import Dict, Any


def generate_decision_reason(prediction: Dict[str, Any]) -> str:
    """
    Generates a strictly truthful, explainable justification for AI signal recommendations.
    Every statement is strictly conditional on measured feature values.
    Never states false relations between indicators.
    """
    signal = str(prediction.get("signal", "HOLD")).upper()
    conf = float(prediction.get("confidence", 50.0))
    price = float(prediction.get("latest_price", 0.0))
    feats = prediction.get("feature_snapshot", {})

    r9 = float(feats.get("rsi_9", 50.0))
    r14 = float(feats.get("rsi_14", 50.0))
    p_vwap = float(feats.get("price_to_vwap", 0.0))
    p_ema20 = float(feats.get("price_to_ema20", 0.0))
    vol_ratio = float(feats.get("volume_ratio", 1.0))

    clauses = []

    if signal == "BUY":
        if r9 > r14:
            clauses.append(f"Fast RSI 9 ({r9:.1f}) is leading above RSI 14 ({r14:.1f})")
        elif r9 < r14:
            clauses.append(f"Fast RSI 9 ({r9:.1f}) is below RSI 14 ({r14:.1f})")
        else:
            clauses.append(f"Fast RSI 9 ({r9:.1f}) equals RSI 14 ({r14:.1f})")

        if p_vwap > 0:
            clauses.append(f"Price (₹{price:.2f}) is holding {p_vwap:.2f}% above Intraday VWAP")
        elif p_vwap < 0:
            clauses.append(f"Price (₹{price:.2f}) is {abs(p_vwap):.2f}% below Intraday VWAP")

        if p_ema20 > 0:
            clauses.append(f"Trading above EMA20 by +{p_ema20:.2f}%")
        elif p_ema20 < 0:
            clauses.append(f"Trading below EMA20 by {abs(p_ema20):.2f}%")

        if vol_ratio >= 1.2:
            clauses.append(f"Volume expansion confirmed ({vol_ratio:.1f}x of 20-period average)")

        clauses.append(f"Model class confidence is {conf:.1f}% for BUY.")
        return ". ".join(clauses)

    elif signal == "SELL":
        if r9 < r14:
            clauses.append(f"Fast RSI 9 ({r9:.1f}) is trailing below RSI 14 ({r14:.1f})")
        elif r9 > r14:
            clauses.append(f"Fast RSI 9 ({r9:.1f}) is above RSI 14 ({r14:.1f})")
        else:
            clauses.append(f"Fast RSI 9 ({r9:.1f}) equals RSI 14 ({r14:.1f})")

        if p_vwap < 0:
            clauses.append(f"Price (₹{price:.2f}) is below Intraday VWAP by {abs(p_vwap):.2f}%")
        elif p_vwap > 0:
            clauses.append(f"Price (₹{price:.2f}) is {p_vwap:.2f}% above Intraday VWAP")

        if p_ema20 < 0:
            clauses.append(f"Trading below EMA20 by {abs(p_ema20):.2f}%")
        elif p_ema20 > 0:
            clauses.append(f"Trading above EMA20 by +{p_ema20:.2f}%")

        if vol_ratio >= 1.2:
            clauses.append(f"High selling volume activity ({vol_ratio:.1f}x average)")

        clauses.append(f"Model class confidence is {conf:.1f}% for SELL.")
        return ". ".join(clauses)

    else:  # HOLD / WAIT
        hold_clauses = []
        if conf < 60.0:
            hold_clauses.append(f"Model confidence ({conf:.1f}%) is below 60% trade entry threshold")

        if abs(r9 - 50) < 6 and abs(r14 - 50) < 6:
            hold_clauses.append(f"RSI is neutral (RSI9: {r9:.1f}, RSI14: {r14:.1f}), indicating range-bound chop")
        elif r9 >= 75:
            hold_clauses.append(f"RSI 9 ({r9:.1f}) is in overbought territory")
        elif r9 <= 25:
            hold_clauses.append(f"RSI 9 ({r9:.1f}) is in oversold territory")

        if abs(p_vwap) < 0.2:
            hold_clauses.append("Price is oscillating near VWAP with no directional expansion")

        if not hold_clauses:
            hold_clauses.append("Technical conditions do not satisfy trade entry criteria")

        hold_clauses.append("Action: Stand by in cash and wait for next valid setup.")
        return ". ".join(hold_clauses)
