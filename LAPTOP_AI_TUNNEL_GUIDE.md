# 🧠 ETERNAL AI Model — Laptop Runner & Cloud Tunnel Guide

This guide explains how to run the AI Model locally on your laptop/PC and bridge it to your deployed Render backend and Vercel frontend.

---

## 🌟 Why Run the AI Model on Your Laptop?
1. **Zero Cloud Machine Learning Costs**: Train and infer HistGradientBoosting models with zero expensive cloud GPU/vCPU fees.
2. **Data & Model Privacy**: Model weights (`eternal_ai_model.joblib`) and training features stay securely on your personal computer.
3. **Plug-and-Play Mobility**: With `start.bat`, your laptop establishes an encrypted public HTTPS tunnel (via ngrok) and handshakes automatically with Render.

---

## 🚀 Quick Start (1 Click)

1. Double-click **`start.bat`**.
2. Press **Enter** (Option `[1] Start Laptop AI Model + Cloud Tunnel`).
3. That's it!
   - The AI microservice boots on `http://127.0.0.1:8001`.
   - ngrok creates a public HTTPS bridge (e.g. `https://xxxx.ngrok-free.app`).
   - The tunnel manager registers with your Render backend.
   - Continuous heartbeats prevent Render's free tier from sleeping.

---

## ⚙️ Configuring Your Laptop Environment (`.env`)

In your local `.env` file (copied from `.env.example`), set:

```ini
# Render Backend URL (Where your cloud backend is hosted)
RENDER_BACKEND_URL=https://eternal-trading-backend.onrender.com

# Shared secret token for tunnel authentication (Must match Render environment variable)
AI_SECRET_TOKEN=your_secure_ai_token

# Free ngrok auth token (from https://dashboard.ngrok.com/get-started/your-authtoken)
NGROK_AUTHTOKEN=your_ngrok_token_here
```

---

## 🛠️ Verification & Health Check

- **Local AI Health**: Open [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health) in your browser -> Returns `{"status": "healthy"}`.
- **Local Prediction**: Open [http://127.0.0.1:8001/api/ai/predict](http://127.0.0.1:8001/api/ai/predict) -> Returns current signal, calibrated confidence, ATR brackets, and market state.
- **Accuracy History**: Open [http://127.0.0.1:8001/api/ai/accuracy-trend](http://127.0.0.1:8001/api/ai/accuracy-trend) -> Returns measured learning history.
