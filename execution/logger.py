import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import zoneinfo
from config import Settings, settings as default_settings, BASE_DIR

ADVISORIES_LOG_FILE = BASE_DIR / "advisories.jsonl"
PREDICTIONS_LOG_FILE = BASE_DIR / "predictions.jsonl"

_recorded_prediction_timestamps: Set[str] = set()

# Initialize existing timestamps for predictions deduplication
if PREDICTIONS_LOG_FILE.exists():
    try:
        with open(PREDICTIONS_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        ts = obj.get("candle_timestamp")
                        if ts:
                            _recorded_prediction_timestamps.add(ts)
                    except Exception:
                        pass
    except Exception:
        pass


def record_analysis_log(
    signal: str,
    action: str,
    reason: str,
    indicators: Dict[str, Any],
    brackets: Optional[Dict[str, Any]] = None,
    order_result: Optional[Dict[str, Any]] = None,
    data_source: str = "UNKNOWN",
    session_state: str = "UNKNOWN",
    config: Optional[Settings] = None
) -> Dict[str, Any]:
    """Appends an immutable analysis record to eternal_paper_log.jsonl with data source and session state."""
    cfg = config or default_settings
    log_path = Path(cfg.paper_log_file)
    if not log_path.is_absolute():
        log_path = BASE_DIR / log_path

    tz = zoneinfo.ZoneInfo(cfg.timezone)
    now = datetime.now(tz)

    record = {
        "timestamp_ist": now.strftime("%Y-%m-%d %H:%M:%S"),
        "iso_time": now.isoformat(),
        "symbol": cfg.symbol,
        "exchange": cfg.exchange,
        "mode": cfg.agent_mode,
        "signal": signal,
        "action": action,
        "reason": reason,
        "data_source": data_source,
        "session_state": session_state,
        "price": indicators.get("price"),
        "indicators": indicators,
        "brackets": brackets or {},
        "order_result": order_result,
        "real_orders_enabled": cfg.real_orders_enabled,
    }

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Error writing to paper log: {e}")

    return record


def record_advisory_log(
    candle_timestamp: str,
    data_source: str,
    symbol: str,
    side: str,
    entry_price: float,
    stop_loss: Optional[float],
    target: Optional[float],
    quantity: int,
    directive: str,
    reason: str,
    session_state: str = "ACTIVE",
    model_version: Optional[str] = "2.0.0",
    config: Optional[Settings] = None,
    advisory_id: Optional[str] = None,
    risk_reward: str = "1:3.00",
    status: str = "ACTIVE",
    brackets: Optional[Dict[str, Any]] = None,
    exit_price: Optional[float] = None,
    exit_time: Optional[str] = None,
    realized_pnl: float = 0.0,
    realized_points: float = 0.0
) -> Optional[Dict[str, Any]]:
    """Appends an immutable record of an issued trade advisory to advisories.jsonl."""
    cfg = config or default_settings
    tz = zoneinfo.ZoneInfo(cfg.timezone)
    now = datetime.now(tz)

    adv_id = advisory_id or f"ADV-{now.strftime('%Y%m%d%H%M%S')}"

    record = {
        "id": adv_id,
        "logged_at": now.isoformat(),
        "candle_timestamp": candle_timestamp,
        "data_source": data_source,
        "symbol": symbol,
        "side": side,
        "entry_price": round(float(entry_price), 2),
        "stop_loss": round(float(stop_loss), 2) if stop_loss is not None else None,
        "target": round(float(target), 2) if target is not None else None,
        "risk_reward": risk_reward,
        "quantity": int(quantity),
        "status": status,
        "directive": directive,
        "reason": reason,
        "session_state": session_state,
        "model_version": model_version,
        "brackets": brackets or {},
        "exit_price": round(float(exit_price), 2) if exit_price is not None else None,
        "exit_time": exit_time,
        "realized_pnl": round(float(realized_pnl), 2),
        "realized_points": round(float(realized_points), 2),
    }

    try:
        with open(ADVISORIES_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record
    except Exception as e:
        print(f"Error writing advisory log: {e}")
        return None


def get_advisories(limit: int = 100) -> List[Dict[str, Any]]:
    """Returns past trade advisories in reverse-chronological order (newest first)."""
    if not ADVISORIES_LOG_FILE.exists():
        return []

    records = []
    try:
        with open(ADVISORIES_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        continue
    except Exception as e:
        print(f"Error reading advisories log: {e}")
        return []

    return list(reversed(records[-limit:]))


def get_active_advisory() -> Optional[Dict[str, Any]]:
    """Returns the most recent active advisory if currently open."""
    advisories = get_advisories(limit=50)
    for adv in advisories:
        if adv.get("status") == "ACTIVE":
            return adv
    return None


def update_advisory_status(
    advisory_id: str,
    new_status: str,
    exit_price: Optional[float] = None,
    exit_time: Optional[str] = None,
    realized_pnl: Optional[float] = None,
    realized_points: Optional[float] = None
) -> bool:
    """Updates the status and exit metrics for a specific advisory in advisories.jsonl."""
    if not ADVISORIES_LOG_FILE.exists():
        return False

    records = []
    updated = False
    try:
        with open(ADVISORIES_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        if record.get("id") == advisory_id:
                            record["status"] = new_status
                            if exit_price is not None:
                                record["exit_price"] = round(float(exit_price), 2)
                            if exit_time is not None:
                                record["exit_time"] = exit_time
                            if realized_pnl is not None:
                                record["realized_pnl"] = round(float(realized_pnl), 2)
                            if realized_points is not None:
                                record["realized_points"] = round(float(realized_points), 2)
                            updated = True
                        records.append(record)
                    except Exception:
                        continue

        if updated:
            with open(ADVISORIES_LOG_FILE, "w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return updated
    except Exception as e:
        print(f"Error updating advisory status: {e}")
        return False


def get_advisory_performance_summary() -> Dict[str, Any]:
    """Calculates win rate, target hit count, stop loss hit count, and total PnL from advisories."""
    if not ADVISORIES_LOG_FILE.exists():
        return {
            "total_advisories": 0,
            "active_count": 0,
            "target_hits": 0,
            "stop_loss_hits": 0,
            "day_end_exits": 0,
            "win_rate_pct": 0.0,
            "total_net_pnl": 0.0,
            "profit_factor": 0.0,
            "total_profit": 0.0,
            "total_loss": 0.0,
        }

    records = []
    try:
        with open(ADVISORIES_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        pass

    target_hits = 0
    sl_hits = 0
    day_close_hits = 0
    active_count = 0
    total_profit = 0.0
    total_loss = 0.0

    for r in records:
        status = r.get("status", "")
        pnl = float(r.get("realized_pnl", 0.0))
        if status == "ACTIVE":
            active_count += 1
        elif status == "TARGET_HIT":
            target_hits += 1
            if pnl > 0:
                total_profit += pnl
        elif status == "SL_HIT":
            sl_hits += 1
            if pnl < 0:
                total_loss += abs(pnl)
        elif status in ("DAY_END_CLOSE", "CANCELLED", "CLOSED"):
            day_close_hits += 1
            if pnl > 0:
                total_profit += pnl
            elif pnl < 0:
                total_loss += abs(pnl)

    closed_decisive = target_hits + sl_hits
    win_rate = round((target_hits / closed_decisive) * 100.0, 1) if closed_decisive > 0 else 0.0
    net_pnl = round(total_profit - total_loss, 2)
    profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else (99.0 if total_profit > 0 else 0.0)

    return {
        "total_advisories": len(records),
        "active_count": active_count,
        "target_hits": target_hits,
        "stop_loss_hits": sl_hits,
        "day_end_exits": day_close_hits,
        "win_rate_pct": win_rate,
        "total_net_pnl": net_pnl,
        "profit_factor": profit_factor,
        "total_profit": round(total_profit, 2),
        "total_loss": round(total_loss, 2),
    }


def record_prediction_log(
    candle_timestamp: str,
    data_source: str,
    model_version: str,
    feature_vector: Dict[str, Any],
    atr: Optional[float],
    side: str,
    entry: Optional[float],
    stop: Optional[float],
    target: Optional[float],
    probabilities: Dict[str, float],
    gate_decisions: Dict[str, Any],
    session_state: str = "ACTIVE",
    config: Optional[Settings] = None
) -> Optional[Dict[str, Any]]:
    """
    Logs prediction for closed candle to predictions.jsonl.
    Deduplicated by candle_timestamp. Never logs when the market session is CLOSED.
    """
    cfg = config or default_settings

    # Gate: never log when market is closed or on weekend
    if session_state in ("CLOSED", "PRE_OPEN"):
        return None

    # Gate: deduplicate by candle timestamp
    if candle_timestamp in _recorded_prediction_timestamps:
        return None

    tz = zoneinfo.ZoneInfo(cfg.timezone)
    now = datetime.now(tz)

    record = {
        "logged_at": now.isoformat(),
        "candle_timestamp": candle_timestamp,
        "data_source": data_source,
        "model_version": model_version,
        "feature_vector": feature_vector,
        "atr": atr,
        "side": side,
        "entry": entry,
        "stop": stop,
        "target": target,
        "probabilities": probabilities,
        "gate_decisions": gate_decisions,
        "session_state": session_state,
    }

    try:
        with open(PREDICTIONS_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        _recorded_prediction_timestamps.add(candle_timestamp)
        return record
    except Exception as e:
        print(f"Error writing prediction log: {e}")
        return None


def get_recent_logs(
    limit: int = 50,
    config: Optional[Settings] = None
) -> List[Dict[str, Any]]:
    """Returns the most recent log entries."""
    cfg = config or default_settings
    log_path = Path(cfg.paper_log_file)
    if not log_path.is_absolute():
        log_path = BASE_DIR / log_path

    if not log_path.exists():
        return []

    records = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return []

    return records[-limit:]


def clear_logs(config: Optional[Settings] = None) -> bool:
    """Safely archives the paper log file to preserve the audit trail."""
    cfg = config or default_settings
    log_path = Path(cfg.paper_log_file)
    if not log_path.is_absolute():
        log_path = BASE_DIR / log_path

    try:
        if log_path.exists():
            archive_dir = (log_path.parent if log_path.is_absolute() else BASE_DIR) / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_path = archive_dir / f"{log_path.stem}_{timestamp}{log_path.suffix}"
            shutil.move(str(log_path), str(archive_path))
        return True
    except Exception:
        return False
