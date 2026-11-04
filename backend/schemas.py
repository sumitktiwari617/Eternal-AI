from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Any, List


class ConfigUpdateRequest(BaseModel):
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    timeframe: Optional[str] = None
    ema_fast: Optional[int] = Field(default=None, gt=1, description="Fast EMA period (> 1)")
    ema_slow: Optional[int] = Field(default=None, gt=1, description="Slow EMA period (> 1)")
    rsi_period: Optional[int] = Field(default=None, gt=1, description="RSI period (> 1)")
    rsi_buy_min: Optional[float] = None
    rsi_buy_max: Optional[float] = None
    rsi_sell_min: Optional[float] = None
    rsi_sell_max: Optional[float] = None
    atr_period: Optional[int] = Field(default=None, gt=1, description="ATR period (> 1)")
    stop_loss_atr_mult: Optional[float] = Field(default=None, gt=0.0, description="Stop-loss ATR multiplier (> 0)")
    target_atr_mult: Optional[float] = Field(default=None, gt=0.0, description="Target ATR multiplier (> 0)")
    initial_capital: Optional[float] = Field(default=None, gt=0.0)
    default_quantity: Optional[int] = Field(default=None, ge=1, description="Default order quantity (>= 1)")
    max_risk_per_trade_rupees: Optional[float] = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def validate_cross_field_constraints(self):
        if self.ema_fast is not None and self.ema_slow is not None:
            if self.ema_fast >= self.ema_slow:
                raise ValueError(f"ema_fast ({self.ema_fast}) must be strictly less than ema_slow ({self.ema_slow})")

        if self.rsi_buy_min is not None and self.rsi_buy_max is not None:
            if self.rsi_buy_min >= self.rsi_buy_max:
                raise ValueError(f"rsi_buy_min ({self.rsi_buy_min}) must be strictly less than rsi_buy_max ({self.rsi_buy_max})")

        if self.rsi_sell_min is not None and self.rsi_sell_max is not None:
            if self.rsi_sell_min >= self.rsi_sell_max:
                raise ValueError(f"rsi_sell_min ({self.rsi_sell_min}) must be strictly less than rsi_sell_max ({self.rsi_sell_max})")

        if self.target_atr_mult is not None and self.stop_loss_atr_mult is not None:
            if self.target_atr_mult <= self.stop_loss_atr_mult:
                raise ValueError(f"target_atr_mult ({self.target_atr_mult}) must be strictly greater than stop_loss_atr_mult ({self.stop_loss_atr_mult})")

        return self


class BacktestRequest(BaseModel):
    symbol: Optional[str] = None
    range_period: str = Field(default="60d", description="Historical range: 5d, 1mo, 60d, 1y")
    interval: str = Field(default="5m", description="Candle interval: 1m, 5m, 15m, 1h, 1d")
    initial_capital: Optional[float] = None
    quantity: Optional[int] = None
    stop_loss_atr_mult: Optional[float] = None
    target_atr_mult: Optional[float] = None


class ModeUpdateRequest(BaseModel):
    mode: str = Field(..., description="COPILOT or PAPER (LIVE autonomous order placement is permanently disabled)")


class KotakLoginRequest(BaseModel):
    totp: str = Field(..., description="6-digit TOTP code")
    mpin: Optional[str] = Field(default=None, description="6-digit Kotak Neo MPIN (optional)")


class TunnelRegistrationRequest(BaseModel):
    tunnel_url: str = Field(..., description="Public HTTPS tunnel URL (e.g. https://xyz.ngrok-free.app)")
    secret_token: Optional[str] = Field(default=None, description="Shared AI secret token for verification")

