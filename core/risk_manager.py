from typing import Dict, Any, Optional, Tuple, Set
from datetime import datetime, time
from pathlib import Path
import math
import json
import zoneinfo
from config import Settings, settings as default_settings, BASE_DIR


def load_market_holidays(holiday_file: Optional[str] = None) -> Set[str]:
    """
    Loads user-maintained market holidays from JSON file in YYYY-MM-DD format.
    Ignores comment lines starting with '_'.
    """
    path_str = holiday_file or default_settings.market_holidays_file
    p = Path(path_str)
    if not p.is_absolute():
        p = BASE_DIR / p

    holidays: Set[str] = set()
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, str) and not item.startswith("_"):
                            holidays.add(item.strip())
        except Exception:
            pass
    return holidays


def parse_time_str(time_str: str) -> time:
    """Parses 'HH:MM' string to datetime.time."""
    parts = [int(p) for p in time_str.split(":")]
    return time(parts[0], parts[1])


def get_market_session_state(
    current_dt: datetime,
    config: Optional[Settings] = None
) -> Tuple[str, bool, str]:
    """
    Evaluates market session state based on configured trading windows (IST).
    Returns (session_state, can_enter_trades, explanation_reason).

    Session States:
      PRE_OPEN:          Before 09:15 IST (Weekdays) -> No new trades
      OPENING_DISCOVERY: 09:15 - 09:30 IST (Hypothesis: high opening volatility) -> WAIT
      ACTIVE:            09:30 - 14:30 IST (Hypothesis: core intraday liquidity window) -> Eligible
      WIND_DOWN:         14:30 - 15:30 IST (Hypothesis: no new entries to avoid gap risk) -> No new trades
      CLOSED:            Weekends, Market Holidays, or after 15:30 IST -> Closed
    """
    cfg = config or default_settings

    # 1. Weekend Check (Monday=0 ... Sunday=6)
    if current_dt.weekday() > 4:
        return "CLOSED", False, f"Market closed (Weekend: {current_dt.strftime('%A')})."

    # 2. Holiday Check
    date_str = current_dt.strftime("%Y-%m-%d")
    holidays = load_market_holidays(cfg.market_holidays_file)
    if date_str in holidays:
        return "CLOSED", False, f"Market closed today for scheduled holiday ({date_str})."

    # 3. Time Windows Check
    t = current_dt.time()
    t_open = parse_time_str(cfg.market_open_time)
    t_discovery_end = parse_time_str(cfg.opening_discovery_end_time)
    t_no_new_entries = parse_time_str(cfg.no_new_entries_time)
    t_close = parse_time_str(cfg.market_close_time)

    if t < t_open:
        return "PRE_OPEN", False, f"Pre-market session before {cfg.market_open_time} IST. Current time: {t.strftime('%H:%M:%S')}"

    if t_open <= t < t_discovery_end:
        return "OPENING_DISCOVERY", False, f"Opening discovery session ({cfg.market_open_time}-{cfg.opening_discovery_end_time} IST): high opening volatility, wait for price stabilization."

    if t_discovery_end <= t < t_no_new_entries:
        return "ACTIVE", True, "Active market session: Intraday trade signals permitted."

    if t_no_new_entries <= t < t_close:
        return "WIND_DOWN", False, f"Wind-down session ({cfg.no_new_entries_time}-{cfg.market_close_time} IST): No new intraday entries permitted before market close."

    return "CLOSED", False, f"Market closed after {cfg.market_close_time} IST. Current time: {t.strftime('%H:%M:%S')}"


def calculate_trade_brackets(
    entry_price: float,
    atr: float,
    side: str,
    config: Optional[Settings] = None
) -> Optional[Dict[str, Any]]:
    """
    Computes strict Risk-to-Reward Ratio Stop-Loss, Take-Profit target,
    and risk-capped position sizing.

    Enforces max_risk_per_trade_rupees:
      qty = min(default_quantity, floor(max_risk / risk_per_share))
      If qty < 1 -> returns None.
    If side is not BUY or SELL -> returns None.
    """
    cfg = config or default_settings
    side_clean = str(side).upper()

    if side_clean not in ("BUY", "LONG", "SELL", "SHORT"):
        return None

    entry_price = float(entry_price)
    atr = max(float(atr), 0.05)

    sl_mult = getattr(cfg, "stop_loss_atr_mult", 1.0)
    tp_mult = getattr(cfg, "target_atr_mult", 3.0)

    risk_per_share = round(max(0.05, sl_mult * atr), 2)
    reward_per_share = round(risk_per_share * tp_mult, 2)

    if side_clean in ("BUY", "LONG"):
        action_side = "BUY"
        stop_loss = round(entry_price - risk_per_share, 2)
        target = round(entry_price + reward_per_share, 2)
    else:
        action_side = "SELL"
        stop_loss = round(entry_price + risk_per_share, 2)
        target = round(entry_price - reward_per_share, 2)

    max_risk_rupees = float(getattr(cfg, "max_risk_per_trade_rupees", 2000.0))
    default_qty = int(getattr(cfg, "default_quantity", 1000))

    if risk_per_share <= 0:
        return None

    risk_capped_qty = math.floor(max_risk_rupees / risk_per_share)
    qty = min(default_qty, risk_capped_qty)

    if qty < 1:
        return None

    estimated_max_risk_rupees = round(qty * risk_per_share, 2)
    estimated_target_profit_rupees = round(qty * reward_per_share, 2)

    return {
        "side": action_side,
        "entry_price": round(entry_price, 2),
        "stop_loss": stop_loss,
        "target": target,
        "atr": round(atr, 2),
        "risk_per_share": risk_per_share,
        "reward_per_share": reward_per_share,
        "risk_reward_ratio": f"1:{tp_mult:.2f}",
        "suggested_quantity": qty,
        "estimated_max_risk_rupees": estimated_max_risk_rupees,
        "estimated_target_profit_rupees": estimated_target_profit_rupees,
        "rr_multiple": tp_mult,
    }


def check_safety_gate(
    data_timestamp: Optional[datetime],
    config: Optional[Settings] = None
) -> Dict[str, Any]:
    """
    Evaluates whether live/paper execution is safe to proceed:
      1. Emergency stop active check
      2. Market session hours and holiday gate
      3. Data freshness check (age < max_data_age_seconds, computed from closed candle end time)
    """
    cfg = config or default_settings

    if cfg.emergency_stop:
        return {
            "allowed": False,
            "session_state": "EMERGENCY_STOPPED",
            "reason": "EMERGENCY STOP is currently ACTIVE. All execution blocked.",
            "status": "EMERGENCY_STOPPED"
        }

    tz = zoneinfo.ZoneInfo(cfg.timezone)
    now = datetime.now(tz)

    session_state, can_enter, session_reason = get_market_session_state(now, cfg)

    if cfg.enforce_market_hours and not can_enter:
        return {
            "allowed": False,
            "session_state": session_state,
            "reason": session_reason,
            "status": f"MARKET_{session_state}"
        }

    # Data freshness check (from candle end timestamp)
    if data_timestamp:
        if data_timestamp.tzinfo is None:
            data_timestamp = data_timestamp.replace(tzinfo=tz)
        else:
            data_timestamp = data_timestamp.astimezone(tz)

        age_seconds = (now - data_timestamp).total_seconds()
        if age_seconds < 0:
            age_seconds = 0.0

        if cfg.enforce_market_hours and age_seconds > cfg.max_data_age_seconds:
            return {
                "allowed": False,
                "session_state": session_state,
                "reason": f"Market data is stale ({int(age_seconds)}s since candle close > threshold {cfg.max_data_age_seconds}s).",
                "status": "STALE_DATA"
            }

    return {
        "allowed": True,
        "session_state": session_state,
        "reason": "Safety checks passed. Safe for execution.",
        "status": "READY"
    }
