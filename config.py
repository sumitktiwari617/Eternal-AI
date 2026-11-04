import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file if present
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


class Settings(BaseModel):
    # --- Asset & Market Settings ---
    symbol: str = Field(default_factory=lambda: os.getenv("SYMBOL", "ETERNAL.NS"))
    exchange: str = Field(default_factory=lambda: os.getenv("EXCHANGE", "NSE"))
    timeframe: str = Field(default_factory=lambda: os.getenv("TIMEFRAME", "5m"))
    kotak_token: str = Field(default_factory=lambda: os.getenv("KOTAK_TOKEN", "5097"))
    kotak_segment: str = Field(default_factory=lambda: os.getenv("KOTAK_SEGMENT", "nse_cm"))

    # --- Strategy Parameters (EMA, VWAP, RSI, ATR) ---
    ema_fast: int = Field(default_factory=lambda: int(os.getenv("EMA_FAST", "20")))
    ema_slow: int = Field(default_factory=lambda: int(os.getenv("EMA_SLOW", "50")))
    rsi_period: int = Field(default_factory=lambda: int(os.getenv("RSI_PERIOD", "14")))
    rsi_buy_min: float = Field(default_factory=lambda: float(os.getenv("RSI_BUY_MIN", "50.0")))
    rsi_buy_max: float = Field(default_factory=lambda: float(os.getenv("RSI_BUY_MAX", "70.0")))
    rsi_sell_min: float = Field(default_factory=lambda: float(os.getenv("RSI_SELL_MIN", "30.0")))
    rsi_sell_max: float = Field(default_factory=lambda: float(os.getenv("RSI_SELL_MAX", "50.0")))
    atr_period: int = Field(default_factory=lambda: int(os.getenv("ATR_PERIOD", "14")))
    stop_loss_atr_mult: float = Field(default_factory=lambda: float(os.getenv("STOP_LOSS_ATR_MULT", "1.0")))
    target_atr_mult: float = Field(default_factory=lambda: float(os.getenv("TARGET_ATR_MULT", "3.0")))

    # --- Risk & Money Management ---
    initial_capital: float = Field(default_factory=lambda: float(os.getenv("INITIAL_CAPITAL", "100000.0")))
    default_quantity: int = Field(default_factory=lambda: int(os.getenv("DEFAULT_QUANTITY", "1000")))
    max_risk_per_trade_rupees: float = Field(default_factory=lambda: float(os.getenv("MAX_RISK_PER_TRADE_RUPEES", "2000.0")))
    cost_rate_per_side: float = Field(default_factory=lambda: float(os.getenv("COST_RATE_PER_SIDE", "0.0005")))

    # --- Safety & Execution Flags ---
    # Real autonomous orders are PERMANENTLY DISABLED (System is strictly an AI Trading Guider)
    real_orders_enabled: bool = False
    emergency_stop: bool = Field(default_factory=lambda: os.getenv("EMERGENCY_STOP", "False").lower() in ("true", "1", "yes"))
    agent_mode: str = Field(default_factory=lambda: os.getenv("AGENT_MODE", "GUIDER"))  # "GUIDER" (Advisory Only) or "PAPER"
    max_data_age_seconds: int = Field(default_factory=lambda: int(os.getenv("MAX_DATA_AGE_SECONDS", "300")))
    enforce_market_hours: bool = Field(default_factory=lambda: os.getenv("ENFORCE_MARKET_HOURS", "False").lower() in ("true", "1", "yes"))
    market_open_time: str = Field(default_factory=lambda: os.getenv("MARKET_OPEN_TIME", "09:15"))
    market_close_time: str = Field(default_factory=lambda: os.getenv("MARKET_CLOSE_TIME", "15:30"))
    timezone: str = Field(default_factory=lambda: os.getenv("TIMEZONE", "Asia/Kolkata"))

    # --- Kotak Neo Broker Credentials (Optional) ---
    kotak_consumer_key: Optional[str] = Field(default_factory=lambda: os.getenv("KOTAK_CONSUMER_KEY", None))
    kotak_consumer_secret: Optional[str] = Field(default_factory=lambda: os.getenv("KOTAK_CONSUMER_SECRET", None))
    kotak_mobile_number: Optional[str] = Field(default_factory=lambda: os.getenv("KOTAK_MOBILE_NUMBER", None))
    kotak_client_code: Optional[str] = Field(default_factory=lambda: os.getenv("KOTAK_CLIENT_CODE", None))
    kotak_mpin: Optional[str] = Field(default_factory=lambda: os.getenv("KOTAK_MPIN", None))
    kotak_environment: str = Field(default_factory=lambda: os.getenv("KOTAK_ENVIRONMENT", "prod"))
    kotak_product: str = Field(default_factory=lambda: os.getenv("KOTAK_PRODUCT", "MIS"))
    kotak_trading_symbol: Optional[str] = Field(default_factory=lambda: os.getenv("KOTAK_TRADING_SYMBOL", None))

    # --- Server & File Storage Paths (Cloud / Render & Localhost) ---
    server_host: str = Field(default_factory=lambda: os.getenv("SERVER_HOST", "0.0.0.0" if os.getenv("RENDER") else "127.0.0.1"))
    server_port: int = Field(default_factory=lambda: int(os.getenv("PORT", os.getenv("SERVER_PORT", "8000"))))
    cors_origins: str = Field(default_factory=lambda: os.getenv("CORS_ORIGINS", "*"))
    render_backend_url: Optional[str] = Field(default_factory=lambda: os.getenv("RENDER_BACKEND_URL", None))
    
    # --- Localhost AI Model Microservice & Tunnel Settings ---
    ai_service_host: str = Field(default_factory=lambda: os.getenv("AI_SERVICE_HOST", "127.0.0.1"))
    ai_service_port: int = Field(default_factory=lambda: int(os.getenv("AI_SERVICE_PORT", "8001")))
    ai_model_service_url: str = Field(default_factory=lambda: os.getenv("AI_MODEL_SERVICE_URL", "http://127.0.0.1:8001"))
    ai_secret_token: Optional[str] = Field(default_factory=lambda: os.getenv("AI_SECRET_TOKEN", None))
    ai_tunnel_skip_warning: bool = Field(default_factory=lambda: os.getenv("AI_TUNNEL_SKIP_WARNING", "True").lower() in ("true", "1", "yes"))
    ngrok_authtoken: Optional[str] = Field(default_factory=lambda: os.getenv("NGROK_AUTHTOKEN", None))

    poll_interval_seconds: int = Field(default_factory=lambda: int(os.getenv("POLL_INTERVAL_SECONDS", "30")))
    paper_log_file: str = Field(default_factory=lambda: os.getenv("PAPER_LOG_FILE", "eternal_paper_log.jsonl"))
    backtest_csv_file: str = Field(default_factory=lambda: os.getenv("BACKTEST_CSV_FILE", "eternal_backtest_results.csv"))


# Global singleton settings object
settings = Settings()


def update_settings(new_values: dict) -> Settings:
    """Dynamically update configuration parameters at runtime in-place."""
    global settings
    for k, v in new_values.items():
        if k == "real_orders_enabled":
            continue  # Hard-lock: real orders can NEVER be enabled
        if hasattr(settings, k):
            setattr(settings, k, v)
    settings.real_orders_enabled = False
    return settings

