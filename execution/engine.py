from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import zoneinfo
import pandas as pd

from config import Settings, settings as default_settings, update_settings, BASE_DIR
from core.indicators import calculate_indicators
from core.strategy import evaluate_signal
from core.risk_manager import calculate_trade_brackets, check_safety_gate
from data.fetcher import fetch_historical_candles, fetch_latest_quote, DataUnavailableError
from data.kotak_client import KotakNeoAdapter
from execution.logger import record_analysis_log, record_advisory_log


def parse_timeframe_minutes(tf: str) -> int:
    """Parses timeframe string ('5m', '15m', '1h') to integer minutes."""
    tf = tf.strip().lower()
    if tf.endswith("m"):
        return max(1, int(tf[:-1]))
    if tf.endswith("h"):
        return max(1, int(tf[:-1]) * 60)
    if tf.endswith("d"):
        return max(1, int(tf[:-1]) * 1440)
    return 5


class ExecutionEngine:
    """
    Central operational engine for ETERNAL Trading Agent.
    Strictly Read-Only Guider & Advisory System.
    Real orders are permanently disabled.
    """

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or default_settings
        self.state = "IDLE"  # IDLE, RUNNING, PAUSED, EMERGENCY_STOPPED
        self.kotak = KotakNeoAdapter(self.config)
        self.last_decision = None
        self.last_analysis_time = None
        self.last_quote = None

        # Check persistent emergency stop flag on startup
        if self._get_lock_path().exists() or self.config.emergency_stop:
            self.state = "EMERGENCY_STOPPED"
            update_settings({"emergency_stop": True})

    def _get_lock_path(self) -> Path:
        lock_path = Path(self.config.emergency_stop_file)
        if not lock_path.is_absolute():
            return BASE_DIR / lock_path
        return lock_path

    def start(self) -> Dict[str, Any]:
        if self.config.emergency_stop or self._get_lock_path().exists():
            self.state = "EMERGENCY_STOPPED"
            return {
                "success": False,
                "error": "Cannot start agent while EMERGENCY STOP is active. Please reset first.",
                "state": self.state
            }
        self.state = "RUNNING"
        return {"success": True, "message": "Agent started and active.", "state": self.state}

    def pause(self) -> Dict[str, Any]:
        self.state = "PAUSED"
        return {"success": True, "message": "Agent paused.", "state": self.state}

    def emergency_stop(self) -> Dict[str, Any]:
        self.state = "EMERGENCY_STOPPED"
        update_settings({"emergency_stop": True})
        try:
            self._get_lock_path().write_text("EMERGENCY_STOPPED", encoding="utf-8")
        except Exception:
            pass
        return {
            "success": True,
            "message": "EMERGENCY STOP ACTIVATED! All operations and orders halted.",
            "state": self.state
        }

    def reset(self) -> Dict[str, Any]:
        update_settings({"emergency_stop": False})
        self.state = "IDLE"
        try:
            lock = self._get_lock_path()
            if lock.exists():
                lock.unlink()
        except Exception:
            pass
        return {
            "success": True,
            "message": "Emergency stop cleared. Agent returned to IDLE state.",
            "state": self.state
        }

    def set_mode(self, mode: str) -> Dict[str, Any]:
        mode_upper = mode.upper()
        if mode_upper in ("GUIDER", "COPILOT", "ADVISORY", "SIGNALS_ONLY"):
            update_settings({"agent_mode": "GUIDER", "real_orders_enabled": False})
        elif mode_upper == "PAPER":
            update_settings({"agent_mode": "PAPER", "real_orders_enabled": False})
        else:
            return {"success": False, "error": f"Invalid mode: {mode}. Allowed modes are GUIDER or PAPER."}

        return {"success": True, "message": f"Agent mode set to {self.config.agent_mode}.", "mode": self.config.agent_mode}

    def run_single_analysis(self) -> Dict[str, Any]:
        """
        Executes a single market inspection and decision cycle:
          1. Fetches latest candles & quote
          2. Enforces closed-candle only processing (drops in-progress candle)
          3. Evaluates safety and market session gates
          4. Computes indicators and strategy rules
          5. Computes risk-capped brackets (brackets: null if HOLD/WAIT)
          6. Records immutable audit logs
        """
        tz = zoneinfo.ZoneInfo(self.config.timezone)
        now = datetime.now(tz)
        self.last_analysis_time = now.isoformat()
        tf_mins = parse_timeframe_minutes(self.config.timeframe)

        quote = fetch_latest_quote(symbol=self.config.symbol, config=self.config, kotak_adapter=self.kotak)
        self.last_quote = quote

        # 0. Emergency Stop Guard
        if self.config.emergency_stop or self.state == "EMERGENCY_STOPPED" or self._get_lock_path().exists():
            self.state = "EMERGENCY_STOPPED"
            self.last_decision = {
                "timestamp": now.isoformat(),
                "symbol": self.config.symbol,
                "mode": self.config.agent_mode,
                "signal": "HOLD",
                "action": "EMERGENCY_STOPPED",
                "directive": "EMERGENCY STOP IS ACTIVE. Operations halted.",
                "human_guidance": "Emergency stop is active. Reset to resume.",
                "reason": "EMERGENCY_STOPPED",
                "safety": {"allowed": False, "reason": "Emergency stop is active", "status": "EMERGENCY_STOPPED"},
                "quote": quote,
                "indicators": None,
                "brackets": None,
                "data_source": "NONE",
                "real_orders_enabled": False,
            }
            return {
                "success": False,
                "advisory_refused": True,
                "error": "Emergency stop is active. No advisories issued.",
                "state": self.state,
                "decision": self.last_decision
            }

        # 1. Fetch candles
        try:
            df = fetch_historical_candles(
                symbol=self.config.symbol,
                range_period="5d",
                interval=self.config.timeframe,
                config=self.config
            )
        except DataUnavailableError as e:
            df = None
            data_err = str(e)
        except Exception as e:
            df = None
            data_err = str(e)

        # 2. Guard: Data source validation
        data_source = df.attrs.get("source", "UNKNOWN") if df is not None else "NONE"
        is_live_source = data_source in ("YAHOO", "KOTAK_NEO_LIVE")

        if df is None or df.empty or len(df) < 5 or not is_live_source:
            self.last_decision = {
                "timestamp": now.isoformat(),
                "symbol": self.config.symbol,
                "mode": self.config.agent_mode,
                "signal": "WAIT",
                "action": "DATA UNAVAILABLE",
                "directive": "STATUS: WAIT. Market data is unavailable or not from a validated live source.",
                "human_guidance": "Data feed unavailable or outside live market connection. Stand by.",
                "reason": "DATA UNAVAILABLE / NOT LIVE",
                "safety": {"allowed": False, "reason": "Data source is not live or unavailable", "status": "DATA_UNAVAILABLE"},
                "quote": quote,
                "indicators": None,
                "brackets": None,
                "data_source": data_source,
                "real_orders_enabled": False,
            }
            return {
                "success": False,
                "error": "DATA UNAVAILABLE / NOT LIVE",
                "quote": quote,
                "signal": "WAIT",
                "reason": "DATA UNAVAILABLE / NOT LIVE",
                "decision": self.last_decision,
            }

        # 3. Closed candles only: Drop in-progress bar
        latest_candle_start = df.index[-1]
        if hasattr(latest_candle_start, "tzinfo") and latest_candle_start.tzinfo is None:
            latest_candle_start = latest_candle_start.replace(tzinfo=tz)

        candle_end_time = latest_candle_start + timedelta(minutes=tf_mins)
        if candle_end_time > now:
            # Drop incomplete candle
            if len(df) > 1:
                df = df.iloc[:-1]
                latest_candle_start = df.index[-1]
                if hasattr(latest_candle_start, "tzinfo") and latest_candle_start.tzinfo is None:
                    latest_candle_start = latest_candle_start.replace(tzinfo=tz)
                candle_end_time = latest_candle_start + timedelta(minutes=tf_mins)

        # 4. Check safety & session gate (staleness evaluated from candle end time)
        safety = check_safety_gate(data_timestamp=candle_end_time, config=self.config)
        session_state = safety.get("session_state", "UNKNOWN")

        # 5. Calculate indicators
        ind_df = calculate_indicators(
            df,
            ema_fast=self.config.ema_fast,
            ema_slow=self.config.ema_slow,
            rsi_period=self.config.rsi_period,
            atr_period=self.config.atr_period,
        )
        latest_row = ind_df.iloc[-1]

        # 6. Evaluate strategy signal
        decision = evaluate_signal(latest_row, self.config)
        signal = decision["signal"]
        action = decision["action"]
        reason = decision["reason"]
        indicators = decision["indicators"]

        # Override signal if safety gate blocked
        if not safety["allowed"]:
            signal = "WAIT"
            action = f"SAFETY: {session_state}"
            reason = f"Safety Gate Blocked: {safety['reason']}"

        # 7. Calculate brackets (only when signal is BUY or SELL, otherwise brackets: None)
        price = float(latest_row["close"])
        atr = float(latest_row.get(f"ATR{self.config.atr_period}", 1.0))
        scrip = self.kotak.get_trading_symbol(self.config.symbol)
        brackets = None

        if signal in ("BUY", "SELL") and safety["allowed"]:
            brackets = calculate_trade_brackets(
                entry_price=price,
                atr=atr,
                side=signal,
                config=self.config
            )

            if brackets is None:
                # Risk per trade cap was exceeded or size < 1
                signal = "WAIT"
                action = "RISK CAP FILTERED"
                reason += " | Trade filtered: Position risk would exceed max_risk_per_trade_rupees."
                directive = f"STATUS: WAIT / HOLD. Setup on {scrip} exceeds allowable risk cap."
                human_guidance = "Risk exceeds configured cap. Wait for volatility contraction."
            else:
                qty = brackets["suggested_quantity"]
                target_price = brackets["target"]
                stop_loss_price = brackets["stop_loss"]
                total_risk = brackets["estimated_max_risk_rupees"]
                total_profit = brackets["estimated_target_profit_rupees"]

                directive = (
                    f"ACTION: {signal} {qty} SHARES of {scrip} around ₹{price:.2f} | "
                    f"TARGET: ₹{target_price:.2f} (+₹{total_profit:,.2f}) | "
                    f"STOP LOSS: ₹{stop_loss_price:.2f} (-₹{total_risk:,.2f}) | "
                    f"STRICT 1:3 RISK-TO-REWARD"
                )
                human_guidance = (
                    f"Open Kotak Neo app -> Place {signal} order for {qty:,} shares of {scrip} around ₹{price:.2f}. "
                    f"Set Target at ₹{target_price:.2f} (Profit: ₹{total_profit:,.2f}) and "
                    f"Stop Loss at ₹{stop_loss_price:.2f} (Risk: ₹{total_risk:,.2f})."
                )
                action = f"GUIDER ADVISORY: {signal} {qty} {scrip} (1:3 R:R)"

                # Record issued advisory to advisories.jsonl
                record_advisory_log(
                    candle_timestamp=latest_candle_start.isoformat(),
                    data_source=data_source,
                    symbol=self.config.symbol,
                    side=signal,
                    entry_price=price,
                    stop_loss=stop_loss_price,
                    target=target_price,
                    quantity=qty,
                    directive=directive,
                    reason=reason,
                    session_state=session_state,
                    config=self.config
                )
        else:
            brackets = None
            directive = f"STATUS: WAIT / HOLD. No active trade advisory for {scrip}."
            human_guidance = "Market is in waiting period or conditions are not met. Stand by in cash."
            if signal != "WAIT":
                signal = "WAIT"

        # 8. Record paper journal log
        record_analysis_log(
            signal=signal,
            action=action,
            reason=reason,
            indicators=indicators,
            brackets=brackets,
            order_result=None,
            data_source=data_source,
            session_state=session_state,
            config=self.config
        )

        self.last_decision = {
            "timestamp": now.isoformat(),
            "candle_timestamp": latest_candle_start.isoformat(),
            "symbol": self.config.symbol,
            "mode": self.config.agent_mode,
            "signal": signal,
            "action": action,
            "directive": directive,
            "human_guidance": human_guidance,
            "reason": reason,
            "safety": safety,
            "quote": quote,
            "indicators": indicators,
            "brackets": brackets,
            "data_source": data_source,
            "session_state": session_state,
            "real_orders_enabled": False,
        }

        return {
            "success": True,
            "decision": self.last_decision,
        }

    def get_dashboard_state(self) -> Dict[str, Any]:
        """Provides full real-time operational telemetry for UI/CLI."""
        tz = zoneinfo.ZoneInfo(self.config.timezone)
        now = datetime.now(tz)

        return {
            "agent_state": self.state,
            "agent_mode": self.config.agent_mode,
            "emergency_stop": self.config.emergency_stop,
            "real_orders_enabled": self.config.real_orders_enabled,
            "symbol": self.config.symbol,
            "exchange": self.config.exchange,
            "timeframe": self.config.timeframe,
            "timezone": self.config.timezone,
            "server_time_ist": now.strftime("%Y-%m-%d %H:%M:%S"),
            "last_analysis_time": self.last_analysis_time,
            "last_quote": self.last_quote,
            "last_decision": self.last_decision,
            "kotak_status": self.kotak.status(),
        }


# Global engine singleton
engine = ExecutionEngine()
