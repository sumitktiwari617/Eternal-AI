import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import zoneinfo
import requests
import pandas as pd
import numpy as np

from config import Settings, settings as default_settings

logger = logging.getLogger(__name__)


class DataUnavailableError(Exception):
    """Raised when live market data cannot be retrieved and synthetic fallback is disabled."""
    pass


def fetch_historical_candles(
    symbol: Optional[str] = None,
    range_period: str = "5d",
    interval: str = "5m",
    config: Optional[Settings] = None
) -> pd.DataFrame:
    """
    Fetches historical OHLCV candles via Yahoo Finance REST API.
    Raises DataUnavailableError on failure unless ALLOW_SYNTHETIC_DATA is explicitly enabled.
    """
    cfg = config or default_settings
    sym = symbol or cfg.symbol
    tz = zoneinfo.ZoneInfo(cfg.timezone)

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={range_period}&interval={interval}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            payload = resp.json()
            results = payload.get("chart", {}).get("result")
            if results and len(results) > 0:
                item = results[0]
                timestamps = item.get("timestamp", [])
                quotes = item.get("indicators", {}).get("quote", [{}])[0]

                if timestamps and quotes:
                    dt_index = [
                        datetime.fromtimestamp(ts, tz=zoneinfo.ZoneInfo("UTC")).astimezone(tz)
                        for ts in timestamps
                    ]

                    df = pd.DataFrame({
                        "open": quotes.get("open", []),
                        "high": quotes.get("high", []),
                        "low": quotes.get("low", []),
                        "close": quotes.get("close", []),
                        "volume": quotes.get("volume", []),
                    }, index=pd.DatetimeIndex(dt_index))

                    # Drop rows missing close price
                    df = df.dropna(subset=["close"])
                    if not df.empty:
                        df.attrs["source"] = "YAHOO"
                        df.attrs["fetched_at"] = datetime.now(tz).isoformat()
                        return df
    except Exception as ex:
        logger.warning(f"Yahoo Finance candle fetch failed for {sym}: {ex}")

    # Fallback to synthetic data ONLY when explicitly enabled in configuration
    if getattr(cfg, "allow_synthetic_data", False):
        logger.info(f"ALLOW_SYNTHETIC_DATA=True: Generating synthetic candles for {sym}")
        df = generate_synthetic_candles(symbol=sym, count=250, interval_minutes=5, timezone_str=cfg.timezone)
        df.attrs["source"] = "SYNTHETIC"
        df.attrs["fetched_at"] = datetime.now(tz).isoformat()
        return df

    raise DataUnavailableError(f"Historical candles unavailable for {sym} from live sources and synthetic fallback is disabled.")


def fetch_latest_quote(
    symbol: Optional[str] = None,
    config: Optional[Settings] = None,
    kotak_adapter: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Fetches latest available real-time quote/LTP for symbol.
    Checks Kotak Neo live quote first when authenticated; falls back to Yahoo Finance.
    Never returns hardcoded or fabricated prices on failure.
    """
    cfg = config or default_settings
    sym = symbol or cfg.symbol
    tz = zoneinfo.ZoneInfo(cfg.timezone)

    kotak_err: Optional[str] = None
    quote_err: Optional[str] = None

    # 1. Try Kotak Neo live API first if authenticated
    adapter = kotak_adapter
    if adapter is None:
        try:
            from execution.engine import engine
            adapter = getattr(engine, "kotak", None)
        except Exception:
            adapter = None

    if adapter and getattr(adapter, "is_authenticated", False):
        try:
            tok = getattr(cfg, "kotak_token", "5097")
            seg = getattr(cfg, "kotak_segment", "nse_cm")
            k_res = adapter.get_live_quote(token=tok, segment=seg)
            if k_res.get("success") and k_res.get("quote"):
                q = k_res["quote"]
                ltp = float(q.get("ltp", 0.0))
                return {
                    "symbol": sym,
                    "ltp": round(ltp, 2),
                    "open": round(float(q.get("open", ltp)), 2),
                    "high": round(float(q.get("high", ltp)), 2),
                    "low": round(float(q.get("low", ltp)), 2),
                    "close": round(ltp, 2),
                    "volume": int(q.get("vol", 0) or q.get("volume", 0)),
                    "change": round(float(q.get("net_change", 0.0)), 2),
                    "change_pct": round(float(q.get("percent_change", 0.0)), 2),
                    "timestamp": q.get("lstup_time") or datetime.now(tz).isoformat(),
                    "source": "KOTAK_NEO_LIVE",
                    "quote_source": "KOTAK_NEO_LIVE",
                    "quote_error": None,
                    "success": True,
                    "is_fresh": True,
                }
            else:
                kotak_err = k_res.get("error", "Empty quote from Kotak Neo")
                logger.warning(f"Kotak Neo quote unsuccessful for token {tok}: {kotak_err}")
        except Exception as ex:
            kotak_err = str(ex)
            logger.error(f"Kotak Neo live quote exception: {ex}")

    # 2. Secondary Fallback: Yahoo Finance REST API via 1-day candles
    try:
        df = fetch_historical_candles(symbol=sym, range_period="1d", interval="5m", config=cfg)
        if df is not None and not df.empty:
            source = df.attrs.get("source", "YAHOO")
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            ltp = float(latest["close"])
            change = float(ltp - prev["close"])
            change_pct = (change / prev["close"] * 100.0) if prev["close"] > 0 else 0.0

            ts = latest.name if hasattr(latest, "name") else datetime.now(tz)
            is_fresh = (source != "SYNTHETIC")

            return {
                "symbol": sym,
                "ltp": round(ltp, 2),
                "open": round(float(latest["open"]), 2),
                "high": round(float(latest["high"]), 2),
                "low": round(float(latest["low"]), 2),
                "close": round(ltp, 2),
                "volume": int(latest["volume"]),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "source": source,
                "quote_source": source,
                "quote_error": None if source != "SYNTHETIC" else "Live quote unavailable; synthetic data used",
                "success": True,
                "is_fresh": is_fresh,
            }
    except DataUnavailableError as e:
        quote_err = str(e)
    except Exception as e:
        quote_err = str(e)
        logger.warning(f"Yahoo candle fallback failed for quote: {e}")

    # Fail closed: No hardcoded fallback prices
    return {
        "symbol": sym,
        "success": False,
        "reason": "Live market quote unavailable from Kotak Neo and Yahoo Finance.",
        "quote_source": "NONE",
        "quote_error": quote_err or kotak_err or "Market quote feed unavailable",
        "is_fresh": False,
        "ltp": None,
        "open": None,
        "high": None,
        "low": None,
        "close": None,
        "volume": None,
        "change": None,
        "change_pct": None,
        "timestamp": datetime.now(tz).isoformat(),
    }


def generate_synthetic_candles(
    symbol: str = "ETERNAL.NS",
    count: int = 250,
    interval_minutes: int = 5,
    timezone_str: str = "Asia/Kolkata"
) -> pd.DataFrame:
    """
    Generates synthetic geometric Brownian motion intraday candles.
    ONLY used when ALLOW_SYNTHETIC_DATA=True for local testing/demo.
    """
    tz = zoneinfo.ZoneInfo(timezone_str)
    now = datetime.now(tz)
    start_time = now - timedelta(minutes=count * interval_minutes)

    dt_index = [
        start_time + timedelta(minutes=i * interval_minutes)
        for i in range(count)
    ]

    base_price = 320.0
    volatility = 0.002
    np.random.seed(42)

    returns = np.random.normal(0.0001, volatility, count)
    price_series = base_price * np.exp(np.cumsum(returns))

    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []

    for i in range(count):
        close_p = price_series[i]
        open_p = price_series[i-1] if i > 0 else base_price
        high_p = max(open_p, close_p) + abs(np.random.normal(0, 0.4))
        low_p = min(open_p, close_p) - abs(np.random.normal(0, 0.4))
        vol = int(max(1000, np.random.normal(25000, 8000)))

        opens.append(round(open_p, 2))
        highs.append(round(high_p, 2))
        lows.append(round(low_p, 2))
        closes.append(round(close_p, 2))
        volumes.append(vol)

    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    }, index=pd.DatetimeIndex(dt_index))
