# ⚡ ETERNAL AI Trading Agent — PRO
### Unified Intraday Momentum & Autonomous Machine Learning Engine (NSE / Kotak Neo)

An algorithmic, quantitative trading engine designed for National Stock Exchange (NSE) equities, featuring an authentic **autonomous self-learning AI model**, explainable decision logic, and a **3-tier hybrid deployment architecture**:
- **Frontend**: Hosted on **Vercel** (Responsive Financial Web Terminal)
- **Backend**: Hosted on **Render** (FastAPI REST API & Paper/Live Execution Engine)
- **AI Model**: Runs **100% locally on your PC** via **Tunnel** (ngrok / Cloudflare) with **zero cloud AI or Hugging Face fees**

---

## 🌟 Key Features

1. **Autonomous Self-Learning Machine Learning Layer**:
   - Initial walk-forward training across **6 months of historical data**.
   - **Zero manual train buttons**: Daily walk-forward retraining triggers automatically at **15:30 IST (Indian Market Close)**.
   - Outputs calibrated class probabilities: **BUY**, **SELL**, **HOLD**, with **Confidence %** and **Model Accuracy %**.
   - Generates plain-English **decision explanations** for every signal.
2. **Hybrid Cloud Deployment Architecture**:
   - **Vercel**: Hosts the static web UI with dynamic endpoint switcher (`vercel.json` included).
   - **Render**: Hosts the FastAPI backend with `$PORT` dynamic binding and CORS (`render.yaml` & `Procfile` included).
   - **Localhost + Tunnel**: AI runs locally on port `8001`, exposed to Render via `ngrok` or `cloudflared`.
3. **1-Click Windows Launchers**:
   - [`start.bat`](start.bat): Master interactive launcher (Full Stack, Local AI, Tunnel, or Backtest).
   - [`start_ai_tunnel.bat`](start_ai_tunnel.bat): Dedicated 1-click launcher with ngrok/cloudflared detection.
   - [`start_ai_model.bat`](start_ai_model.bat): Dedicated local AI microservice launcher.
4. **Pure RSI 9 & 14 Backtesting Engine**:
   - Vectorized 6-month historical simulation without EMA or VWAP lag.
5. **Multi-Layer Safety Engine**:
   - `REAL_ORDERS_ENABLED = False` by default (Paper Trading safe).
   - Emergency Stop kill-switch and stale data age validation (< 180s).
   - Strict session square-off (no overnight risk).

---

## 📁 Clean Project Structure

```
d:\update\New folder\
├── config.py                 # Central settings & dynamic runtime config (Pydantic)
├── .env.example              # Environment variables template (no hardcoding)
├── .gitignore                # Strictly excludes secrets, logs, and cache
├── requirements.txt          # Production dependencies (FastAPI, Scikit-Learn, Pandas)
├── Procfile                  # PaaS start command for Render / Heroku
├── render.yaml               # Render Blueprint web service specification
├── vercel.json               # Vercel routing, rewrites & security headers
├── cli.py                    # Complete CLI terminal interface
├── eternal.py                # Backward-compatible unified script & dispatcher
├── eternal_ai_model.joblib   # Local Scikit-Learn machine learning weights
├── model_learning_history.json # Day-by-day learning milestone log
│
├── start.bat                 # 1-Click Master Launcher (Menu / Flags)
├── start_ai_tunnel.bat       # 1-Click AI Server + Cloud Tunnel (ngrok)
├── start_ai_model.bat        # 1-Click Local-Only AI Server (Port 8001)
│
├── frontend/                 # Vercel-ready Web Dashboard
│   ├── index.html            # Dark-theme financial terminal UI
│   ├── style.css             # Terminal stylesheet
│   ├── app.js                # State management, endpoint switcher & canvas charts
│   └── vercel.json           # Subfolder Vercel configuration
│
├── backend/                  # Render-ready FastAPI REST API
│   ├── app.py                # High-performance endpoints, background worker, CORS
│   └── schemas.py            # Pydantic request & response validation schemas
│
├── ai/                       # Localhost Machine Learning Engine
│   ├── server.py             # Dedicated Port 8001 microservice & tunnel bridge
│   ├── model.py              # HistGradientBoosting classifier & calibrated probabilities
│   ├── feature_extractor.py  # 30+ non-lagging technical & momentum features
│   ├── explainer.py          # Explainable plain-English decision reason generator
│   └── auto_learner.py       # Autonomous 3:30 PM IST daily retraining pipeline
│
├── core/                     # Quantitative Strategy Engine
│   ├── indicators.py         # EMA20, EMA50, VWAP (daily reset), RSI14, ATR14
│   ├── strategy.py           # Signal evaluation (BUY / SELL / WAIT)
│   ├── risk_manager.py       # ATR brackets, position sizing & safety gates
│   ├── backtester.py         # Realistic event-driven 5m backtest simulator
│   └── rsi_engine.py         # Pure RSI 9 & 14 strategy & 6-month backtest
│
├── data/                     # Market Data Pipeline
│   ├── fetcher.py            # Yahoo Finance REST client + offline fallback
│   └── kotak_client.py       # Kotak Neo API SDK adapter with TOTP login
│
├── execution/                # Trade Execution & Safety Gating
│   ├── engine.py             # Agent state machine (IDLE, RUNNING, PAUSED, STOPPED)
│   └── logger.py             # Append-only paper trade audit logger
│
└── tests/                    # Security & Deployment Test Suite
    └── test_security_and_deployment.py # 14 Automated verification checks
```

---

## 🚀 How to Host: Step-by-Step Instructions

### Step 1: Start Your Local AI Model & Tunnel (Local PC)
1. Double-click **[`start_ai_tunnel.bat`](start_ai_tunnel.bat)** on your PC.
2. It boots the AI server on `http://127.0.0.1:8001` and opens your tunnel (`ngrok http 8001` or `cloudflared`).
3. Copy your public forwarding HTTPS URL (e.g. `https://your-tunnel.ngrok-free.app`).

### Step 2: Deploy Backend to Render
1. Push this repository to GitHub.
2. In [Render.com](https://render.com), create a **New Web Service** from your repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
5. In **Environment Variables**, set:
   ```ini
   AI_MODEL_SERVICE_URL=https://your-tunnel.ngrok-free.app
   AGENT_MODE=PAPER
   CORS_ORIGINS=*
   ```
6. Click **Deploy** and copy your Render URL (e.g., `https://eternal-trading-backend.onrender.com`).

### Step 3: Deploy Frontend to Vercel
1. In [Vercel.com](https://vercel.com), click **Add New...** -> **Project** and select your repo.
2. Click **Deploy** (the included `vercel.json` handles static routing).
3. Open your Vercel URL in Chrome, go to the **Settings** tab:
   - In **Render Backend REST API Endpoint**, paste your Render URL and click **Save Backend**.
   - In **Localhost AI Model / Tunnel URL**, paste your tunnel URL and click **Save AI**.
   - Click **Test Backend** and **Test AI** to verify active connection.

---

## 🧪 Run Automated Security & Integration Tests

To run the full 14-test verification suite locally:
```bash
python -c "import sys; from tests.test_security_and_deployment import *; [print('[PASS]', t.__name__) for t in [test_gitignore_protects_secrets, test_env_example_has_zero_secrets, test_requirements_contains_all_production_dependencies, test_vercel_json_configuration, test_render_yaml_configuration, test_backend_security_headers, test_backend_cors_for_vercel_domains, test_ai_server_private_network_access, test_ai_server_open_mode_when_no_token, test_ai_server_token_enforcement_when_configured, test_malicious_symbol_injection_defense, test_invalid_config_update_validation, test_ai_model_loaded_and_predicts_correctly, test_accuracy_trend_endpoint] if not t()]"
```
Or simply double-click `start.bat` and select **Option 6**!
