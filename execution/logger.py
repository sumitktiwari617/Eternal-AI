import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import zoneinfo
from config import Settings, settings as default_settings


def record_analysis_log(
    signal: str,
    action: str,
    reason: str,
    indicators: Dict[str, Any],
    brackets: Optional[Dict[str, Any]] = None,
    order_result: Optional[Dict[str, Any]] = None,
    config: Optional[Settings] = None
) -> Dict[str, Any]:
    """Appends an immutable analysis record to the paper log file."""
    cfg = config or default_settings
    log_path = Path(cfg.paper_log_file)

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
        print(f"Error writing to log: {e}")

    return record


def get_recent_logs(
    limit: int = 50,
    config: Optional[Settings] = None
) -> List[Dict[str, Any]]:
    """Returns the most recent log entries."""
    cfg = config or default_settings
    log_path = Path(cfg.paper_log_file)

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
    """Clears the paper log file."""
    cfg = config or default_settings
    log_path = Path(cfg.paper_log_file)
    try:
        if log_path.exists():
            log_path.unlink()
        return True
    except Exception:
        return False

