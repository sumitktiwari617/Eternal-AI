"""
ETERNAL AI Trading Agent — Dedicated Localhost AI Model Microservice
Runs on localhost (default port 8001) to provide local machine learning inference,
calibrated confidence scoring, explainable plain-English reasoning, and autonomous
daily self-learning (3:30 PM IST) for locally hosted or cloud-hosted backends & frontends.
"""

import sys
import os
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
from contextlib import asynccontextmanager
import pandas as pd
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Ensure parent directory is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings, update_settings
from ai.model import ai_model
from ai.explainer import generate_decision_reason
from ai.auto_learner import auto_learner
from data.fetcher import fetch_historical_candles
from core.risk_manager import calculate_trade_brackets


# --- Request Schemas ---

class CandleItem(BaseModel):
    timestamp: Optional[str] = None
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = 0.0


class PredictCandlesRequest(BaseModel):
    symbol: Optional[str] = None
    confidence_threshold: Optional[float] = 55.0
    candles: Optional[List[CandleItem]] = None


# --- Lifespan Manager ---

_learner_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _learner_task

    # 1. Ensure initial 6-month training
    print("🧠 [Local AI Model Server] Initializing model weights and 6-month historical training...")
    try:
        init_res = auto_learner.ensure_initial_training()
        print(f"✅ [Local AI Model Server] Initial training status: {init_res.get('status', 'READY')} "
              f"| Accuracy: {ai_model.last_accuracy}% | Samples: {ai_model.total_samples}")
    except Exception as e:
        print(f"⚠️ [Local AI Model Server] Note on initial train: {e}")

    # 2. Launch background 3:30 PM market-close auto-learning daemon
    _learner_task = asyncio.create_task(auto_learner.background_market_close_daemon())
    print("⏰ [Local AI Model Server] Autonomous 3:30 PM IST daily retraining daemon started in background.")

    yield

    if _learner_task:
        _learner_task.cancel()
    print("🛑 [Local AI Model Server] Server stopped.")


# --- FastAPI Application ---

app = FastAPI(
    title="ETERNAL Localhost AI Model Microservice",
    description=(
        "Dedicated Machine Learning Prediction and Autonomous Self-Learning Engine. "
        "Runs on localhost to serve predictions to cloud-hosted or local backends and frontends."
    ),
    version="2.0.0",
    lifespan=lifespan,
)


# --- Private Network Access & CORS Middleware ---

class PrivateNetworkAccessMiddleware(BaseHTTPMiddleware):
    """
    Handles Chrome/Edge Private Network Access (PNA) preflight and response headers.
    Allows remote hosted web apps (e.g. on https://my-trading-app.com) to access
    the local AI model on http://127.0.0.1:8001 seamlessly.
    """
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" and "access-control-request-private-network" in request.headers:
            response = Response(status_code=204)
            response.headers["Access-Control-Allow-Origin"] = request.headers.get("origin", "*")
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Private-Network"] = "true"
            return response

        response = await call_next(request)
        response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response


import hmac

cors_origins_list = (
    [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if settings.cors_origins and settings.cors_origins != "*"
    else ["http://localhost:8000", "http://127.0.0.1:8000"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(PrivateNetworkAccessMiddleware)


# --- Tunnel Authentication Helper ---

def verify_tunnel_auth(request: Request):
    """
    Verifies incoming requests supply the matching X-AI-Secret-Token header.
    Fails closed: requires AI_SECRET_TOKEN unless DEV_MODE=true and bound to localhost.
    Uses hmac.compare_digest to prevent timing attacks.
    """
    token = (
        request.headers.get("X-AI-Secret-Token")
        or request.headers.get("x-ai-secret-token")
    )
    if not token and "authorization" in request.headers:
        auth_hdr = request.headers.get("authorization", "")
        if auth_hdr.startswith("Bearer "):
            token = auth_hdr[7:].strip()

    expected = settings.ai_secret_token
    if expected:
        if not token or not hmac.compare_digest(token.strip(), expected.strip()):
            raise HTTPException(
                status_code=401,
                detail="Unauthorized: Missing or invalid X-AI-Secret-Token header for AI Model Tunnel."
            )
        return True

    # If AI_SECRET_TOKEN is unset in env:
    client_host = request.client.host if request.client else ""
    is_localhost = client_host in ("127.0.0.1", "localhost", "::1", "testclient")
    if settings.dev_mode and is_localhost:
        return True

    raise HTTPException(
        status_code=503,
        detail="AI Service Unavailable: AI_SECRET_TOKEN is not configured."
    )


# --- Endpoints ---

@app.get("/")
def get_root_info():
    """Returns local AI model status, accuracy, and API catalog."""
    return {
        "service": "ETERNAL Autonomous AI Trading Model Server",
        "status": "ONLINE",
        "version": "2.0.0",
        "location": "Localhost (Your Machine)",
        "model": {
            "file": "eternal_ai_model.joblib",
            "accuracy": ai_model.last_accuracy,
            "total_samples": ai_model.total_samples,
            "last_train_time": ai_model.last_train_time,
            "features_count": len(ai_model.feature_names),
        },
        "autonomous_learner": {
            "status": "ACTIVE",
            "schedule": "Daily at 15:30 IST (Indian Market Close)",
            "last_trained_date": auto_learner.last_trained_date,
            "predictions_logged_file": "daily_predictions.jsonl",
            "learning_history_file": "model_learning_history.json",
        },
        "endpoints": {
            "predict_live": "GET /api/ai/predict",
            "predict_candles": "POST /api/ai/predict",
            "accuracy_trend": "GET /api/ai/accuracy-trend",
            "retrain": "POST /api/ai/retrain",
            "swagger_docs": "GET /docs",
        },
    }


@app.get("/health")
def health_check():
    """Lightweight health check probe."""
    return {
        "status": "healthy",
        "service": "eternal-local-ai-model",
        "accuracy": ai_model.last_accuracy,
    }


@app.get("/api/ai/status")
def get_ai_status():
    """Returns detailed AI model telemetry and learning status."""
    return {
        "service": "ETERNAL AI Model Server",
        "model_loaded": ai_model.model is not None,
        "model_accuracy": ai_model.last_accuracy,
        "total_samples": ai_model.total_samples,
        "last_train_time": ai_model.last_train_time,
        "feature_count": len(ai_model.feature_names),
        "target_symbol": settings.symbol,
        "timeframe": settings.timeframe,
        "learner_active": True,
        "last_trained_date": auto_learner.last_trained_date,
    }


@app.get("/api/ai/predict")
def get_ai_prediction_live(
    request: Request,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    confidence_threshold: float = 55.0
):
    """
    Live AI Prediction:
    Fetches real-time candles (via Kotak Neo or Yahoo Finance fallback),
    runs feature extraction and model inference, returns BUY/SELL/HOLD signal,
    calibrated confidence %, model accuracy %, explainable reason, and trade brackets.
    """
    verify_tunnel_auth(request)
    target_symbol = symbol or settings.symbol
    target_tf = timeframe or settings.timeframe

    df = fetch_historical_candles(
        symbol=target_symbol,
        range_period="5d",
        interval=target_tf,
        config=settings
    )

    if df is None or len(df) < 20:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient candle history for symbol '{target_symbol}' to run AI inference."
        )

    data_source = df.attrs.get("source", "UNKNOWN")
    if data_source not in ("YAHOO", "KOTAK_NEO_LIVE"):
        return {
            "success": False,
            "source": "localhost_ai_model",
            "symbol": target_symbol,
            "timeframe": target_tf,
            "signal": "WAIT",
            "confidence": 0.0,
            "model_accuracy": ai_model.last_accuracy,
            "probabilities": None,
            "reason": "DATA UNAVAILABLE / NOT LIVE",
            "brackets": None,
            "latest_price": None,
            "feature_snapshot": None,
            "last_train_time": ai_model.last_train_time,
            "note": "Market data is not from a live validated source.",
        }

    pred = ai_model.predict(df, confidence_threshold=confidence_threshold)
    reason = generate_decision_reason(pred)

    price = pred["latest_price"]
    atr_norm = pred["feature_snapshot"].get("atr_normalized", 1.0)
    atr = (atr_norm / 100.0) * price

    brackets = None
    if pred["signal"] in ("BUY", "SELL"):
        brackets = calculate_trade_brackets(
            entry_price=price,
            atr=atr,
            side=pred["signal"],
            config=settings
        )

    # Note: Closed-candle prediction logging is handled strictly at candle close via logger

    return {
        "success": True,
        "source": "localhost_ai_model",
        "symbol": target_symbol,
        "timeframe": target_tf,
        "signal": pred["signal"],
        "confidence": pred["confidence"],
        "model_accuracy": pred["model_accuracy"],
        "probabilities": pred["probabilities"],
        "reason": reason,
        "brackets": brackets,
        "latest_price": price,
        "feature_snapshot": pred["feature_snapshot"],
        "last_train_time": pred["last_train_time"],
        "note": pred["note"],
    }


@app.post("/api/ai/predict")
def predict_from_candles(req: PredictCandlesRequest, request: Request):
    """
    Inference endpoint supporting explicit candle submission:
    If a cloud-hosted backend or frontend supplies candles, this endpoint
    scores those exact candles using the local model.
    If no candles are provided, it fetches live candles automatically.
    """
    verify_tunnel_auth(request)
    target_symbol = req.symbol or settings.symbol
    conf_thresh = req.confidence_threshold or 55.0

    if req.candles and len(req.candles) >= 20:
        # Convert candle list to DataFrame
        records = []
        for c in req.candles:
            records.append({
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume or 0.0,
            })
        df = pd.DataFrame(records)
    else:
        # Fetch live candles
        df = fetch_historical_candles(
            symbol=target_symbol,
            range_period="5d",
            interval=settings.timeframe,
            config=settings
        )

    if df is None or len(df) < 20:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient candle history (need >= 20 candles, got {len(df) if df is not None else 0})."
        )

    data_source = df.attrs.get("source", "LIVE" if req.candles else "UNKNOWN")
    if data_source not in ("YAHOO", "KOTAK_NEO_LIVE", "LIVE"):
        return {
            "success": False,
            "source": "localhost_ai_model",
            "symbol": target_symbol,
            "signal": "WAIT",
            "confidence": 0.0,
            "model_accuracy": ai_model.last_accuracy,
            "probabilities": None,
            "reason": "DATA UNAVAILABLE / NOT LIVE",
            "brackets": None,
            "latest_price": None,
            "feature_snapshot": None,
            "last_train_time": ai_model.last_train_time,
            "note": "Market data is not from a live validated source.",
        }

    pred = ai_model.predict(df, confidence_threshold=conf_thresh)
    reason = generate_decision_reason(pred)

    price = pred["latest_price"]
    atr_norm = pred["feature_snapshot"].get("atr_normalized", 1.0)
    atr = (atr_norm / 100.0) * price

    brackets = None
    if pred["signal"] in ("BUY", "SELL"):
        brackets = calculate_trade_brackets(
            entry_price=price,
            atr=atr,
            side=pred["signal"],
            config=settings
        )

    return {
        "success": True,
        "source": "localhost_ai_model",
        "symbol": target_symbol,
        "signal": pred["signal"],
        "confidence": pred["confidence"],
        "model_accuracy": pred["model_accuracy"],
        "probabilities": pred["probabilities"],
        "reason": reason,
        "brackets": brackets,
        "latest_price": price,
        "feature_snapshot": pred["feature_snapshot"],
        "last_train_time": pred["last_train_time"],
        "note": pred["note"],
    }


@app.get("/api/ai/accuracy-trend")
def get_accuracy_trend(request: Request):
    """Returns day-by-day learning history and accuracy timeline for chart visualization."""
    verify_tunnel_auth(request)
    history = auto_learner.get_learning_history()
    return {
        "success": True,
        "history": history,
        "current_accuracy": ai_model.last_accuracy,
        "total_samples": ai_model.total_samples,
        "last_train_time": ai_model.last_train_time,
    }


@app.post("/api/ai/retrain")
def trigger_retrain(request: Request):
    """Triggers an autonomous walk-forward retraining cycle."""
    verify_tunnel_auth(request)
    res = auto_learner.run_daily_retrain_cycle()
    return {
        "success": True,
        "result": res,
        "updated_accuracy": ai_model.last_accuracy,
    }

