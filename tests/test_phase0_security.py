"""
Phase 0 Security & Reliability Test Suite
Covers:
1. ADMIN_API_KEY_BROKER enforcement & masking (401 on missing/invalid, absent from public_dict)
2. STRICT_SECRETS validation (fails on placeholder secrets when strict mode enabled)
3. Logs limit capping (max 500) and truthful count (len(logs))
4. Audit log preservation in archive/ on clear_logs
5. In-Memory Rate Limiter (sliding window returns 429 when threshold exceeded)
6. CORS strictness and Private Network Access origin reflection filtering
7. Persistent emergency stop file (emergency_stop.lock) and refusal of advisories
8. Input validation allow-lists (range_period, interval) and Pydantic constraints
9. Blocking of dynamic symbol change in /api/config
10. Cloudflared SHA256 checksum verification
"""

import os
import sys
import tempfile
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from fastapi import HTTPException, Request

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import Settings, settings, update_settings
from data.fetcher import fetch_historical_candles
from execution.logger import clear_logs, get_recent_logs
from execution.engine import ExecutionEngine
from backend.schemas import ConfigUpdateRequest
from backend.app import app as backend_app, InMemoryRateLimiter, verify_broker_key
from ai.server import app as ai_app, is_allowed_origin
from ai.tunnel_manager import compute_file_sha256, PINNED_CLOUDFLARED_SHA256


client_backend = TestClient(backend_app)
client_ai = TestClient(ai_app)
ADMIN_HEADERS = {"X-Admin-Key": settings.admin_api_key or "admin_aa3797c179a6236618316e26"}


# =====================================================================
# 1. BROKER KEY ENFORCEMENT & SECRET MASKING
# =====================================================================

def test_broker_key_enforcement():
    """Verify that when ADMIN_API_KEY_BROKER is set, broker operations require X-Broker-Key."""
    test_broker_key = "broker_super_secret_key_456"
    orig_broker_key = settings.admin_api_key_broker

    try:
        settings.admin_api_key_broker = test_broker_key

        # Missing broker key header should return 401
        res = client_backend.get("/api/orders/positions", headers=ADMIN_HEADERS)
        assert res.status_code == 401
        assert "X-Broker-Key" in res.json()["detail"]

        # Invalid broker key should return 401
        headers_invalid = {**ADMIN_HEADERS, "X-Broker-Key": "wrong_key"}
        res = client_backend.get("/api/orders/positions", headers=headers_invalid)
        assert res.status_code == 401

        # Valid broker key should pass auth check (status 200)
        headers_valid = {**ADMIN_HEADERS, "X-Broker-Key": test_broker_key}
        res = client_backend.get("/api/orders/positions", headers=headers_valid)
        assert res.status_code == 200
    finally:
        settings.admin_api_key_broker = orig_broker_key


def test_broker_key_masked_in_public_dict():
    """Verify admin_api_key_broker is in secret_keys and omitted from public_dict."""
    pub = settings.public_dict()
    assert "admin_api_key_broker" not in pub
    assert "admin_api_key" not in pub
    assert "kotak_consumer_secret" not in pub


# =====================================================================
# 2. STRICT SECRETS VALIDATION
# =====================================================================

def test_strict_secrets_validation():
    """Verify that placeholder secrets raise RuntimeError when STRICT_SECRETS is enabled."""
    from backend.app import validate_strict_secrets
    cfg = Settings(
        strict_secrets=True,
        admin_api_key="admin_aa3797c179a6236618316e26",
    )
    with pytest.raises(RuntimeError, match="ADMIN_API_KEY must be set to a custom"):
        validate_strict_secrets(cfg)


# =====================================================================
# 3. LOGS LIMIT CAPPING & TRUTHFUL COUNT
# =====================================================================

def test_logs_limit_capping_and_actual_count():
    """Verify /api/logs caps limit at 500 and returns count equal to actual returned items."""
    res = client_backend.get("/api/logs?limit=999")
    assert res.status_code == 200
    data = res.json()
    assert data["limit"] == 500
    assert data["count"] == len(data["logs"])
    assert data["count"] <= 500


# =====================================================================
# 4. AUDIT LOG PRESERVATION ON CLEAR
# =====================================================================

def test_clear_logs_preserves_audit_trail_in_archive():
    """Verify clear_logs moves the file to archive/ rather than unlinking/deleting."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_log_file = tmp_path / "paper_analysis_journal.csv"
        test_log_file.write_text("timestamp,symbol,mode,signal,price\n2026-11-04,ETERNAL,PAPER,BUY,100\n", encoding="utf-8")

        mock_config = Settings(paper_log_file=str(test_log_file))

        # Clear logs
        success = clear_logs(config=mock_config)
        assert success is True

        # Verify archive directory is created and holds the timestamped file
        archive_dir = tmp_path / "archive"
        assert archive_dir.exists()
        archived_files = list(archive_dir.glob("paper_analysis_journal_*.csv"))
        assert len(archived_files) == 1
        content = archived_files[0].read_text(encoding="utf-8")
        assert "ETERNAL" in content


# =====================================================================
# 5. IN-MEMORY RATE LIMITER
# =====================================================================

def test_in_memory_rate_limiter():
    """Verify rate limiter raises 429 when request threshold is exceeded."""
    limiter = InMemoryRateLimiter(max_requests=3, window_seconds=60.0)

    # Mock request with non-loopback IP to test rate limiting logic
    mock_req = MagicMock(spec=Request)
    mock_req.client = MagicMock()
    mock_req.client.host = "198.51.100.5"

    # Turn off dev_mode for the test
    orig_dev = settings.dev_mode
    try:
        settings.dev_mode = False
        assert limiter.check(mock_req) is True
        assert limiter.check(mock_req) is True
        assert limiter.check(mock_req) is True

        with pytest.raises(HTTPException) as exc_info:
            limiter.check(mock_req)
        assert exc_info.value.status_code == 429
    finally:
        settings.dev_mode = orig_dev


# =====================================================================
# 6. CORS STRICTNESS & PRIVATE NETWORK ACCESS
# =====================================================================

def test_cors_strictness_and_origin_validation():
    """Verify is_allowed_origin respects cors_origins_strict setting."""
    orig_strict = settings.cors_origins_strict
    try:
        settings.cors_origins_strict = True
        # Under strict mode, arbitrary vercel subdomains should NOT be permitted
        assert is_allowed_origin("https://arbitrary-attacker.vercel.app") is False
        assert is_allowed_origin("http://localhost:8000") is True

        settings.cors_origins_strict = False
        assert is_allowed_origin("https://my-app.vercel.app") is True
    finally:
        settings.cors_origins_strict = orig_strict


def test_ai_server_pna_rejects_unallowed_origin():
    """Verify PrivateNetworkAccessMiddleware does not reflect unallowed origins."""
    res = client_ai.options(
        "/health",
        headers={
            "Origin": "https://malicious-attacker.com",
            "Access-Control-Request-Private-Network": "true",
            "Access-Control-Request-Method": "GET",
        }
    )
    assert res.headers.get("Access-Control-Allow-Private-Network") != "true"
    assert res.headers.get("Access-Control-Allow-Origin") != "https://malicious-attacker.com"


# =====================================================================
# 7. PERSISTENT EMERGENCY STOP
# =====================================================================

def test_persistent_emergency_stop():
    """Verify emergency stop creates lock file, halts analysis, and survives restart."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        lock_file_path = tmp_path / "test_emergency.lock"
        mock_cfg = Settings(emergency_stop_file=str(lock_file_path))

        engine = ExecutionEngine(config=mock_cfg)
        assert engine.state != "EMERGENCY_STOPPED"

        # Trigger emergency stop
        res = engine.emergency_stop()
        assert res["success"] is True
        assert engine.state == "EMERGENCY_STOPPED"
        assert lock_file_path.exists()

        # Analysis must be refused during emergency stop
        analysis_res = engine.run_single_analysis()
        assert analysis_res.get("advisory_refused") is True
        assert analysis_res.get("state") == "EMERGENCY_STOPPED"
        assert analysis_res.get("decision", {}).get("action") == "EMERGENCY_STOPPED"

        # Restarting engine must detect lock file and restore EMERGENCY_STOPPED
        new_engine = ExecutionEngine(config=mock_cfg)
        assert new_engine.state == "EMERGENCY_STOPPED"

        # Reset removes lock file
        reset_res = new_engine.reset()
        assert reset_res["success"] is True
        assert not lock_file_path.exists()
        assert new_engine.state == "IDLE"


# =====================================================================
# 8. INPUT VALIDATION ALLOW-LISTS & CONSTRAINTS
# =====================================================================

def test_fetch_historical_candles_rejects_unallowed_inputs():
    """Verify fetch_historical_candles rejects invalid range_period or interval."""
    with pytest.raises(ValueError, match="Invalid range_period"):
        fetch_historical_candles("ETERNAL.NS", range_period="100y", interval="5m")

    with pytest.raises(ValueError, match="Invalid interval"):
        fetch_historical_candles("ETERNAL.NS", range_period="5d", interval="45m")


def test_config_update_request_cross_field_validations():
    """Verify Pydantic cross-field constraints on indicators."""
    # ema_fast must be less than ema_slow
    with pytest.raises(ValidationError):
        ConfigUpdateRequest(ema_fast=50, ema_slow=20)

    # rsi_buy_min must be less than rsi_buy_max
    with pytest.raises(ValidationError):
        ConfigUpdateRequest(rsi_buy_min=75, rsi_buy_max=70)

    # target_atr_mult must be greater than stop_loss_atr_mult
    with pytest.raises(ValidationError):
        ConfigUpdateRequest(stop_loss_atr_mult=2.5, target_atr_mult=1.5)


def test_symbol_change_blocked_via_api():
    """Verify /api/config blocks changing symbol to prevent token mismatch."""
    res = client_backend.post(
        "/api/config",
        headers=ADMIN_HEADERS,
        json={"symbol": "INFY.NS"}
    )
    assert res.status_code == 400
    assert "Symbol change via API is blocked" in res.json()["detail"]


# =====================================================================
# 9. CLOUDFLARED SHA256 VERIFICATION
# =====================================================================

def test_cloudflared_sha256_verification():
    """Verify compute_file_sha256 computes accurate SHA256 checksum."""
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"cloudflared binary test payload")
        tf_path = Path(tf.name)

    try:
        calculated_hash = compute_file_sha256(tf_path)
        expected_hash = hashlib.sha256(b"cloudflared binary test payload").hexdigest()
        assert calculated_hash == expected_hash
    finally:
        tf_path.unlink(missing_ok=True)


# =====================================================================
# 10. ANTIVIRUS-SAFE OPENSSH TUNNEL PRIORITY & BEHAVIOR
# =====================================================================

def test_openssh_tunnel_priority_over_cloudflare(monkeypatch):
    """Verify start_tunnel() prioritizes OpenSSH over Cloudflare to avoid downloading .exe files."""
    from ai.tunnel_manager import start_tunnel

    call_order = []

    def mock_ngrok():
        return None

    def mock_ssh(port):
        call_order.append("ssh")
        return "https://antivirus-safe-tunnel.lhr.life"

    def mock_cf(port):
        call_order.append("cloudflare")
        return "https://cloudflared.trycloudflare.com"

    monkeypatch.setattr("ai.tunnel_manager.get_existing_ngrok_url", mock_ngrok)
    monkeypatch.setattr("ai.tunnel_manager.start_ssh_tunnel", mock_ssh)
    monkeypatch.setattr("ai.tunnel_manager.start_cloudflare_tunnel", mock_cf)
    monkeypatch.setattr(settings, "ngrok_authtoken", None)

    url = start_tunnel(8001)
    assert url == "https://antivirus-safe-tunnel.lhr.life"
    assert call_order == ["ssh"], "OpenSSH should be called BEFORE Cloudflare to prevent Quick Heal quarantine"


def test_cloudflare_tunnel_handles_antivirus_quarantine(monkeypatch):
    """Verify start_cloudflare_tunnel gracefully catches PermissionError / WinError 225."""
    from ai.tunnel_manager import start_cloudflare_tunnel

    def mock_quarantined_download():
        raise PermissionError("Access is denied (quarantined by antivirus)")

    monkeypatch.setattr("ai.tunnel_manager.get_or_download_cloudflared", mock_quarantined_download)
    url = start_cloudflare_tunnel(8001)
    assert url is None


# =====================================================================
# 11. NO HARDCODED METRICS & ACCURATE TIMESTAMPS
# =====================================================================

def test_model_no_fabricated_fallbacks(tmp_path):
    """Verify EternalAIModel defaults to None, not fabricated 68.4% / 90.7%."""
    from ai.model import EternalAIModel
    import joblib

    empty_model_path = tmp_path / "test_model.joblib"
    joblib.dump({"model": None, "features": [], "accuracy": 35.0}, empty_model_path)

    m = EternalAIModel(model_path=empty_model_path)
    assert m.last_accuracy == 35.0
    assert m.high_conf_accuracy is None, "high_conf_accuracy must not default to hardcoded 68.4"
    assert m.regime_accuracy is None, "regime_accuracy must not default to hardcoded 90.7"


def test_predict_includes_genuine_timestamps():
    """Verify prediction includes genuine candle_timestamp and prediction_timestamp."""
    from ai.model import ai_model
    import pandas as pd
    import numpy as np

    if ai_model.model is None:
        pytest.skip("AI model is not trained yet")

    # Generate small sample DataFrame with DatetimeIndex
    dates = pd.date_range("2026-11-05 09:15", periods=50, freq="5min", tz="Asia/Kolkata")
    df = pd.DataFrame({
        "open": np.linspace(350, 355, 50),
        "high": np.linspace(351, 356, 50),
        "low": np.linspace(349, 354, 50),
        "close": np.linspace(350.5, 355.5, 50),
        "volume": [1000] * 50
    }, index=dates)

    pred = ai_model.predict(df)
    assert "candle_timestamp" in pred
    assert pred["candle_timestamp"] is not None
    assert "2026-11-05" in pred["candle_timestamp"]
    assert "prediction_timestamp" in pred
    assert pred["prediction_timestamp"] is not None



