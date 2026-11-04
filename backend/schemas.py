from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class ConfigUpdateRequest(BaseModel):
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    timeframe: Optional[str] = None
    ema_fast: Optional[int] = None
    ema_slow: Optional[int] = None
    rsi_period: Optional[int] = None
    rsi_buy_min: Optional[float] = None
    rsi_buy_max: Optional[float] = None
    rsi_sell_min: Optional[float] = None
    rsi_sell_max: Optional[float] = None
    atr_period: Optional[int] = None
    stop_loss_atr_mult: Optional[float] = None
    target_atr_mult: Optional[float] = None
    initial_capital: Optional[float] = None
    default_quantity: Optional[int] = None
    max_risk_per_trade_rupees: Optional[float] = None
    enforce_market_hours: Optional[bool] = None
    max_data_age_seconds: Optional[int] = None


class BacktestRequest(BaseModel):
    symbol: Optional[str] = None
    range_period: str = Field(default="60d", description="Historical range: 5d, 1mo, 60d, 1y")
    interval: str = Field(default="5m", description="Candle interval: 1m, 5m, 15m, 1h, 1d")
    initial_capital: Optional[float] = None
    quantity: Optional[int] = None
    stop_loss_atr_mult: Optional[float] = None
    target_atr_mult: Optional[float] = None


class ModeUpdateRequest(BaseModel):
    mode: str = Field(..., description="COPILOT, PAPER or LIVE")


class KotakLoginRequest(BaseModel):
    totp: str = Field(..., description="6-digit TOTP code")
    mpin: Optional[str] = Field(default=None, description="6-digit Kotak Neo MPIN (optional)")


class TunnelRegistrationRequest(BaseModel):
    tunnel_url: str = Field(..., description="Public HTTPS tunnel URL (e.g. https://xyz.ngrok-free.app)")
    secret_token: Optional[str] = Field(default=None, description="Shared AI secret token for verification")

