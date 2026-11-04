from typing import Dict, Any, Optional
from datetime import datetime
import zoneinfo
import pandas as pd

from config import Settings, settings as default_settings, update_settings
from core.indicators import calculate_indicators
from core.strategy import evaluate_signal
from core.risk_manager import calculate_trade_brackets, check_safety_gate
from data.fetcher import fetch_historical_candles, fetch_latest_quote
from data.kotak_client import KotakNeoAdapter
from execution.logger import record_analysis_log


class ExecutionEngine:
    """
    Central operational engine for ETERNAL Trading Agent.
    Orchestrates market data fetching, safety gate verification,
    indicator processing, strategy decision, and paper/live logging.
    """

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or default_settings
        self.state = "IDLE"  # IDLE, RUNNING, PAUSED, EMERGENCY_STOPPED
        self.kotak = KotakNeoAdapter(self.config)
        self.last_decision = None
        self.last_analysis_time = None
        self.last_quote = None

    def start(self) -> Dict[str, Any]:
        if self.config.emergency_stop:
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
        return {
            "success": True,
            "message": "EMERGENCY STOP ACTIVATED! All operations and orders halted.",
            "state": self.state
        }

    def reset(self) -> Dict[str, Any]:
        update_settings({"emergency_stop": False})
        self.state = "IDLE"
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
          2. Evaluates safety gates
          3. Calculates technical indicators
          4. Evaluates strategy signal
          5. Calculates risk/bracket parameters
          6. Records paper log
        """
        tz = zoneinfo.ZoneInfo(self.config.timezone)
        now = datetime.now(tz)
        self.last_analysis_time = now.isoformat()

        # 1. Fetch market data
        df = fetch_historical_candles(
            symbol=self.config.symbol,
            range_period="5d",
            interval=self.config.timeframe,
            config=self.config
        )
        quote = fetch_latest_quote(symbol=self.config.symbol, config=self.config, kotak_adapter=self.kotak)
        self.last_quote = quote

        if df is None or df.empty or len(df) < 5:
            return {
                "success": False,
                "error": "Unable to fetch valid market candles.",
                "quote": quote,
                "signal": "WAIT",
                "reason": "Market candle feed unavailable."
            }

        # 2. Check safety gates
        latest_ts = df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
        safety = check_safety_gate(data_timestamp=latest_ts, config=self.config)

        # 3. Calculate indicators
        ind_df = calculate_indicators(
            df,
            ema_fast=self.config.ema_fast,
            ema_slow=self.config.ema_slow,
            rsi_period=self.config.rsi_period,
            atr_period=self.config.atr_period,
        )
        latest_row = ind_df.iloc[-1]

        # 4. Evaluate strategy
        decision = evaluate_signal(latest_row, self.config)
        signal = decision["signal"]
        action = decision["action"]
        reason = decision["reason"]
        indicators = decision["indicators"]

        # Override signal if safety gate blocked
        if not safety["allowed"]:
            signal = "WAIT"
            action = "SAFETY BLOCKED"
            reason = f"Safety Gate Blocked: {safety['reason']}"

        # 5. Calculate trade brackets
        price = float(latest_row["close"])
        atr = float(latest_row.get(f"ATR{self.config.atr_period}", 1.0))
        brackets = calculate_trade_brackets(
            entry_price=price,
            atr=atr,
            side=signal if signal in ("BUY", "SELL") else "BUY",
            config=self.config
        )

        # 6. Generate Actionable Human Guider Directives (Strict 1:3 Risk-to-Reward on 1,000 Shares)
        scrip = self.kotak.get_trading_symbol(self.config.symbol)
        qty = int(getattr(self.config, "default_quantity", 1000))
        target_price = brackets.get("target", price)
        stop_loss_price = brackets.get("stop_loss", price)
        risk_per_sh = brackets.get("risk_per_share", 0.0)
        reward_per_sh = brackets.get("reward_per_share", 0.0)
        total_risk = brackets.get("estimated_max_risk_rupees", qty * risk_per_sh)
        total_profit = brackets.get("estimated_target_profit_rupees", qty * reward_per_sh)

        # Enforce strict 1:3 Risk:Reward validation filter
        if signal in ("BUY", "SELL"):
            if risk_per_sh <= 0 or reward_per_sh < (risk_per_sh * 2.95):
                signal = "WAIT"
                action = "GUIDER: 1:3 RATIO FILTERED"
                reason += " | Setup filtered out: Does not satisfy strict 1:3 Risk-to-Reward ratio."
                directive = f"STATUS: WAIT / HOLD. Setup on {scrip} does not meet strict 1:3 profit-to-loss criteria."
                human_guidance = "Only trades with exact 1:3 Risk-to-Reward (₹1 risk vs ₹3 profit) are suggested. Wait for the next setup."
            elif signal == "BUY":
                directive = (
                    f"ACTION: BUY 1000 SHARES of {scrip} around ₹{price:.2f} | "
                    f"TARGET: ₹{target_price:.2f} (+₹{total_profit:,.2f}) | "
                    f"STOP LOSS: ₹{stop_loss_price:.2f} (-₹{total_risk:,.2f}) | "
                    f"STRICT 1:3 RISK-TO-REWARD"
                )
                human_guidance = (
                    f"Open Kotak Neo app -> Place BUY order for 1,000 shares of {scrip} around ₹{price:.2f}. "
                    f"Set Target at ₹{target_price:.2f} (Profit: ₹{total_profit:,.2f}) and "
                    f"Stop Loss at ₹{stop_loss_price:.2f} (Risk: ₹{total_risk:,.2f}). Profit is exactly 3x your Risk."
                )
                action = f"GUIDER ADVISORY: BUY 1000 {scrip} (1:3 R:R)"
            elif signal == "SELL":
                directive = (
                    f"ACTION: SELL / SHORT 1000 SHARES of {scrip} around ₹{price:.2f} | "
                    f"TARGET: ₹{target_price:.2f} (+₹{total_profit:,.2f}) | "
                    f"STOP LOSS: ₹{stop_loss_price:.2f} (-₹{total_risk:,.2f}) | "
                    f"STRICT 1:3 RISK-TO-REWARD"
                )
                human_guidance = (
                    f"Open Kotak Neo app -> Place SELL order for 1,000 shares of {scrip} around ₹{price:.2f}. "
                    f"Set Target at ₹{target_price:.2f} (Profit: ₹{total_profit:,.2f}) and "
                    f"Stop Loss at ₹{stop_loss_price:.2f} (Risk: ₹{total_risk:,.2f}). Profit is exactly 3x your Risk."
                )
                action = f"GUIDER ADVISORY: SELL 1000 {scrip} (1:3 R:R)"
        else:
            directive = f"STATUS: WAIT / HOLD. No high-probability 1:3 Risk-to-Reward setup on {scrip}."
            human_guidance = "Market is consolidating or Risk:Reward < 1:3. Stay in cash and wait for the next optimal 1:3 setup."
            action = "GUIDER: WAIT / HOLD (1:3 FILTER)"

        # 7. Log analysis record (Guider advisory log)
        log_entry = record_analysis_log(
            signal=signal,
            action=action,
            reason=reason,
            indicators=indicators,
            brackets=brackets,
            order_result=None,
            config=self.config
        )

        self.last_decision = {
            "timestamp": now.isoformat(),
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
