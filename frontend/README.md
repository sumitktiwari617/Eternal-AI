# ⚡ ETERNAL AI Trading Agent — Frontend (Vercel Ready)

This directory contains the complete, self-contained web dashboard for the **ETERNAL AI Trading Agent**.

- **Zero-Build**: Pure vanilla HTML5, CSS3, and modern JavaScript. No node modules, no webpack, no compile step.
- **Ultra-Fast CDN**: Deploys instantly to Vercel's global edge network.
- **Cross-Origin Ready**: Seamlessly connects to your backend hosted on Render and your local AI microservice.

---

## 🚀 How to Host on Vercel (3 Easy Methods)

### Method 1: GitHub Integration (Recommended)
1. Push your repository to your GitHub account.
2. Go to [https://vercel.com/new](https://vercel.com/new).
3. Import your GitHub repository.
4. In **Project Settings**:
   - **Framework Preset**: Select `Other` (or leave default).
   - **Root Directory**: Click *Edit* and select **`frontend`**.
5. Click **Deploy**. Your frontend is live in 5 seconds!

### Method 2: Drag & Drop (Instant, No Git Required)
1. Log in to [https://vercel.com](https://vercel.com).
2. Go to your dashboard and navigate to [https://vercel.com/new](https://vercel.com/new).
3. Drag and drop this **`frontend`** folder directly into the browser window.
4. Vercel will immediately deploy and provide your live HTTPS URL (e.g. `https://eternal-ai-frontend.vercel.app`).

### Method 3: Vercel CLI
From your terminal:
```bash
cd frontend
npx vercel --prod
```

---

## 🔗 Connecting to Your Render Backend

1. Open your live Vercel frontend URL in any browser.
2. Click on the **Settings** tab (gear icon).
3. Under **1. Render Backend REST API Endpoint**, paste your Render URL:
   ```text
   https://your-backend-name.onrender.com
   ```
4. Click **Save Backend**.
5. The status badge in the top header will immediately turn green: **RENDER BACKEND: ONLINE**.
