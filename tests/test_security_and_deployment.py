"""
Comprehensive Security, Tunnel, and Deployment Test Suite
Verifies:
1. Git & Secrets Protection (.gitignore, .env.example)
2. Vercel & Render Deployment Blueprints (vercel.json, render.yaml, Procfile, requirements.txt)
3. CORS, Security Headers, and Chrome Private Network Access
4. Tunnel Authentication and Ngrok Bypass Header Integration
5. API Input Sanitization and Malicious Input Resilience
6. AI Model Inference, Calibrated Probabilities, and Reason Generation
"""

import os
import sys
import json
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure root workspace is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings, update_settings
from backend.app import app as backend_app
from ai.server import app as ai_app
from ai.model import ai_model


client_backend = TestClient(backend_app)
client_ai = TestClient(ai_app)


# =====================================================================
# 1. SECRETS & GIT REPOSITORY SECURITY CHECKS
# =====================================================================

def test_gitignore_protects_secrets():
    """Verify .gitignore exists and strictly excludes credentials and env files."""
    gitignore_path = BASE_DIR / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist to prevent accidental secret leakage"

    content = gitignore_path.read_text(encoding="utf-8")
    must_exclude = [".env", "*.log", "daily_predictions.jsonl", "*.key", "__pycache__"]
    for pattern in must_exclude:
        assert pattern in content, f".gitignore must contain '{pattern}' for security"


def test_env_example_has_zero_secrets():
    """Verify .env.example contains only dummy placeholders and no real API tokens."""
    env_example = BASE_DIR / ".env.example"
    assert env_example.exists()

    content = env_example.read_text(encoding="utf-8")
    assert "your_consumer_key_here" in content or "KOTAK_CONSUMER_KEY=" in content
    # Ensure no active production passwords or tokens are checked in
    forbidden_tokens = ["secret_live_", "eyJh", "ghp_"]
    for t in forbidden_tokens:
        assert t not in content


def test_requirements_contains_all_production_dependencies():
    """Verify requirements.txt contains all core machine learning & server packages."""
    req_path = BASE_DIR / "requirements.txt"
    assert req_path.exists()
    content = req_path.read_text(encoding="utf-8").lower()

    required_pkgs = ["fastapi", "uvicorn", "pydantic", "pandas", "numpy", "scikit-learn", "joblib", "requests"]
    for pkg in required_pkgs:
        assert pkg in content, f"requirements.txt missing required package: {pkg}"


# =====================================================================
# 2. VERCEL & RENDER DEPLOYMENT BLUEPRINTS
# =====================================================================

def test_vercel_json_configuration():
    """Verify vercel.json is syntactically valid and routes static frontend assets properly."""
    vercel_path = BASE_DIR / "vercel.json"
    assert vercel_path.exists(), "vercel.json is required for Vercel deployment"

    data = json.loads(vercel_path.read_text(encoding="utf-8"))
    assert data.get("version") == 2
    assert "rewrites" in data
    # Verify rewrite destinations point to /frontend/
    rewrites = data["rewrites"]
    destinations = [r.get("destination", "") for r in rewrites]
    assert any("/frontend/" in d for d in destinations), "vercel.json must route requests to /frontend/"


def test_render_yaml_configuration():
    """Verify render.yaml and Procfile are configured with proper build and start commands."""
    render_yaml_path = BASE_DIR / "render.yaml"
    procfile_path = BASE_DIR / "Procfile"

    assert render_yaml_path.exists(), "render.yaml is required for Render deployment"
    assert procfile_path.exists(), "Procfile is required for standard PaaS process management"

    render_content = render_yaml_path.read_text(encoding="utf-8")
    assert "pip install -r requirements.txt" in render_content
    assert "$PORT" in render_content

    procfile_content = procfile_path.read_text(encoding="utf-8")
    assert "uvicorn backend.app:app" in procfile_content
    assert "$PORT" in procfile_content


# =====================================================================
# 3. CORS, PNA & SECURITY HEADERS
# =====================================================================

def test_backend_security_headers():
    """Verify security headers (nosniff, SAMEORIGIN, etc.) are attached to backend responses."""
    resp = client_backend.get("/api/status")
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "SAMEORIGIN"


def test_backend_cors_for_vercel_domains():
    """Verify backend allows cross-origin requests from Vercel deployments."""
    resp = client_backend.options(
        "/api/status",
        headers={
            "Origin": "https://my-trading-app.vercel.app",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert resp.status_code == 200
    allow_origin = resp.headers.get("access-control-allow-origin")
    assert allow_origin in ("*", "https://my-trading-app.vercel.app")


def test_ai_server_private_network_access():
    """Verify AI Microservice responds to Chrome Private Network Access preflights."""
    resp = client_ai.options(
        "/api/ai/predict",
        headers={
            "Origin": "https://my-app.vercel.app",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Private-Network": "true"
        }
    )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-private-network") == "true"


# =====================================================================
# 4. TUNNEL AUTHENTICATION & NGROK INTEGRATION
# =====================================================================

def test_ai_server_open_mode_when_no_token():
    """When AI_SECRET_TOKEN is empty, server allows local/development requests."""
    orig_token = settings.ai_secret_token
    try:
        update_settings({"ai_secret_token": None})
        resp = client_ai.get("/api/ai/predict")
        assert resp.status_code == 200
        assert resp.json().get("success") is True
    finally:
        update_settings({"ai_secret_token": orig_token})


def test_ai_server_token_enforcement_when_configured():
    """When AI_SECRET_TOKEN is configured, verify unauthenticated tunnel calls return 401."""
    test_secret = "super_secure_tunnel_token_12345"
    orig_token = settings.ai_secret_token
    try:
        update_settings({"ai_secret_token": test_secret})

        # Request WITHOUT token -> 401 Unauthorized
        resp_unauth = client_ai.get("/api/ai/predict")
        assert resp_unauth.status_code == 401
        assert "Unauthorized" in resp_unauth.json().get("detail", "")

        # Request WITH valid X-AI-Secret-Token -> 200 OK
        resp_auth = client_ai.get(
            "/api/ai/predict",
            headers={"X-AI-Secret-Token": test_secret, "ngrok-skip-browser-warning": "1"}
        )
        assert resp_auth.status_code == 200
        assert resp_auth.json().get("success") is True
    finally:
        update_settings({"ai_secret_token": orig_token})


# =====================================================================
# 5. INPUT SANITIZATION & INJECTION DEFENSE
# =====================================================================

def test_malicious_symbol_injection_defense():
    """Verify backend safely handles attempts at path traversal and SQL injection in symbol."""
    malicious_inputs = [
        "../../etc/passwd",
        "'; DROP TABLE USERS; --",
        "<script>alert('XSS')</script>",
        "../../../eternal_ai_model.joblib"
    ]
    for bad_sym in malicious_inputs:
        resp = client_backend.get(f"/api/market-data?symbol={bad_sym}&range_period=5d")
        # Should gracefully return valid status or 404/400 error, never crash or leak system files
        assert resp.status_code in (200, 400, 404)


def test_invalid_config_update_validation():
    """Verify pydantic schema prevents invalid types and malformed config payloads."""
    # Attempt string in integer field
    bad_payload = {"ema_fast": "NOT_AN_INTEGER"}
    resp = client_backend.post("/api/config", json=bad_payload)
    assert resp.status_code == 422  # Unprocessable Entity (Pydantic validation error)


# =====================================================================
# 6. MODEL INTEGRITY & EXPLAINABLE REASON GENERATION
# =====================================================================

def test_ai_model_loaded_and_predicts_correctly():
    """Verify local AI model is loaded, generates calibrated probabilities, and explains reasons."""
    resp = client_ai.get("/api/ai/predict")
    assert resp.status_code == 200
    data = resp.json()

    assert data.get("signal") in ("BUY", "SELL", "HOLD")
    assert 0.0 <= data.get("confidence", 0.0) <= 100.0
    assert data.get("model_accuracy", 0.0) > 0.0
    assert len(data.get("reason", "")) > 10, "Decision reason must be descriptive and plain-English"

    # Probabilities must sum to ~100%
    probs = data.get("probabilities", {})
    total_prob = sum(probs.values())
    assert 99.0 <= total_prob <= 101.0, f"Class probabilities should sum to 100% (got {total_prob})"


def test_accuracy_trend_endpoint():
    """Verify accuracy trend returns historical learning array for frontend charts."""
    resp = client_ai.get("/api/ai/accuracy-trend")
    assert resp.status_code == 200
    data = resp.json()
    assert "history" in data
    assert isinstance(data["history"], list)


# =====================================================================
# 7. DYNAMIC TUNNEL REGISTRATION & KOTAK ORDER SAFETY TESTS
# =====================================================================

def test_dynamic_tunnel_registration_endpoint():
    """Verify POST /api/ai/register-tunnel updates backend's AI service URL in memory dynamically."""
    orig_url = settings.ai_model_service_url
    orig_token = settings.ai_secret_token
    try:
        # 1. Successful registration without token
        update_settings({"ai_secret_token": None})
        resp = client_backend.post(
            "/api/ai/register-tunnel",
            json={"tunnel_url": "https://portable-desktop-2.ngrok-free.app"}
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert settings.ai_model_service_url == "https://portable-desktop-2.ngrok-free.app"

        # 2. Token protection when token configured
        test_token = "secret_handshake_token_999"
        update_settings({"ai_secret_token": test_token})

        # Request missing token -> 401
        resp_unauth = client_backend.post(
            "/api/ai/register-tunnel",
            json={"tunnel_url": "https://portable-desktop-3.ngrok-free.app"}
        )
        assert resp_unauth.status_code == 401

        # Request with valid token in body -> 200
        resp_auth = client_backend.post(
            "/api/ai/register-tunnel",
            json={"tunnel_url": "https://portable-desktop-3.ngrok-free.app", "secret_token": test_token}
        )
        assert resp_auth.status_code == 200
        assert settings.ai_model_service_url == "https://portable-desktop-3.ngrok-free.app"

        # 3. Invalid URL scheme rejected
        resp_bad = client_backend.post(
            "/api/ai/register-tunnel",
            json={"tunnel_url": "ftp://malicious-scheme.com", "secret_token": test_token}
        )
        assert resp_bad.status_code == 400

    finally:
        update_settings({"ai_model_service_url": orig_url, "ai_secret_token": orig_token})


def test_kotak_trading_symbol_formatting():
    """Verify Kotak Neo adapter correctly formats Yahoo tickers into NSE cash scrips."""
    from execution.engine import engine
    assert engine.kotak.get_trading_symbol("TATAMOTORS.NS") == "TATAMOTORS-EQ"
    assert engine.kotak.get_trading_symbol("RELIANCE.NS") == "RELIANCE-EQ"
    assert engine.kotak.get_trading_symbol("INFY-EQ") == "INFY-EQ"


def test_real_money_auto_orders_completely_disabled():
    """Verify autonomous order placement is strictly removed and rejected by the API."""
    # Attempting to post to /api/orders/place should be 404/405 (endpoint completely removed)
    resp = client_backend.post(
        "/api/orders/place",
        json={"symbol": "TATAMOTORS-EQ", "quantity": 1, "transaction_type": "B"}
    )
    assert resp.status_code in (404, 405)

    from execution.engine import engine
    # Switching to LIVE autonomous mode is rejected
    res_live = engine.set_mode("LIVE")
    assert res_live.get("success") is False

    # Switching to GUIDER mode is allowed and enforces real_orders_enabled=False
    res_guider = engine.set_mode("GUIDER")
    assert res_guider.get("success") is True
    assert settings.real_orders_enabled is False


def test_guider_mode_directive_generation():
    """Verify GUIDER mode produces actionable human guidance directives without auto-trading."""
    from execution.engine import engine
    orig_mode = settings.agent_mode
    orig_real = settings.real_orders_enabled
    try:
        update_settings({"agent_mode": "GUIDER", "real_orders_enabled": False})
        res = engine.run_single_analysis()
        assert res.get("success") is True
        dec = res.get("decision", {})
        assert "directive" in dec
        assert "human_guidance" in dec
        assert dec.get("real_orders_enabled") is False
        assert dec.get("order_result") is None  # Zero auto-trading
    finally:
        update_settings({"agent_mode": orig_mode, "real_orders_enabled": orig_real})


def test_strict_1_to_3_risk_reward_and_1000_shares():
    """Verify trade brackets enforce exact 1:3 profit-to-loss ratio on fixed 1,000 shares."""
    from core.risk_manager import calculate_trade_brackets

    # Test BUY brackets
    brackets_buy = calculate_trade_brackets(entry_price=100.0, atr=2.0, side="BUY")
    assert brackets_buy["risk_reward_ratio"] == "1:3.00"
    assert brackets_buy["suggested_quantity"] == 1000
    assert brackets_buy["risk_per_share"] == 2.0  # 1.0 * ATR
    assert brackets_buy["reward_per_share"] == 6.0  # 3.0 * risk
    assert brackets_buy["stop_loss"] == 98.0
    assert brackets_buy["target"] == 106.0
    assert brackets_buy["estimated_max_risk_rupees"] == 2000.0  # 1000 * 2.0
    assert brackets_buy["estimated_target_profit_rupees"] == 6000.0  # 1000 * 6.0 (3x risk!)

    # Test SELL brackets
    brackets_sell = calculate_trade_brackets(entry_price=200.0, atr=3.0, side="SELL")
    assert brackets_sell["risk_reward_ratio"] == "1:3.00"
    assert brackets_sell["suggested_quantity"] == 1000
    assert brackets_sell["risk_per_share"] == 3.0
    assert brackets_sell["reward_per_share"] == 9.0
    assert brackets_sell["stop_loss"] == 203.0
    assert brackets_sell["target"] == 191.0
    assert brackets_sell["estimated_max_risk_rupees"] == 3000.0
    assert brackets_sell["estimated_target_profit_rupees"] == 9000.0  # 3x risk!


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    all_tests = [
        test_gitignore_protects_secrets,
        test_env_example_has_zero_secrets,
        test_requirements_contains_all_production_dependencies,
        test_vercel_json_configuration,
        test_render_yaml_configuration,
        test_backend_security_headers,
        test_backend_cors_for_vercel_domains,
        test_ai_server_private_network_access,
        test_ai_server_open_mode_when_no_token,
        test_ai_server_token_enforcement_when_configured,
        test_malicious_symbol_injection_defense,
        test_invalid_config_update_validation,
        test_ai_model_loaded_and_predicts_correctly,
        test_accuracy_trend_endpoint,
        test_dynamic_tunnel_registration_endpoint,
        test_kotak_trading_symbol_formatting,
        test_real_money_auto_orders_completely_disabled,
        test_guider_mode_directive_generation,
        test_strict_1_to_3_risk_reward_and_1000_shares,
    ]

    passed, failed = 0, 0
    for test_fn in all_tests:
        try:
            test_fn()
            print(f"[PASS] {test_fn.__name__}")
            passed += 1
        except Exception as err:
            print(f"[FAIL] {test_fn.__name__}: {err}")
            failed += 1

    print(f"\nFinal Test Results: {passed} passed, {failed} failed.")
    sys.exit(failed)
