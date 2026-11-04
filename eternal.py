# -*- coding: utf-8 -*-
"""
ETERNAL AI TRADING AGENT — PRO
Unified Intraday Momentum & Quantitative Trading Engine
Equities & Derivatives (NSE / Kotak Neo / Yahoo Finance)

This file integrates all fixed core modules (indicators, strategy, risk management,
data pipeline, backtester, execution engine, CLI, and FastAPI Web Dashboard).
Zero hardcoded values: all settings are driven dynamically via config.py and .env.
"""

import sys
import os
import json
from datetime import datetime, time
import zoneinfo
from typing import Dict, Any, Optional

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pandas as pd
import numpy as np

# Import modular components
from config import settings, update_settings, Settings
from core.indicators import calculate_indicators
from core.strategy import evaluate_signal
from core.risk_manager import calculate_trade_brackets, check_safety_gate
from core.backtester import run_backtest
from data.fetcher import fetch_historical_candles, fetch_latest_quote, generate_synthetic_candles
from data.kotak_client import KotakNeoAdapter, HAS_NEO_SDK
from execution.engine import engine, ExecutionEngine
from execution.logger import record_analysis_log, get_recent_logs, clear_logs


# =====================================================================
# BACKWARD-COMPATIBLE FUNCTION APIS (WITH FULL BUG FIXES)
# =====================================================================

def calculate_risk(entry: float, stop_loss: float, quantity: int) -> Dict[str, Any]:
    """
    Computes absolute Rupee risk per share and total capital at risk.
    Guards against negative or zero entries.
    """
    entry = float(entry)
    stop_loss = float(stop_loss)
    quantity = int(quantity)

    if entry <= 0 or stop_loss <= 0 or quantity <= 0:
        raise ValueError("Entry, stop-loss, and quantity must be strictly positive numbers.")

    risk_per_share = abs(entry - stop_loss)
    total_risk = risk_per_share * quantity

    return {
        "entry_reference": round(entry, 2),
        "stop_loss_reference": round(stop_loss, 2),
        "quantity": quantity,
        "risk_per_share": round(risk_per_share, 2),
        "estimated_risk_rupees": round(total_risk, 2),
        "note": "Pre-trade risk estimate; statutory charges, slippage, and gap-risk excluded."
    }


def safe_signal_gate(data_is_fresh: bool, market_session_confirmed: bool, indicators_ready: bool) -> tuple:
    """
    Multi-gate safety filter. All criteria must pass before analysis is permitted.
    """
    if not data_is_fresh:
        return "WAIT", "Market data is stale or unverified."
    if not market_session_confirmed and settings.enforce_market_hours:
        return "WAIT", "Outside confirmed market trading session hours."
    if not indicators_ready:
        return "WAIT", "Technical indicators are still warming up or incomplete."
    return "READY_FOR_ANALYSIS", "All safety gates passed. Ready for signal evaluation."


def check_data_freshness(data_timestamp: Optional[datetime], max_age_seconds: int = 180) -> bool:
    """
    Verifies that the incoming candle timestamp is within the freshness threshold.
    """
    if not data_timestamp:
        return False

    tz = zoneinfo.ZoneInfo(settings.timezone)
    now = datetime.now(tz)

    if data_timestamp.tzinfo is None:
        data_timestamp = data_timestamp.replace(tzinfo=tz)
    else:
        data_timestamp = data_timestamp.astimezone(tz)

    age = (now - data_timestamp).total_seconds()
    return age <= max_age_seconds


def check_analysis_readiness(data_timestamp: Optional[datetime], df: pd.DataFrame, market_session_confirmed: bool = False) -> Dict[str, Any]:
    """
    Comprehensive readiness check before running strategy decisions.
    """
    fresh = check_data_freshness(data_timestamp, max_age_seconds=settings.max_data_age_seconds)
    has_candles = df is not None and not df.empty and len(df) >= 20
    gate_status, reason = safe_signal_gate(fresh, market_session_confirmed, has_candles)

    return {
        "ready": gate_status == "READY_FOR_ANALYSIS",
        "data_is_fresh": fresh,
        "candles_available": len(df) if df is not None else 0,
        "gate_status": gate_status,
        "reason": reason
    }


def record_analysis(signal: str, reason: str, data_timestamp: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Appends an analysis decision to the paper trading journal.
    """
    ind = details.get("indicators", {}) if details else {}
    brk = details.get("brackets", {}) if details else {}
    return record_analysis_log(
        signal=signal,
        action=f"{signal} BIAS" if signal in ("BUY", "SELL") else "WAIT",
        reason=reason,
        indicators=ind,
        brackets=brk,
        config=settings
    )


def emergency_stop() -> Dict[str, Any]:
    """Triggers global emergency stop kill-switch."""
    return engine.emergency_stop()


def manual_reset() -> Dict[str, Any]:
    """Clears emergency stop and returns agent to idle state."""
    return engine.reset()


def start_agent() -> Dict[str, Any]:
    """Starts agent monitoring."""
    return engine.start()


def show_status():
    """Prints terminal status report."""
    from cli import cmd_status
    cmd_status()


# =====================================================================
# CLI / ENTRYPOINT DISPATCHER
# =====================================================================

def main():
    """
    Main entrypoint: parses command-line arguments and launches CLI or server.
    """
    from cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
