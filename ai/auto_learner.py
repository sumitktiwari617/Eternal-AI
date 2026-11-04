import os
import json
import asyncio
from pathlib import Path
from datetime import datetime, time
import zoneinfo
from typing import Dict, Any, List, Optional
import pandas as pd

from config import settings
from ai.model import ai_model
from ai.feature_extractor import prepare_training_dataset
from data.fetcher import fetch_historical_candles
from execution.logger import record_prediction_log
from core.risk_manager import get_market_session_state


LEARNING_HISTORY_FILE = Path(__file__).resolve().parent.parent / "model_learning_history.json"
PREDICTIONS_LOG_FILE = Path(__file__).resolve().parent.parent / "daily_predictions.jsonl"


class AutonomousLearner:
    """
    Autonomous Background Self-Learning Pipeline:
      1. Zero fabricated historical seeds. Starts with empty history or strictly measured data.
      2. One-time migration to remove unmeasured seeds and deduplicate history with backup.
      3. At 3:30 PM IST (Market Close), retrains model weights locally.
    """

    def __init__(self):
        self.history_file = LEARNING_HISTORY_FILE
        self.predictions_file = PREDICTIONS_LOG_FILE
        self.is_training_in_progress = False
        self.last_trained_date: Optional[str] = None
        self._init_history()

    def _init_history(self):
        """Initializes learning history with zero fabricated numbers and runs one-time cleanup migration."""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    raw_history = json.load(f)
            except Exception:
                raw_history = []

            # Check if migration is needed (presence of unmeasured seeds or duplicates)
            has_unmeasured = any(h.get("source") != "measured" for h in raw_history if isinstance(h, dict))
            if has_unmeasured or len(raw_history) > 0:
                # Write backup before mutating
                bak_path = self.history_file.with_suffix(".json.bak")
                if not bak_path.exists():
                    try:
                        with open(bak_path, "w", encoding="utf-8") as bf:
                            json.dump(raw_history, bf, indent=2)
                    except Exception:
                        pass

                # Filter for strictly measured rows and deduplicate by (date, event)
                seen_keys = set()
                clean_history = []
                for item in raw_history:
                    if not isinstance(item, dict):
                        continue
                    if item.get("source") != "measured":
                        continue
                    key = (item.get("date"), item.get("event"))
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    clean_history.append(item)

                self._save_history(clean_history)
                if clean_history:
                    self.last_trained_date = clean_history[-1].get("date")
        else:
            # Fresh install: Start with an empty list. Zero fake seeds.
            self._save_history([])

    def _save_history(self, history: List[Dict[str, Any]]):
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    def get_learning_history(self) -> List[Dict[str, Any]]:
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def ensure_initial_training(self) -> Dict[str, Any]:
        """
        Ensures the AI model is trained on historical data if model is not already loaded.
        """
        if ai_model.model is not None:
            return {
                "status": "READY",
                "accuracy": ai_model.last_accuracy,
                "samples": ai_model.total_samples,
                "message": "AI Model loaded and operational."
            }

        print("🤖 [Autonomous AI Learner] First-time setup: Fetching historical data for initial training...")
        df = fetch_historical_candles(
            symbol=settings.symbol,
            range_period="60d",
            interval=settings.timeframe,
            config=settings
        )

        res = ai_model.train(df)
        tz = zoneinfo.ZoneInfo(settings.timezone)
        today_str = datetime.now(tz).strftime("%Y-%m-%d")
        self.last_trained_date = today_str

        # Update learning log with source="measured"
        history = self.get_learning_history()
        history.append({
            "date": today_str,
            "accuracy": res["accuracy"],
            "samples": res["samples"],
            "source": "measured",
            "event": "Initial Walk-Forward Training Complete"
        })
        self._save_history(history)

        print(f"✅ [Autonomous AI Learner] Model trained successfully! Measured validation accuracy: {res['accuracy']}%")
        return res

    def record_prediction(self, prediction: Dict[str, Any], current_price: float, candle_timestamp: Optional[str] = None):
        """
        Logs prediction to audit log only during active market sessions on closed candles.
        Replaces un-audited duplicate logging.
        """
        tz = zoneinfo.ZoneInfo(settings.timezone)
        now = datetime.now(tz)
        session_state, can_enter, _ = get_market_session_state(now, settings)

        # Do not log outside market hours
        if session_state in ("CLOSED", "PRE_OPEN") and settings.enforce_market_hours:
            return

        ts = candle_timestamp or prediction.get("candle_timestamp") or now.isoformat()
        feats = prediction.get("feature_snapshot", {})
        probs = prediction.get("probabilities", {})

        record_prediction_log(
            candle_timestamp=ts,
            data_source="LIVE",
            model_version="2.0.0",
            feature_vector=feats,
            atr=feats.get("atr_normalized"),
            side=prediction.get("signal", "HOLD"),
            entry=current_price,
            stop=prediction.get("brackets", {}).get("stop_loss") if prediction.get("brackets") else None,
            target=prediction.get("brackets", {}).get("target") if prediction.get("brackets") else None,
            probabilities=probs,
            gate_decisions={"session_state": session_state, "confidence": prediction.get("confidence")},
            session_state=session_state,
            config=settings
        )

    def run_daily_retrain_cycle(self) -> Dict[str, Any]:
        """
        Executes daily retraining:
          1. Fetches updated historical corpus.
          2. Retrains model weights.
          3. Evaluates measured accuracy.
          4. Updates persistent history with measured source.
        """
        if self.is_training_in_progress:
            return {"status": "SKIPPED", "message": "Training already in progress."}

        self.is_training_in_progress = True
        try:
            print("🔄 [Autonomous AI Learner] Market closed: Running daily walk-forward retraining...")
            df = fetch_historical_candles(
                symbol=settings.symbol,
                range_period="60d",
                interval=settings.timeframe,
                config=settings
            )

            res = ai_model.train(df)
            tz = zoneinfo.ZoneInfo(settings.timezone)
            today_str = datetime.now(tz).strftime("%Y-%m-%d")
            self.last_trained_date = today_str

            # Update history log with source="measured"
            history = self.get_learning_history()
            history.append({
                "date": today_str,
                "accuracy": res["accuracy"],
                "samples": res["samples"],
                "source": "measured",
                "event": f"Daily Auto-Learning Update (Trained on {res['samples']} candles)"
            })
            self._save_history(history)

            print(f"🏆 [Autonomous AI Learner] Day-by-Day Learning complete! Updated Model Accuracy: {res['accuracy']}%")
            return res
        finally:
            self.is_training_in_progress = False

    async def background_market_close_daemon(self):
        """
        Monitors Indian market hours (09:15 - 15:30 IST).
        Triggers daily retraining automatically at 3:30 PM.
        """
        tz = zoneinfo.ZoneInfo(settings.timezone)
        while True:
            try:
                now = datetime.now(tz)
                today_str = now.strftime("%Y-%m-%d")

                is_weekday = now.weekday() < 5
                is_after_market_close = now.time() >= time(15, 30)

                if is_weekday and is_after_market_close and self.last_trained_date != today_str:
                    self.run_daily_retrain_cycle()

            except Exception as e:
                print(f"Notice in Autonomous Learner daemon: {e}")

            await asyncio.sleep(60)


# Singleton learner instance
auto_learner = AutonomousLearner()
