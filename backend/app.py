import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings, update_settings
from backend.schemas import (
    ConfigUpdateRequest,
    BacktestRequest,
    ModeUpdateRequest,
    KotakLoginRequest,
    TunnelRegistrationRequest,
)
from execution.engine import engine
from execution.logger import get_recent_logs, clear_logs
from core.backtester import run_backtest
from core.rsi_engine import run_pure_rsi_backtest
from core.indicators import calculate_indicators
from data.fetcher import fetch_historical_candles, fetch_latest_quote
from core.risk_manager import calculate_trade_brackets

# Import AI Engine components
from ai.model import ai_model
from ai.explainer import generate_decision_reason
from ai.auto_learner import auto_learner

# Background Poller Task
_poller_task = None
_learner_task = None


async def background_monitoring_loop():
    """Background polling worker that evaluates signals when agent is RUNNING."""
    while True:
        try:
            if engine.state == "RUNNING" and not settings.emergency_stop:
                engine.run_single_analysis()
        except Exception as e:
            print(f"Background worker error: {e}")
        await asyncio.sleep(max(5, settings.poll_interval_seconds))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _poller_task, _learner_task

    # 1. Autonomous 6-month training check on boot
    try:
        auto_learner.ensure_initial_training()
    except Exception as e:
        print(f"Initial AI auto-train note: {e}")

    # 2. Initial analysis on startup
    try:
        engine.run_single_analysis()
    except Exception as e:
        print(f"Startup initial analysis notice: {e}")

    # 3. Launch background daemons
    _poller_task = asyncio.create_task(background_monitoring_loop())
    _learner_task = asyncio.create_task(auto_learner.background_market_close_daemon())

    yield

    if _poller_task:
        _poller_task.cancel()
    if _learner_task:
        _learner_task.cancel()


app = FastAPI(
    title="ETERNAL AI Trading Agent API",
    description="High-performance, modular algorithmic trading backend for NSE equities and derivatives.",
    version="2.0.0",
    lifespan=lifespan,
)

# --- Security & CORS Middleware ---

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if request.url.path.startswith("/static") or request.url.path in ("/", "/index.html"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Enable CORS for Vercel, Localhost & Cloud Deployments
cors_origins_list = (
    [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if settings.cors_origins != "*" else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list,
    allow_origin_regex=r"https://.*\.vercel\.app" if cors_origins_list != ["*"] else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_ai_service_headers() -> Dict[str, str]:
    """Headers for connecting to AI Model running on Localhost or Public Tunnel."""
    headers = {
        "User-Agent": "ETERNAL-Trading-Backend/2.0",
        "Accept": "application/json",
    }
    if settings.ai_tunnel_skip_warning:
        headers["ngrok-skip-browser-warning"] = "1"
    if settings.ai_secret_token:
        headers["X-AI-Secret-Token"] = settings.ai_secret_token
    return headers

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# --- API Routes ---

@app.get("/api/status")
def get_system_status():
    """Returns real-time agent state, telemetry, and quotes."""
    return engine.get_dashboard_state()


@app.get("/api/config")
def get_configuration():
    """Returns current active settings."""
    return settings.model_dump()


@app.post("/api/config")
def update_configuration(req: ConfigUpdateRequest):
    """Updates configuration parameters dynamically without restarting."""
    payload = {k: v for k, v in req.model_dump().items() if v is not None}
    new_cfg = update_settings(payload)
    return {
        "success": True,
        "message": "Configuration updated successfully.",
        "config": new_cfg.model_dump(),
    }


@app.get("/api/market-data")
def get_market_data(
    range_period: str = "5d",
    interval: Optional[str] = None
):
    """Returns historical candles along with precalculated indicators for chart rendering."""
    inv = interval or settings.timeframe
    df = fetch_historical_candles(
        symbol=settings.symbol,
        range_period=range_period,
        interval=inv,
        config=settings
    )

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="Market data could not be retrieved.")

    try:
        ind_df = calculate_indicators(
            df,
            ema_fast=settings.ema_fast,
            ema_slow=settings.ema_slow,
            rsi_period=settings.rsi_period,
            atr_period=settings.atr_period,
        )
    except Exception:
        ind_df = df

    records = []
    for ts, row in ind_df.iterrows():
        records.append({
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row.get("volume", 0)),
            "ema_fast": round(float(row[f"EMA{settings.ema_fast}"]), 2) if f"EMA{settings.ema_fast}" in row else None,
            "ema_slow": round(float(row[f"EMA{settings.ema_slow}"]), 2) if f"EMA{settings.ema_slow}" in row else None,
            "vwap": round(float(row["VWAP"]), 2) if "VWAP" in row else None,
            "rsi": round(float(row[f"RSI{settings.rsi_period}"]), 2) if f"RSI{settings.rsi_period}" in row else None,
            "atr": round(float(row[f"ATR{settings.atr_period}"]), 2) if f"ATR{settings.atr_period}" in row else None,
        })

    return {
        "symbol": settings.symbol,
        "interval": inv,
        "count": len(records),
        "candles": records,
    }


@app.post("/api/analyze")
def trigger_analysis():
    """Triggers an immediate market data fetch, indicator calculation, and signal decision."""
    res = engine.run_single_analysis()
    return res


@app.post("/api/controls/start")
def control_start():
    return engine.start()


@app.post("/api/controls/pause")
def control_pause():
    return engine.pause()


@app.post("/api/controls/emergency-stop")
def control_emergency_stop():
    return engine.emergency_stop()


@app.post("/api/controls/reset")
def control_reset():
    return engine.reset()


@app.post("/api/controls/mode")
def control_set_mode(req: ModeUpdateRequest):
    return engine.set_mode(req.mode)


@app.post("/api/backtest")
def trigger_backtest(req: BacktestRequest):
    """Executes a backtest on historical candles with customizable parameters."""
    sym = req.symbol or settings.symbol
    df = fetch_historical_candles(
        symbol=sym,
        range_period=req.range_period,
        interval=req.interval,
        config=settings
    )

    if df is None or len(df) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient candle history for symbol '{sym}' (fetched {len(df) if df is not None else 0} candles)."
        )

    # Local overrides if provided
    overrides = {}
    if req.initial_capital is not None:
        overrides["initial_capital"] = req.initial_capital
    if req.quantity is not None:
        overrides["default_quantity"] = req.quantity
    if req.stop_loss_atr_mult is not None:
        overrides["stop_loss_atr_mult"] = req.stop_loss_atr_mult
    if req.target_atr_mult is not None:
        overrides["target_atr_mult"] = req.target_atr_mult

    test_cfg = settings
    if overrides:
        data_dict = settings.model_dump()
        data_dict.update(overrides)
        from config import Settings
        test_cfg = Settings(**data_dict)

    res = run_backtest(df, config=test_cfg, export_csv=True)
    return res


@app.post("/api/backtest-rsi")
def trigger_rsi_backtest(req: BacktestRequest):
    """Executes a pure RSI 9 & RSI 14 backtest without EMA or VWAP."""
    sym = req.symbol or settings.symbol
    range_p = req.range_period or "6mo"
    interval = req.interval or "1h"

    df = fetch_historical_candles(
        symbol=sym,
        range_period=range_p,
        interval=interval,
        config=settings
    )

    if df is None or len(df) < 25:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient candle history for symbol '{sym}' (fetched {len(df) if df is not None else 0} candles)."
        )

    qty = req.quantity or 100
    capital = req.initial_capital or 100000.0

    res = run_pure_rsi_backtest(
        df,
        initial_capital=capital,
        quantity=qty,
        min_rsi_slow=50.0,
        overbought_rsi=70.0,
        allow_short=False,
        stop_loss_pct=0.04
    )
    return res


@app.get("/api/logs")
def get_logs(limit: int = 50):
    """Returns recent paper trading and analysis logs."""
    return {
        "count": limit,
        "logs": get_recent_logs(limit=limit, config=settings)
    }


@app.delete("/api/logs")
def clear_paper_logs():
    """Clears the paper analysis journal."""
    success = clear_logs(config=settings)
    return {"success": success, "message": "Log file cleared."}


@app.post("/api/kotak/login")
def login_kotak(req: KotakLoginRequest):
    """Logs into Kotak Neo API using TOTP."""
    return engine.kotak.login_with_totp(totp_code=req.totp, mpin=req.mpin)


# --- Read-Only Broker Telemetry Endpoints ---

@app.get("/api/orders/positions")
def get_positions():
    """Fetches open positions from Kotak Neo API (Read-Only)."""
    return engine.kotak.get_positions()


@app.get("/api/orders/history")
def get_order_history():
    """Fetches daily order book / report from Kotak Neo API (Read-Only)."""
    return engine.kotak.get_order_report()


# --- Autonomous Machine Learning AI Endpoints ---

@app.post("/api/ai/register-tunnel")
def register_ai_tunnel(req: TunnelRegistrationRequest, request: Request):
    """
    Dynamic Tunnel Handshake endpoint:
    Allows any desktop running 'start_ai_tunnel.bat' to automatically report
    its live public tunnel URL to this hosted backend (e.g. on Render) without manual redeployment.
    """
    # 1. Enforce secret token verification if configured
    if settings.ai_secret_token:
        provided_token = req.secret_token or request.headers.get("X-AI-Secret-Token")
        if not provided_token or provided_token.strip() != settings.ai_secret_token.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Invalid or missing X-AI-Secret-Token."
            )

    url = req.tunnel_url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tunnel URL format. Must begin with http:// or https://"
        )

    clean_url = url.rstrip("/")
    update_settings({"ai_model_service_url": clean_url})

    return {
        "success": True,
        "message": f"AI model tunnel successfully registered to {clean_url}",
        "active_ai_service_url": settings.ai_model_service_url,
    }


@app.get("/api/ai/tunnel-status")
def get_ai_tunnel_status():
    """Returns current active AI tunnel service URL and handshake configuration."""
    return {
        "success": True,
        "active_ai_service_url": settings.ai_model_service_url,
        "has_secret_token": bool(settings.ai_secret_token),
        "ai_tunnel_skip_warning": settings.ai_tunnel_skip_warning,
    }

@app.get("/api/ai/predict")
def get_ai_prediction():
    """
    Runs real-time machine learning inference:
    First attempts to query the dedicated Localhost AI Model Microservice (if running),
    otherwise falls back to the in-process local model.
    Returns AI Signal (BUY/SELL/HOLD), Confidence %, Model Accuracy %,
    Plain-English Reason, and Risk Brackets.
    """
    # 1. Check if external or standalone Local AI Model server is reachable
    if settings.ai_model_service_url:
        try:
            import requests
            resp = requests.get(
                f"{settings.ai_model_service_url.rstrip('/')}/api/ai/predict",
                params={"symbol": settings.symbol, "timeframe": settings.timeframe},
                headers=get_ai_service_headers(),
                timeout=3.0
            )
            if resp.status_code == 200:
                res_data = resp.json()
                res_data["routed_via"] = "localhost_ai_service"
                return res_data
        except Exception:
            pass  # Fall back to embedded model

    # 2. In-process embedded AI model inference
    df = fetch_historical_candles(
        symbol=settings.symbol,
        range_period="5d",
        interval=settings.timeframe,
        config=settings
    )

    if df is None or len(df) < 20:
        raise HTTPException(status_code=400, detail="Insufficient candle data to run AI inference.")

    pred = ai_model.predict(df, confidence_threshold=55.0)
    reason = generate_decision_reason(pred)

    price = pred["latest_price"]
    atr_norm = pred["feature_snapshot"].get("atr_normalized", 1.0)
    atr = max(0.5, (atr_norm / 100.0) * price)

    brackets = calculate_trade_brackets(
        entry_price=price,
        atr=atr,
        side=pred["signal"] if pred["signal"] in ("BUY", "SELL") else "BUY",
        config=settings
    )

    # Record daily prediction for 3:30 PM evaluation
    auto_learner.record_prediction(pred, current_price=price)

    return {
        "success": True,
        "symbol": settings.symbol,
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
        "routed_via": "embedded_model",
    }


@app.get("/api/ai/accuracy-trend")
def get_ai_accuracy_trend():
    """Returns day-by-day learning accuracy history for frontend visualization."""
    if settings.ai_model_service_url:
        try:
            import requests
            resp = requests.get(
                f"{settings.ai_model_service_url.rstrip('/')}/api/ai/accuracy-trend",
                headers=get_ai_service_headers(),
                timeout=3.0
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass

    history = auto_learner.get_learning_history()
    return {
        "success": True,
        "history": history,
        "current_accuracy": ai_model.last_accuracy,
        "total_samples": ai_model.total_samples,
        "last_train_time": ai_model.last_train_time,
    }


# --- Serve Frontend Static Assets ---

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_index():
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Frontend index.html not found."}

