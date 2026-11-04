"""
Phase 1 Safety, Truthfulness, and Security Test Suite
Covers:
1. Synthetic fallback blocked & flagged (DataUnavailableError)
2. Kotak quote signature and exception handling (mock-based)
3. Market session states & holiday gate (Sunday, 09:20, 14:45, 15:40, holiday)
4. Incomplete candle exclusion & end-time staleness
5. Zero secret leakage in /api/config and Settings repr/dict
6. Admin API Key authentication on mutating routes (401/503 fail-closed)
7. Zero fake history seeded on fresh install
8. Migration removes unmeasured seeds with backup
9. Truthful explanations (contradicting RSI relations never appear)
10. HOLD / WAIT returns brackets == None
11. Risk cap parameter enforcement on position size
12. Zero order-placement symbols in codebase (strictly read-only advisory)
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, time, timedelta
import zoneinfo
from unittest.mock import MagicMock, patch

import pytest
import pandas as pd
from fastapi.testclient import TestClient

# Ensure root directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import Settings, settings, update_settings
from data.fetcher import fetch_historical_candles, fetch_latest_quote, DataUnavailableError
from data.kotak_client import KotakNeoAdapter
from core.risk_manager import (
    calculate_trade_brackets,
    check_safety_gate,
    get_market_session_state,
    load_market_holidays,
)
from ai.explainer import generate_decision_reason
from ai.model import EternalAIModel
from ai.auto_learner import AutonomousLearner
from backend.app import app as backend_app
from ai.server import app as ai_app


client_backend = TestClient(backend_app)
client_ai = TestClient(ai_app)


# =====================================================================
# 1. SYNTHETIC FALLBACK BLOCKED BY DEFAULT
# =====================================================================

def test_synthetic_fallback_blocked_by_default():
    """Verify DataUnavailableError is raised when live fetch fails and allow_synthetic_data=False."""
    cfg = Settings(allow_synthetic_data=False)
    with patch("requests.get", side_effect=Exception("Connection refused")):
        with pytest.raises(DataUnavailableError):
            fetch_historical_candles(symbol="ETERNAL.NS", config=cfg)


def test_synthetic_data_tagged_when_explicitly_enabled():
    """Verify synthetic candles are tagged with source='SYNTHETIC' when enabled."""
    cfg = Settings(allow_synthetic_data=True)
    with patch("requests.get", side_effect=Exception("Offline")):
        df = fetch_historical_candles(symbol="ETERNAL.NS", config=cfg)
        assert df is not None
        assert df.attrs.get("source") == "SYNTHETIC"
        assert "fetched_at" in df.attrs


def test_quote_fallback_has_no_hardcoded_prices():
    """Verify quote returns failure when live feeds fail, without 322.60 hardcoded price."""
    cfg = Settings(allow_synthetic_data=False)
    with patch("requests.get", side_effect=Exception("Offline")):
        q = fetch_latest_quote(symbol="ETERNAL.NS", config=cfg, kotak_adapter=None)
        assert q["success"] is False
        assert q["ltp"] is None
        assert q["quote_source"] == "NONE"


# =====================================================================
# 2. KOTAK CALL SIGNATURE & ERROR HANDLING
# =====================================================================

def test_kotak_quote_signature_and_token_verification():
    """Verify Kotak get_live_quote uses token and segment parameters and handles errors gracefully."""
    cfg = Settings(kotak_token="5097", kotak_segment="nse_cm")
    adapter = KotakNeoAdapter(config=cfg)
    adapter.is_authenticated = True
    adapter.client = MagicMock()

    # Mock quotes return
    adapter.client.quotes.return_value = [
        {"ltp": 348.50, "trdSym": "ETERNAL-EQ", "lstup_time": "2026-11-03 14:30:00"}
    ]

    res = adapter.get_live_quote(token="5097", segment="nse_cm")
    assert res["success"] is True
    assert res["ltp"] == 348.50

    # Verify quotes called with expected instrument_tokens
    adapter.client.quotes.assert_called_with(
        instrument_tokens=[{"instrument_token": "5097", "exchange_segment": "nse_cm"}],
        quote_type="all"
    )

    # Test token verification method
    v_res = adapter.verify_instrument_token(token="5097", segment="nse_cm")
    assert v_res["verified"] is True
    assert v_res["status"] == "MATCH"


def test_kotak_quote_error_surfaced():
    """Verify exceptions in Kotak Neo adapter are logged and return error structure."""
    cfg = Settings(kotak_token="5097", kotak_segment="nse_cm")
    adapter = KotakNeoAdapter(config=cfg)
    adapter.is_authenticated = True
    adapter.client = MagicMock()
    adapter.client.quotes.side_effect = RuntimeError("Broker server timeout")

    res = adapter.get_live_quote()
    assert res["success"] is False
    assert "Broker server timeout" in res["error"]


# =====================================================================
# 3. MARKET SESSION & HOLIDAY GATING
# =====================================================================

def test_market_session_weekend():
    """Sunday must always result in CLOSED and no trade entries."""
    tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    sunday_dt = datetime(2026, 11, 1, 11, 0, 0, tzinfo=tz)  # Sunday
    cfg = Settings(enforce_market_hours=True)

    state, can_enter, reason = get_market_session_state(sunday_dt, cfg)
    assert state == "CLOSED"
    assert can_enter is False
    assert "Weekend" in reason


def test_market_session_opening_discovery_9_20():
    """09:20 IST on weekday must be OPENING_DISCOVERY (WAIT)."""
    tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    weekday_discovery = datetime(2026, 11, 3, 9, 20, 0, tzinfo=tz)  # Tuesday 09:20
    cfg = Settings(enforce_market_hours=True)

    state, can_enter, reason = get_market_session_state(weekday_discovery, cfg)
    assert state == "OPENING_DISCOVERY"
    assert can_enter is False


def test_market_session_active_10_30():
    """10:30 IST on weekday must be ACTIVE."""
    tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    active_dt = datetime(2026, 11, 3, 10, 30, 0, tzinfo=tz)
    cfg = Settings(enforce_market_hours=True)

    state, can_enter, reason = get_market_session_state(active_dt, cfg)
    assert state == "ACTIVE"
    assert can_enter is True


def test_market_session_wind_down_14_45():
    """14:45 IST on weekday must be WIND_DOWN (No new entries)."""
    tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    wind_down_dt = datetime(2026, 11, 3, 14, 45, 0, tzinfo=tz)
    cfg = Settings(enforce_market_hours=True)

    state, can_enter, reason = get_market_session_state(wind_down_dt, cfg)
    assert state == "WIND_DOWN"
    assert can_enter is False


def test_market_session_closed_after_hours_15_40():
    """15:40 IST on weekday must be CLOSED."""
    tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    closed_dt = datetime(2026, 11, 3, 15, 40, 0, tzinfo=tz)
    cfg = Settings(enforce_market_hours=True)

    state, can_enter, reason = get_market_session_state(closed_dt, cfg)
    assert state == "CLOSED"
    assert can_enter is False


def test_market_holiday_gating(tmp_path):
    """Configured holiday date must block trade entries."""
    holiday_file = tmp_path / "market_holidays.json"
    holiday_file.write_text(json.dumps(["_comment: test", "2026-01-26"]), encoding="utf-8")

    tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    holiday_dt = datetime(2026, 1, 26, 11, 0, 0, tzinfo=tz)  # Republic Day Monday
    cfg = Settings(market_holidays_file=str(holiday_file), enforce_market_hours=True)

    state, can_enter, reason = get_market_session_state(holiday_dt, cfg)
    assert state == "CLOSED"
    assert can_enter is False
    assert "holiday" in reason.lower()


# =====================================================================
# 4. INCOMPLETE CANDLE EXCLUSION & STALENESS
# =====================================================================

def test_staleness_computed_from_candle_end_time():
    """Staleness check must measure time elapsed since candle end time."""
    tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    now = datetime.now(tz)
    # Candle that ended 600 seconds ago (threshold is 300)
    stale_candle_end = now - timedelta(seconds=600)
    cfg = Settings(enforce_market_hours=True, max_data_age_seconds=300)

    # During active market, stale candle end time fails safety check
    with patch("core.risk_manager.get_market_session_state", return_value=("ACTIVE", True, "Active")):
        safety = check_safety_gate(data_timestamp=stale_candle_end, config=cfg)
        assert safety["allowed"] is False
        assert safety["status"] == "STALE_DATA"


# =====================================================================
# 5. SECURITY: ZERO SECRET LEAKAGE IN CONFIG
# =====================================================================

def test_api_config_never_leaks_secrets():
    """GET /api/config and Settings.public_dict() must never serialize secret keys."""
    cfg = Settings(
        kotak_consumer_key="key_123",
        kotak_consumer_secret="secret_abc",
        kotak_mobile_number="9876543210",
        kotak_client_code="UCC123",
        kotak_mpin="9999",
        ai_secret_token="ai_secret_xyz",
        ngrok_authtoken="ngrok_xyz",
        admin_api_key="master_admin_key"
    )

    pub = cfg.public_dict()
    forbidden_keys = [
        "kotak_consumer_key", "kotak_consumer_secret", "kotak_mobile_number",
        "kotak_client_code", "kotak_mpin", "ai_secret_token", "ngrok_authtoken",
        "admin_api_key"
    ]
    for k in forbidden_keys:
        assert k not in pub

    # Check string and repr representations do not contain secrets
    repr_str = repr(cfg)
    str_str = str(cfg)
    assert "secret_abc" not in repr_str
    assert "9999" not in repr_str
    assert "master_admin_key" not in repr_str

    # Test via API endpoint
    res = client_backend.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    for k in forbidden_keys:
        assert k not in data


# =====================================================================
# 6. ADMIN API KEY AUTHENTICATION (FAIL-CLOSED)
# =====================================================================

def test_mutating_routes_require_admin_key():
    """Mutating routes must reject requests without valid X-Admin-Key header."""
    settings.admin_api_key = "test_secret_admin_key_123"

    mutating_endpoints = [
        ("POST", "/api/config", {"symbol": "TATAMOTORS.NS"}),
        ("POST", "/api/controls/start", {}),
        ("POST", "/api/controls/pause", {}),
        ("POST", "/api/controls/emergency-stop", {}),
        ("POST", "/api/controls/reset", {}),
        ("POST", "/api/kotak/login", {"totp": "123456"}),
        ("GET", "/api/orders/positions", None),
        ("GET", "/api/orders/history", None),
        ("DELETE", "/api/logs", None),
        ("POST", "/api/ai/register-tunnel", {"tunnel_url": "https://xyz.ngrok-free.app", "secret_token": "token"}),
    ]

    for method, path, payload in mutating_endpoints:
        if method == "POST":
            res = client_backend.post(path, json=payload or {})
        elif method == "GET":
            res = client_backend.get(path)
        elif method == "DELETE":
            res = client_backend.delete(path)

        assert res.status_code == 401, f"Endpoint {path} did not return 401 when missing X-Admin-Key"

        # Now supply valid X-Admin-Key header and verify it passes auth check
        headers = {"X-Admin-Key": "test_secret_admin_key_123"}
        if method == "POST":
            res_auth = client_backend.post(path, json=payload or {}, headers=headers)
        elif method == "GET":
            res_auth = client_backend.get(path, headers=headers)
        elif method == "DELETE":
            res_auth = client_backend.delete(path, headers=headers)

        assert res_auth.status_code != 401, f"Endpoint {path} failed authentication with valid X-Admin-Key"

    # Reset admin key
    settings.admin_api_key = None


def test_admin_routes_return_503_when_admin_key_unset_on_remote_host():
    """When ADMIN_API_KEY is unset and request is from a non-localhost host, return 503."""
    settings.admin_api_key = None
    settings.dev_mode = False

    res = client_backend.post(
        "/api/controls/start",
        headers={"X-Forwarded-For": "203.0.113.195"}
    )
    # Since dev_mode is False, fails closed with 503
    assert res.status_code == 503

    settings.dev_mode = True


# =====================================================================
# 7. ZERO FABRICATED ACCURACY SEEDS ON FRESH INSTALL
# =====================================================================

def test_fresh_install_has_zero_fake_accuracy_seeds(tmp_path):
    """A fresh install must have an empty learning history list and no 65.4% / 68.5% seeds."""
    hist_file = tmp_path / "model_learning_history.json"
    learner = AutonomousLearner()
    learner.history_file = hist_file
    learner._init_history()

    history = learner.get_learning_history()
    assert history == []

    # Model default last_accuracy must be None
    model = EternalAIModel(model_path=tmp_path / "model.joblib")
    assert model.last_accuracy is None


# =====================================================================
# 8. MIGRATION PURGES UNMEASURED SEEDED ROWS
# =====================================================================

def test_migration_removes_unmeasured_rows_and_creates_backup(tmp_path):
    """Migration must filter out rows without source='measured' and backup original file."""
    hist_file = tmp_path / "model_learning_history.json"
    raw_seeds = [
        {"date": "2026-10-27", "accuracy": 65.4, "samples": 750, "event": "Seed 1"},
        {"date": "2026-10-31", "accuracy": 68.5, "samples": 867, "event": "Seed 2"},
        {"date": "2026-11-03", "accuracy": 34.3, "samples": 866, "source": "measured", "event": "Real Train 1"}
    ]
    hist_file.write_text(json.dumps(raw_seeds), encoding="utf-8")

    learner = AutonomousLearner()
    learner.history_file = hist_file
    learner._init_history()

    # Backup must exist
    bak_file = hist_file.with_suffix(".json.bak")
    assert bak_file.exists()

    # History must contain only measured rows
    migrated = learner.get_learning_history()
    assert len(migrated) == 1
    assert migrated[0]["accuracy"] == 34.3
    assert migrated[0]["source"] == "measured"


# =====================================================================
# 9. TRUTHFUL EXPLANATIONS (NO FALSE CLAUSES)
# =====================================================================

def test_explainer_never_states_contradicting_rsi_relation():
    """If RSI 9 > RSI 14 during SELL, explainer must NEVER claim RSI 9 is trailing below RSI 14."""
    pred = {
        "signal": "SELL",
        "confidence": 64.0,
        "latest_price": 348.0,
        "feature_snapshot": {
            "rsi_9": 62.0,
            "rsi_14": 55.0,  # Contradicting SELL assumption
            "price_to_vwap": -0.5,
            "price_to_ema20": -0.3,
            "volume_ratio": 1.1,
            "atr_normalized": 0.8
        }
    }
    reason = generate_decision_reason(pred)

    assert "trailing below RSI 14" not in reason
    assert "Fast RSI 9 (62.0) is above RSI 14 (55.0)" in reason
    assert "Model class confidence is 64.0% for SELL." in reason
    # Ensure no fabricated claims of certainty
    assert "guaranteed" not in reason.lower()
    assert "high-probability" not in reason.lower()


def test_explainer_truthful_buy_clauses():
    """If RSI 9 < RSI 14 during BUY, explainer must not claim leading above."""
    pred = {
        "signal": "BUY",
        "confidence": 70.0,
        "latest_price": 350.0,
        "feature_snapshot": {
            "rsi_9": 48.0,
            "rsi_14": 52.0,
            "price_to_vwap": 0.4,
            "price_to_ema20": 0.2,
            "volume_ratio": 1.3,
            "atr_normalized": 0.9
        }
    }
    reason = generate_decision_reason(pred)
    assert "leading above RSI 14" not in reason
    assert "Fast RSI 9 (48.0) is below RSI 14 (52.0)" in reason


# =====================================================================
# 10. HOLD / WAIT RETURNS NULL BRACKETS
# =====================================================================

def test_hold_and_wait_return_none_brackets():
    """calculate_trade_brackets must return None when side is HOLD or WAIT."""
    assert calculate_trade_brackets(entry_price=348.0, atr=0.4, side="HOLD") is None
    assert calculate_trade_brackets(entry_price=348.0, atr=0.4, side="WAIT") is None
    assert calculate_trade_brackets(entry_price=348.0, atr=0.4, side="NEUTRAL") is None


# =====================================================================
# 11. RISK CAP ENFORCEMENT ON QUANTITY
# =====================================================================

def test_risk_cap_enforces_position_sizing():
    """When ATR risk exceeds max_risk_per_trade_rupees, quantity must be capped."""
    # Entry 300, ATR 4.0, sl_mult 1.0 -> risk_per_share = 4.0
    # max_risk = 2000 -> floor(2000 / 4) = 500 shares (default is 1000)
    cfg = Settings(
        default_quantity=1000,
        max_risk_per_trade_rupees=2000.0,
        stop_loss_atr_mult=1.0,
        target_atr_mult=3.0
    )
    b = calculate_trade_brackets(entry_price=300.0, atr=4.0, side="BUY", config=cfg)
    assert b is not None
    assert b["suggested_quantity"] == 500
    assert b["estimated_max_risk_rupees"] <= 2000.0

    # Extreme volatility: risk_per_share = 3000 -> max_risk 2000 -> qty < 1 -> returns None
    b_extreme = calculate_trade_brackets(entry_price=300.0, atr=3000.0, side="BUY", config=cfg)
    assert b_extreme is None


# =====================================================================
# 12. ZERO ORDER-PLACEMENT SYMBOLS IN CODEBASE (READ-ONLY RULE)
# =====================================================================

def test_zero_order_placement_symbols_exist():
    """Scan all source code files to verify the system has zero order placement / modification calls."""
    forbidden = ["place_order", "cancel_order", "modify_order", ".place("]
    violations = []

    for root, dirs, files in os.walk(BASE_DIR):
        # Ignore git, caches, and test files themselves
        for d in [".git", "__pycache__", ".pytest_cache"]:
            if d in dirs:
                dirs.remove(d)

        for file in files:
            if file.endswith((".py", ".js", ".html", ".sh", ".bat")):
                # Skip the test file scanning itself
                if file in ("test_phase1_safety.py",):
                    continue

                filepath = Path(root) / file
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                for term in forbidden:
                    if term in content:
                        violations.append(f"{filepath.relative_to(BASE_DIR)} contains '{term}'")

    assert len(violations) == 0, f"Found forbidden order placement symbols: {violations}"

