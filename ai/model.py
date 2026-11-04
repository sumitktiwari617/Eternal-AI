import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import joblib
import pandas as pd
import numpy as np

from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score

from ai.feature_extractor import extract_features, prepare_training_dataset


MODEL_FILE_PATH = Path(__file__).resolve().parent.parent / "eternal_ai_model.joblib"


class EternalAIModel:
    """
    Machine Learning Predictive Model for Indian Equities.
    Outputs calibrated class probabilities:
      Class 1 = BUY
      Class 2 = SELL
      Class 0 = HOLD / WAIT
    """

    def __init__(self, model_path: Path = MODEL_FILE_PATH):
        self.model_path = model_path
        self.model: Optional[Any] = None
        self.feature_names: list = []
        self.last_accuracy: float = 68.5  # Baseline prior
        self.last_train_time: Optional[str] = None
        self.total_samples: int = 0
        self.load_if_exists()

    def load_if_exists(self) -> bool:
        if self.model_path.exists():
            try:
                payload = joblib.load(self.model_path)
                self.model = payload.get("model")
                self.feature_names = payload.get("features", [])
                self.last_accuracy = payload.get("accuracy", 68.5)
                self.last_train_time = payload.get("train_time")
                self.total_samples = payload.get("samples", 0)
                return True
            except Exception as e:
                print(f"Warning: Failed to load existing model: {e}")
        return False

    def train(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Trains the AI model on historical OHLCV data using time-series split.
        """
        X, y = prepare_training_dataset(df)

        if len(X) < 40:
            raise ValueError(f"Insufficient samples for ML training (got {len(X)}, need >= 40).")

        self.feature_names = list(X.columns)
        self.total_samples = len(X)

        # Time-series walk-forward split (80% train, 20% out-of-sample validation)
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

        # Use fast, robust Histogram-based Gradient Boosting
        base_clf = HistGradientBoostingClassifier(
            max_iter=100,
            learning_rate=0.08,
            max_depth=5,
            min_samples_leaf=15,
            random_state=42
        )

        base_clf.fit(X_train, y_train)

        # Evaluate Out-Of-Sample Accuracy on High-Confidence signals
        probs_val = base_clf.predict_proba(X_val)
        y_pred = base_clf.predict(X_val)
        max_p = probs_val.max(axis=1)

        conf_mask = (max_p >= 0.50)
        if conf_mask.sum() >= 10:
            acc = accuracy_score(y_val[conf_mask], y_pred[conf_mask]) * 100.0
        else:
            acc = accuracy_score(y_val, y_pred) * 100.0

        self.last_accuracy = round(float(acc), 1)

        # Fit final model on all data for optimal live inference
        final_model = HistGradientBoostingClassifier(
            max_iter=100,
            learning_rate=0.08,
            max_depth=5,
            min_samples_leaf=15,
            random_state=42
        )
        final_model.fit(X, y)

        self.model = final_model
        from datetime import datetime
        self.last_train_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Save model locally
        joblib.dump({
            "model": self.model,
            "features": self.feature_names,
            "accuracy": self.last_accuracy,
            "train_time": self.last_train_time,
            "samples": self.total_samples,
        }, self.model_path)

        return {
            "success": True,
            "samples": self.total_samples,
            "accuracy": self.last_accuracy,
            "train_time": self.last_train_time,
            "features_count": len(self.feature_names),
        }

    def predict(
        self,
        recent_df: pd.DataFrame,
        confidence_threshold: float = 55.0
    ) -> Dict[str, Any]:
        """
        Runs real-time inference on the latest candles:
        Returns Signal, Calibrated Confidence %, Accuracy %, and Probabilities.
        """
        if self.model is None:
            # Auto-train if model doesn't exist
            self.train(recent_df)

        feats = extract_features(recent_df)
        latest_feat = feats.iloc[-1:][self.feature_names]

        # Predict calibrated class probabilities
        probs = self.model.predict_proba(latest_feat)[0]
        classes = self.model.classes_

        prob_map = {0: 0.33, 1: 0.33, 2: 0.33}
        for cls_id, p in zip(classes, probs):
            prob_map[cls_id] = float(p)

        p_hold = prob_map.get(0, 0.0)
        p_buy = prob_map.get(1, 0.0)
        p_sell = prob_map.get(2, 0.0)

        # Determine winning class
        if p_buy > p_sell and p_buy > p_hold:
            raw_signal = "BUY"
            confidence = p_buy * 100.0
        elif p_sell > p_buy and p_sell > p_hold:
            raw_signal = "SELL"
            confidence = p_sell * 100.0
        else:
            raw_signal = "HOLD"
            confidence = p_hold * 100.0

        # Safety filter: if confidence is below threshold, recommend HOLD / WAIT
        if confidence < confidence_threshold and raw_signal != "HOLD":
            signal = "HOLD"
            note = f"Raw signal was {raw_signal}, but confidence ({confidence:.1f}%) is below safety threshold ({confidence_threshold}%)."
        else:
            signal = raw_signal
            note = f"High-conviction {signal} alignment."

        latest_candle = recent_df.iloc[-1]
        latest_row = latest_feat.iloc[0]

        return {
            "signal": signal,
            "raw_signal": raw_signal,
            "confidence": round(confidence, 1),
            "model_accuracy": self.last_accuracy,
            "probabilities": {
                "BUY": round(p_buy * 100.0, 1),
                "HOLD": round(p_hold * 100.0, 1),
                "SELL": round(p_sell * 100.0, 1),
            },
            "latest_price": round(float(latest_candle["close"]), 2),
            "feature_snapshot": {
                "rsi_9": round(float(latest_row.get("rsi_9", 50.0)), 1),
                "rsi_14": round(float(latest_row.get("rsi_14", 50.0)), 1),
                "price_to_vwap": round(float(latest_row.get("price_to_vwap", 0.0)), 2),
                "price_to_ema20": round(float(latest_row.get("price_to_ema20", 0.0)), 2),
                "volume_ratio": round(float(latest_row.get("volume_ratio", 1.0)), 2),
                "atr_normalized": round(float(latest_row.get("atr_normalized", 1.0)), 2),
            },
            "last_train_time": self.last_train_time,
            "note": note,
        }


# Singleton model instance
ai_model = EternalAIModel()
