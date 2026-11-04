# ETERNAL AI Trading Agent — Production Cloud Deployment & PC Mobility Guide

This guide provides step-by-step instructions for deploying the **Frontend to Vercel**, the **Backend to Render**, and running the **AI Engine on your local PC (or any other desktop)** with **zero cloud fees** and **automatic tunnel discovery**.

---

## 1. Cloud Deployment Steps

### A. Deploy Backend to Render (One-Time)
1. Push your repository to GitHub or GitLab (`.env` and secrets are strictly ignored by `.gitignore`).
2. Go to [Render.com](https://render.com) and create a **New Web Service**.
3. Select your repository:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
4. Add your Environment Variables in Render:
   - `SERVER_HOST` = `0.0.0.0`
   - `CORS_ORIGINS` = `*`
   - `REAL_ORDERS_ENABLED` = `True` (or `False` for paper test)
   - `AGENT_MODE` = `LIVE` (or `PAPER`)
   - `KOTAK_CONSUMER_KEY` = your Kotak consumer key
   - `KOTAK_CONSUMER_SECRET` = your Kotak consumer secret
   - `KOTAK_MOBILE_NUMBER` = +91XXXXXXXXXX
   - `KOTAK_CLIENT_CODE` = your UCC client code
   - `KOTAK_MPIN` = your 6-digit MPIN
   - `AI_SECRET_TOKEN` = (optional secure password for your AI tunnel)
5. Render will deploy your backend at: `https://your-backend.onrender.com`

---

### B. Deploy Frontend to Vercel (One-Time)
1. Go to [Vercel.com](https://vercel.com) and click **Add New Project**.
2. Select your repository:
   - **Root Directory:** select `./frontend` or `./`
   - **Framework Preset:** `Other` (HTML/CSS/JS)
3. Click **Deploy**. Vercel will deploy your frontend at: `https://your-frontend.vercel.app`
4. In your browser, open `https://your-frontend.vercel.app`:
   - Navigate to **Tab 5: Settings & Config**.
   - Under **1. Render Backend REST API Endpoint**, enter `https://your-backend.onrender.com`.
   - Click **Save Backend** and **Test Backend** (will turn green).

---

## 2. PC-to-PC Mobility (Shift to Any Desktop)

### How Plug-and-Play Mobility Works:
When you copy this project folder to **any other PC or desktop**:
1. Open `.env` and set your Render backend URL once:
   ```env
   RENDER_BACKEND_URL=https://your-backend.onrender.com
   ```
2. Double-click **`start_ai_tunnel.bat`**.
3. The launcher will automatically:
   - Check Python and auto-install any missing dependencies from `requirements.txt`.
   - Start the local AI model microservice on port 8001.
   - Open a secure public HTTPS tunnel.
   - Automatically register the new tunnel URL with your Render backend via webhook!
   - Send periodic heartbeats every 45s to keep Render awake and keep the AI connection fresh.
4. **Result:** Your cloud-hosted Render backend and Vercel frontend are immediately connected to the new desktop's AI model with **zero manual configuration**!

---

## 3. How the AI Guider Works with Your Kotak Neo Key

1. **Zero Automated Orders**: Autonomous order execution has been completely removed from the code. The system will **never** trade or spend your money automatically.
2. **Kotak Keys for Live Feed**: Your Kotak Neo keys provide the official real-time exchange quote stream and account positions in read-only mode.
3. **Exact Trade Suggestions**: On the Web Dashboard (and via CLI), the AI Guider continuously calculates the market structure and tells you:
   - **Recommended Action**: Bold `BUY`, `SELL`, or `WAIT / HOLD`
   - **Suggested Entry Price**: Exact current price
   - **Target Price**: Calculated Take Profit level
   - **Stop-Loss Price**: Calculated Stop Loss level
   - **Step-by-Step Guidance**: "Open your Kotak Neo app -> Place BUY order for 1 qty -> Set Target and SL."
4. **You Execute Manually**: You use your own mind and judgment to review the AI suggestion, and place the order yourself inside your official Kotak Neo app.

---

## 4. Run Verification Suite

To verify the entire system before trading:
```cmd
start.bat test
```
or
```powershell
python tests\test_security_and_deployment.py
```
All 18 automated tests must pass.

