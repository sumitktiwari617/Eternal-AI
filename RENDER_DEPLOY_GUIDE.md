# 🚀 ETERNAL AI Trading Agent — Render Backend Deployment Guide

This guide explains how to deploy the **FastAPI Backend** to [Render](https://render.com) for 24/7 cloud availability.

---

## 📋 Prerequisites
1. A GitHub account.
2. This repository pushed to your GitHub account.
3. A free account on [https://render.com](https://render.com).

---

## 🛠️ Step-by-Step Deployment Instructions

### Method A: Automated Blueprint (Fastest)
Render will read `render.yaml` automatically from your repo:
1. Log in to [https://dashboard.render.com](https://dashboard.render.com).
2. Click **New +** (top right) and select **Blueprint**.
3. Connect your GitHub repository.
4. Render will detect `render.yaml` and configure the web service automatically.
5. Click **Apply**.

---

### Method B: Manual Web Service Setup
1. Log in to [https://dashboard.render.com](https://dashboard.render.com).
2. Click **New +** -> **Web Service**.
3. Choose **Build and deploy from a Git repository**, then select your repository.
4. Fill in the service details:
   - **Name**: `eternal-trading-backend`
   - **Region**: `Singapore (Southeast Asia)` or `Oregon (US West)`
   - **Branch**: `main` or `master`
   - **Root Directory**: leave blank (defaults to root `.`)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: `Free`
5. Click **Advanced** and add these **Environment Variables**:

| Variable Name | Value | Purpose |
| :--- | :--- | :--- |
| `AGENT_MODE` | `PAPER` | Fail-safe paper simulation |
| `REAL_ORDERS_ENABLED` | `false` | Hard-locks real order execution |
| `SYMBOL` | `ETERNAL.NS` | Target equity ticker |
| `TIMEFRAME` | `5m` | Primary intraday timeframe |
| `ENFORCE_MARKET_HOURS` | `true` | Restricts signals to 09:15–15:30 IST |
| `ADMIN_API_KEY` | `your_secure_admin_key` | Protects controls and config updates |
| `AI_SECRET_TOKEN` | `your_secure_ai_token` | Authenticates laptop AI tunnel handshake |
| `CORS_ORIGINS` | `*` | Allows connections from your Vercel frontend |

6. Click **Deploy Web Service**.

---

## 🔗 After Render Deployment
1. Copy your public Render URL from the dashboard:
   ```text
   https://eternal-trading-backend.onrender.com
   ```
2. Paste this URL into your **Vercel Frontend Settings** (under Render Backend URL).
3. On your laptop, run **`start.bat`** (Option 1) to connect your laptop's AI model tunnel to this Render backend.

