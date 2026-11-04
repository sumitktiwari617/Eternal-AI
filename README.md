# ⚡ ETERNAL AI Trading Agent — PRO
### Unified Intraday Advisory & Autonomous Machine Learning Engine (NSE / Kotak Neo)

An algorithmic, quantitative trading advisory engine designed for National Stock Exchange (NSE) equities, featuring an authentic **autonomous self-learning AI model**, explainable decision logic, and a **3-tier hybrid deployment architecture**:

- 🌐 **Frontend**: Hosted on **Vercel** ([`frontend/`](frontend/README.md)) — Responsive Financial Web Terminal.
- ☁️ **Backend**: Hosted on **Render** ([`RENDER_DEPLOY_GUIDE.md`](RENDER_DEPLOY_GUIDE.md)) — FastAPI REST API with paper execution & risk controls.
- 💻 **AI Model**: Runs on your **Laptop / PC** ([`LAPTOP_AI_TUNNEL_GUIDE.md`](LAPTOP_AI_TUNNEL_GUIDE.md)) via **Tunnel** ([`start.bat`](start.bat)) with **zero cloud AI fees**.

---

## 🌟 Key Features

1. **Strictly Read-Only Advisory**:
   - `real_orders_enabled` is hard-locked to `False`. All execution is simulated paper trading.
   - Comprehensive safety checks fail closed on stale or missing data.
2. **Autonomous Machine Learning Layer**:
   - Walk-forward training with HistGradientBoosting classifier.
   - Retraining triggers automatically at **15:30 IST (Indian Market Close)** on weekdays.
   - Calibrated class probabilities (**BUY**, **SELL**, **WAIT**) with ATR brackets.
   - Generates plain-English **decision explanations** for every signal.
3. **Hybrid Cloud Deployment Architecture**:
   - **Vercel**: Hosts the static web UI with dynamic endpoint switcher ([`frontend/`](frontend/)).
   - **Render**: Hosts the FastAPI backend with `$PORT` dynamic binding and CORS ([`render.yaml`](render.yaml) & [`Procfile`](Procfile)).
   - **Laptop + Tunnel**: AI runs locally on port `8001`, exposed to Render via `ngrok` or `cloudflared`.
4. **1-Click Windows Launchers**:
   - [`start.bat`](start.bat): Master 1-click launcher (Default: Laptop AI Model + Cloud Tunnel).
   - [`start_ai_tunnel.bat`](start_ai_tunnel.bat): Dedicated AI server + ngrok tunnel bridge with auto-handshake.
   - [`start_ai_model.bat`](start_ai_model.bat): Dedicated local AI microservice launcher (Port 8001).

---

## 📁 3-Tier Project Structure & Grouping

```
d:\update\New folder\
├── 🌐 FRONTEND (Vercel Ready)
│   └── frontend/
│       ├── index.html            # Dark-theme financial terminal UI
│       ├── style.css             # Terminal stylesheet
│       ├── app.js                # State management, endpoint switcher & charts
│       ├── vercel.json           # Subfolder Vercel routing & headers
│       └── README.md             # 1-Minute Vercel Deployment Guide
│
├── ☁️ BACKEND (Render Ready)
│   ├── backend/
│   │   ├── app.py                # High-performance FastAPI endpoints & CORS
│   │   └── schemas.py            # Pydantic validation schemas
│   ├── core/                     # Risk management, ATR brackets & backtester
│   ├── data/                     # Market data pipeline & Kotak Neo adapter
│   ├── execution/                # Paper trading engine & execution logger
│   ├── config.py                 # Central settings & dynamic runtime config
│   ├── requirements.txt          # Production dependencies
│   ├── render.yaml               # Render Blueprint web service specification
│   ├── Procfile                  # PaaS start command for Render
│   └── RENDER_DEPLOY_GUIDE.md    # Step-by-step Render setup guide
│
├── 💻 LAPTOP AI TUNNEL (Local PC Ready)
│   ├── ai/                       # HistGradientBoosting ML model & feature extractor
│   │   ├── server.py             # Dedicated Port 8001 AI microservice
│   │   ├── tunnel_manager.py     # Automatic ngrok tunnel & Render handshake
│   │   ├── model.py              # ML classifier & calibrated probabilities
│   │   ├── feature_extractor.py  # Non-lagging technical & momentum features
│   │   ├── explainer.py          # Plain-English decision reason generator
│   │   └── auto_learner.py       # Autonomous daily retraining pipeline
│   ├── eternal_ai_model.joblib   # Local machine learning model weights
│   ├── model_learning_history.json # Day-by-day learning milestone log
│   ├── start.bat                 # 1-Click Master Launcher (Menu / Flags)
│   ├── start_ai_tunnel.bat       # 1-Click AI Server + Cloud Tunnel (ngrok)
│   ├── start_ai_model.bat        # 1-Click Local-Only AI Server (Port 8001)
│   └── LAPTOP_AI_TUNNEL_GUIDE.md # Laptop runner & cloud tunnel guide
│
└── 🧪 AUTOMATED TESTS
    └── tests/
        ├── test_phase1_safety.py           # 22 Safety, truthfulness & security tests
        └── test_security_and_deployment.py # 19 Integration, CORS & deployment tests
```

---

## 🚀 How to Host: Step-by-Step Instructions

### Step 1: Deploy Frontend to Vercel (1 Minute)
See [`frontend/README.md`](frontend/README.md) for full details:
1. Push your repository to GitHub.
2. In [Vercel.com](https://vercel.com/new), import your repository.
3. Under **Project Settings**, set **Root Directory** to `frontend`.
4. Click **Deploy**. Your UI is live on a global CDN!

### Step 2: Deploy Backend to Render (3 Minutes)
See [`RENDER_DEPLOY_GUIDE.md`](RENDER_DEPLOY_GUIDE.md) for full details:
1. In [Render.com](https://dashboard.render.com), create a **New Web Service** from your GitHub repo.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
4. Set Environment Variables:
   - `AGENT_MODE`: `PAPER`
   - `REAL_ORDERS_ENABLED`: `false`
   - `SYMBOL`: `ETERNAL.NS`
   - `TIMEFRAME`: `5m`
   - `ENFORCE_MARKET_HOURS`: `true`
   - `ADMIN_API_KEY`: `<your-admin-key>`
   - `AI_SECRET_TOKEN`: `<your-ai-token>`
   - `CORS_ORIGINS`: `*` (or your Vercel URL)
5. Click **Deploy Web Service** and copy your Render URL.

### Step 3: Run AI Model on Your Laptop (1 Click)
See [`LAPTOP_AI_TUNNEL_GUIDE.md`](LAPTOP_AI_TUNNEL_GUIDE.md) for full details:
1. In your local `.env`, set:
   ```ini
   RENDER_BACKEND_URL=https://your-backend.onrender.com
   AI_SECRET_TOKEN=your_ai_token
   NGROK_AUTHTOKEN=your_ngrok_token
   ```
2. Double-click **`start.bat`** (or press Enter for Option 1).
3. The AI microservice starts on port 8001, opens an encrypted HTTPS tunnel, registers itself with your Render backend, and keeps Render awake with heartbeats.

---

## 🧪 Run Automated Verification Tests

To run the complete test suite (41 tests):
```bash
python -m pytest tests/
```
Or double-click `start.bat` and select **Option 4**!
