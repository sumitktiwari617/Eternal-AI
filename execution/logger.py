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
    config: Optional[Settings] = None
) -> Optional[Dict[str, Any]]:
    """Appends an immutable record of an issued trade advisory to advisories.jsonl."""
    cfg = config or default_settings
    tz = zoneinfo.ZoneInfo(cfg.timezone)
    now = datetime.now(tz)

    record = {
        "logged_at": now.isoformat(),
        "candle_timestamp": candle_timestamp,
        "data_source": data_source,
        "symbol": symbol,
        "side": side,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "target": target,
        "quantity": quantity,
        "directive": directive,
        "reason": reason,
        "session_state": session_state,
        "model_version": model_version,
    }

    try:
        with open(ADVISORIES_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record
    except Exception as e:
        print(f"Error writing advisory log: {e}")
        return None


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
