from typing import Dict, Any, Optional
from datetime import datetime, time
import zoneinfo
from config import Settings, settings as default_settings


def calculate_trade_brackets(
    entry_price: float,
    atr: float,
    side: str,
    config: Optional[Settings] = None
) -> Dict[str, Any]:
    """
    Computes strict 1:3 Risk-to-Reward Ratio Stop-Loss, Take-Profit target,
    and fixed 1,000 shares position sizing.
    For every ₹1 of stop-loss risk, the target is strictly ₹3 of profit.
    """
    cfg = config or default_settings
    entry_price = float(entry_price)
    atr = max(float(atr), 0.05)  # Guard against zero or negative ATR

    sl_mult = getattr(cfg, "stop_loss_atr_mult", 1.0)
    risk_per_share = round(max(0.10, sl_mult * atr), 2)
    # Strictly 3x the risk per share (1:3 Risk:Reward)
    reward_per_share = round(risk_per_share * 3.0, 2)

    if side.upper() in ("BUY", "LONG"):
        stop_loss = round(entry_price - risk_per_share, 2)
        target = round(entry_price + reward_per_share, 2)
    else:  # SELL / SHORT
        stop_loss = round(entry_price + risk_per_share, 2)
        target = round(entry_price - reward_per_share, 2)

    fixed_qty = int(getattr(cfg, "default_quantity", 1000))
    if fixed_qty <= 0:
        fixed_qty = 1000

    estimated_max_risk_rupees = round(fixed_qty * risk_per_share, 2)
    estimated_target_profit_rupees = round(fixed_qty * reward_per_share, 2)

    return {
        "side": side.upper(),
        "entry_price": round(entry_price, 2),
        "stop_loss": stop_loss,
        "target": target,
        "atr": round(atr, 2),
        "risk_per_share": risk_per_share,
        "reward_per_share": reward_per_share,
        "risk_reward_ratio": "1:3.00",
        "suggested_quantity": fixed_qty,
        "estimated_max_risk_rupees": estimated_max_risk_rupees,
        "estimated_target_profit_rupees": estimated_target_profit_rupees,
        "rr_multiple": 3.0,
    }


def check_safety_gate(
    data_timestamp: Optional[datetime],
    config: Optional[Settings] = None
) -> Dict[str, Any]:
    """
    Evaluates whether live/paper execution is safe to proceed:
      1. Emergency stop active check
      2. Data freshness check (age < max_data_age_seconds)
      3. Trading session hours check (IST 09:15 - 15:30 on weekdays)
    """
    cfg = config or default_settings

    if cfg.emergency_stop:
        return {
            "allowed": False,
            "reason": "EMERGENCY STOP is currently ACTIVE. All execution blocked.",
            "status": "EMERGENCY_STOPPED"
        }

    # Timezone check
    tz = zoneinfo.ZoneInfo(cfg.timezone)
    now = datetime.now(tz)

    # Market session check
    if cfg.enforce_market_hours:
        # Check weekday (Monday=0 ... Friday=4)
        if now.weekday() > 4:
            return {
                "allowed": False,
                "reason": f"Market closed (Weekend: {now.strftime('%A')}).",
                "status": "MARKET_CLOSED"
            }

        open_parts = [int(p) for p in cfg.market_open_time.split(":")]
        close_parts = [int(p) for p in cfg.market_close_time.split(":")]
        mkt_open = time(open_parts[0], open_parts[1])
        mkt_close = time(close_parts[0], close_parts[1])

        current_time = now.time()
        if not (mkt_open <= current_time <= mkt_close):
            return {
                "allowed": False,
                "reason": f"Outside market trading hours ({cfg.market_open_time} - {cfg.market_close_time} IST). Current time: {current_time.strftime('%H:%M:%S')}",
                "status": "MARKET_CLOSED"
            }

    # Data freshness check
    if data_timestamp:
        # Ensure data_timestamp is tz-aware in IST
        if data_timestamp.tzinfo is None:
            data_timestamp = data_timestamp.replace(tzinfo=tz)
        else:
            data_timestamp = data_timestamp.astimezone(tz)

        age_seconds = (now - data_timestamp).total_seconds()
        if cfg.enforce_market_hours and age_seconds > cfg.max_data_age_seconds:
            return {
                "allowed": False,
                "reason": f"Market data is stale ({int(age_seconds)}s old > threshold {cfg.max_data_age_seconds}s).",
                "status": "STALE_DATA"
            }

    return {
        "allowed": True,
        "reason": "Safety checks passed. Safe for execution.",
        "status": "READY"
    }

