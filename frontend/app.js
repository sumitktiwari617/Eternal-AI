// ETERNAL AI Trading Agent — Frontend Controller
// Multi-Tier Deployment: Vercel Frontend + Render Backend + Localhost/Tunnel AI Model
const DEFAULT_BACKEND_URL = "https://eternal-ai-3oat.onrender.com";
const DEFAULT_ADMIN_KEY = "admin_aa3797c179a6236618316e26";
const DEFAULT_AI_TOKEN = "ai_2abc92e5c7993432bb3b002a";

let RENDER_BACKEND_URL = localStorage.getItem("eternal_backend_url") || DEFAULT_BACKEND_URL;
let LOCAL_AI_BASE = localStorage.getItem("eternal_local_ai_url") || "http://127.0.0.1:8001";
let AI_SECRET_TOKEN = localStorage.getItem("eternal_ai_token") || DEFAULT_AI_TOKEN;

function getAuthHeaders(customHeaders = {}) {
  const headers = { ...customHeaders };
  const adminKey = sessionStorage.getItem("eternal_admin_key") || DEFAULT_ADMIN_KEY;
  if (adminKey && adminKey.trim()) {
    headers["X-Admin-Key"] = adminKey.trim();
  }
  const brokerKey = sessionStorage.getItem("eternal_broker_key");
  if (brokerKey && brokerKey.trim()) {
    headers["X-Broker-Key"] = brokerKey.trim();
  }
  const aiToken = localStorage.getItem("eternal_ai_token") || AI_SECRET_TOKEN || DEFAULT_AI_TOKEN;
  if (aiToken && aiToken.trim()) {
    headers["X-AI-Secret-Token"] = aiToken.trim();
  }
  return headers;
}

function getApiBase() {
  if (RENDER_BACKEND_URL && RENDER_BACKEND_URL.trim().length > 0) {
    return RENDER_BACKEND_URL.trim().replace(/\/+$/, "");
  }
  return window.location.origin;
}

let pollTimer = null;
let currentConfig = null;
let cachedCandles = [];

// --- Initialize App ---
document.addEventListener("DOMContentLoaded", () => {
  startLiveClock();
  initTabs();
  bindControls();
  bindBacktestForm();
  bindSettingsForm();
  initLocalAIModelConnection();
  bindOrderControls();

  // Initial data fetch
  fetchStatus();
  fetchAIPrediction();
  fetchAIAccuracyTrend();
  fetchConfig();
  fetchMarketData();
  fetchLogs();

  // Start continuous polling (every 4 seconds)
  let pollCycle = 0;
  pollTimer = setInterval(() => {
    pollCycle++;
    fetchStatus();
    fetchAIPrediction();
    if (pollCycle % 3 === 0) {
      checkLocalAIHealth(false);
    }
    if (pollCycle % 8 === 0) {
      fetchAIAccuracyTrend();
    }
    const chartTab = document.getElementById("tab-chart");
    if (chartTab && chartTab.classList.contains("active")) {
      fetchMarketData();
    }
  }, 4000);
});

// --- Live IST Clock (Updates Every Second) ---
function startLiveClock() {
  function updateClock() {
    const el = document.getElementById("header-time");
    if (!el) return;
    try {
      const now = new Date();
      const options = {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false
      };
      el.textContent = new Intl.DateTimeFormat("en-GB", options).format(now);
      el.classList.remove("text-muted");
    } catch (e) {
      el.textContent = new Date().toTimeString().split(" ")[0];
    }
  }
  updateClock();
  setInterval(updateClock, 1000);
}

// --- Tab Navigation ---
function initTabs() {
  const tabs = document.querySelectorAll(".nav-btn");
  tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add("active");

      // Auto-refresh data on tab switch
      if (btn.dataset.tab === "tab-chart") {
        if (cachedCandles.length > 0) {
          requestAnimationFrame(() => {
            renderCandlesTable(cachedCandles);
            drawCanvasChart(cachedCandles);
          });
          setTimeout(() => {
            if (cachedCandles.length > 0) drawCanvasChart(cachedCandles);
          }, 80);
        }
        fetchMarketData();
      }
      if (btn.dataset.tab === "tab-logs") fetchLogs();
      if (btn.dataset.tab === "tab-settings") fetchConfig();
    });
  });

  window.addEventListener("resize", () => {
    const chartTab = document.getElementById("tab-chart");
    if (chartTab && chartTab.classList.contains("active") && cachedCandles.length > 0) {
      drawCanvasChart(cachedCandles);
    }
  });
}

// --- Fetch Telemetry & Status ---
async function fetchStatus() {
  try {
    const res = await fetch(`${getApiBase()}/api/status`);
    if (!res.ok) return;
    const data = await res.json();
    renderStatus(data);
  } catch (err) {
    console.warn("Status fetch error:", err);
  }
}

function renderStatus(data) {
  // 1. Header Telemetry
  document.getElementById("header-symbol").textContent = data.symbol || "ETERNAL.NS";
  document.getElementById("header-timeframe").textContent = data.timeframe || "5m";
  document.getElementById("header-time").textContent = data.server_time_ist || "--:--:--";

  const statePill = document.getElementById("header-state");
  statePill.textContent = data.agent_state;
  statePill.className = "status-pill";
  if (data.agent_state === "RUNNING") statePill.classList.add("status-running");
  else if (data.agent_state === "PAUSED") statePill.classList.add("status-paused");
  else if (data.agent_state === "EMERGENCY_STOPPED") statePill.classList.add("status-emergency");
  else statePill.classList.add("status-idle");

  const modePill = document.getElementById("header-mode");
  if (data.agent_mode === "COPILOT" || data.agent_mode === "ADVISORY") {
    modePill.textContent = "AI COPILOT (YOU TRADE)";
    modePill.className = "mode-pill mode-paper";
  } else if (data.agent_mode === "LIVE") {
    modePill.textContent = "LIVE AUTONOMOUS";
    modePill.className = "mode-pill mode-live";
  } else {
    modePill.textContent = "PAPER SIMULATION";
    modePill.className = "mode-pill mode-paper";
  }

  const modeSelect = document.getElementById("select-mode");
  if (modeSelect && modeSelect.value !== data.agent_mode) {
    modeSelect.value = data.agent_mode;
  }

  // 2. Copilot Action Directive Banner (What You Should Do Now)
  if (data.last_decision) {
    const d = data.last_decision;
    const directiveEl = document.getElementById("copilot-action-directive");
    const guidanceEl = document.getElementById("copilot-human-guidance");
    const pillAction = document.getElementById("copilot-pill-action");
    const entryEl = document.getElementById("copilot-entry-price");
    const targetEl = document.getElementById("copilot-target-price");
    const slEl = document.getElementById("copilot-sl-price");
    const bannerCard = document.getElementById("copilot-banner-card");
    const modeTag = document.getElementById("copilot-mode-tag");
    const timeEl = document.getElementById("copilot-timestamp");

    if (modeTag) {
      modeTag.textContent = `MODE: ${data.agent_mode || "COPILOT"} (YOU TRADE)`;
    }

    if (timeEl && data.last_analysis_time) {
      timeEl.textContent = data.last_analysis_time.slice(11, 19) + " IST";
    }

    if (directiveEl && d.directive) {
      directiveEl.textContent = d.directive;
    }
    if (guidanceEl && d.human_guidance) {
      guidanceEl.textContent = d.human_guidance;
    }

    const b = d.brackets || {};
    if (entryEl) entryEl.textContent = b.entry_price ? `₹${b.entry_price.toFixed(2)}` : "--";
    if (targetEl) targetEl.textContent = b.target ? `₹${b.target.toFixed(2)}` : "--";
    if (slEl) slEl.textContent = b.stop_loss ? `₹${b.stop_loss.toFixed(2)}` : "--";

    const riskEl = document.getElementById("copilot-total-risk");
    const profitEl = document.getElementById("copilot-total-profit");
    if (riskEl) riskEl.textContent = b.estimated_max_risk_rupees ? `-₹${b.estimated_max_risk_rupees.toLocaleString('en-IN')}` : "--";
    if (profitEl) profitEl.textContent = b.estimated_target_profit_rupees ? `+₹${b.estimated_target_profit_rupees.toLocaleString('en-IN')}` : "--";

    if (pillAction) {
      pillAction.textContent = d.signal || "WAIT";
      if (d.signal === "BUY") {
        pillAction.className = "val font-bold text-emerald";
        if (bannerCard) bannerCard.style.borderColor = "#10b981";
      } else if (d.signal === "SELL") {
        pillAction.className = "val font-bold text-rose";
        if (bannerCard) bannerCard.style.borderColor = "#ef4444";
      } else {
        pillAction.className = "val font-bold text-amber";
        if (bannerCard) bannerCard.style.borderColor = "#0284c7";
      }
    }
  }

  // 2. Quote Card
  if (data.last_quote) {
    const q = data.last_quote;
    document.getElementById("quote-ltp").textContent = `₹${q.ltp?.toFixed(2) || "0.00"}`;
    const changeEl = document.getElementById("quote-change");
    const change = q.change || 0.0;
    const changePct = q.change_pct || 0.0;
    const sign = change >= 0 ? "+" : "";
    changeEl.textContent = `${sign}${change.toFixed(2)} (${sign}${changePct.toFixed(2)}%)`;
    changeEl.className = `price-change font-mono ${change >= 0 ? "text-emerald" : "text-rose"}`;

    document.getElementById("quote-open").textContent = `₹${q.open?.toFixed(2) || "--"}`;
    document.getElementById("quote-high").textContent = `₹${q.high?.toFixed(2) || "--"}`;
    document.getElementById("quote-low").textContent = `₹${q.low?.toFixed(2) || "--"}`;
    document.getElementById("quote-vol").textContent = `${Math.round((q.volume || 0) / 1000)}K`;
  }

  // 3. AI Signal Decision Card
  if (data.last_decision) {
    const d = data.last_decision;
    const badge = document.getElementById("signal-badge");
    badge.textContent = d.signal || "WAIT";
    badge.className = "signal-badge";

    if (d.signal === "BUY") badge.classList.add("badge-buy");
    else if (d.signal === "SELL") badge.classList.add("badge-sell");
    else badge.classList.add("badge-wait");

    document.getElementById("signal-reason").textContent = d.reason || "Analyzing candles...";
    document.getElementById("signal-meta").textContent = 
      `Safety: ${d.safety?.status || "READY"} | Real Orders: ${d.real_orders_enabled ? "ENABLED" : "DISABLED"} | Evaluated: ${data.last_analysis_time?.slice(11, 19) || ""}`;

    // 4. Indicators
    if (d.indicators) {
      const ind = d.indicators;
      document.getElementById("ind-ema-fast").textContent = `₹${ind.ema_fast?.toFixed(2) || "--"}`;
      document.getElementById("ind-ema-slow").textContent = `₹${ind.ema_slow?.toFixed(2) || "--"}`;
      document.getElementById("ind-vwap").textContent = `₹${ind.vwap?.toFixed(2) || "--"}`;
      document.getElementById("ind-rsi").textContent = ind.rsi?.toFixed(2) || "--";

      const rsiBar = document.getElementById("ind-rsi-bar");
      if (rsiBar) rsiBar.style.width = `${Math.min(100, Math.max(0, ind.rsi || 50))}%`;

      const fastEmaEl = document.getElementById("ind-ema-status");
      const curPrice = ind.price || (data.last_quote?.ltp);
      if (fastEmaEl && curPrice && ind.ema_fast) {
        if (curPrice >= ind.ema_fast) {
          fastEmaEl.textContent = `Above EMA20 (+₹${(curPrice - ind.ema_fast).toFixed(2)})`;
          fastEmaEl.className = "indicator-status text-emerald";
        } else {
          fastEmaEl.textContent = `Below EMA20 (-₹${(ind.ema_fast - curPrice).toFixed(2)})`;
          fastEmaEl.className = "indicator-status text-rose";
        }
      }

      const trendEl = document.getElementById("ind-trend-status");
      if (trendEl && ind.ema_fast && ind.ema_slow) {
        if (ind.ema_fast >= ind.ema_slow) {
          trendEl.textContent = "Golden Cross (Bullish EMA20 > EMA50)";
          trendEl.className = "indicator-status text-emerald";
        } else {
          trendEl.textContent = "Death Cross (Bearish EMA20 < EMA50)";
          trendEl.className = "indicator-status text-rose";
        }
      }

      const vwapEl = document.getElementById("ind-vwap-status");
      if (vwapEl && curPrice && ind.vwap) {
        if (curPrice >= ind.vwap) {
          vwapEl.textContent = `Bullish (+₹${(curPrice - ind.vwap).toFixed(2)} Above VWAP)`;
          vwapEl.className = "indicator-status text-emerald";
        } else {
          vwapEl.textContent = `Bearish (-₹${(ind.vwap - curPrice).toFixed(2)} Below VWAP)`;
          vwapEl.className = "indicator-status text-rose";
        }
      }

      const rsiStatusEl = document.getElementById("ind-rsi-status");
      if (rsiStatusEl && ind.rsi) {
        if (ind.rsi >= 70) {
          rsiStatusEl.textContent = `Overbought (${ind.rsi.toFixed(1)}) — Caution Longs`;
          rsiStatusEl.className = "indicator-status text-rose";
        } else if (ind.rsi <= 30) {
          rsiStatusEl.textContent = `Oversold (${ind.rsi.toFixed(1)}) — Watch Reversals`;
          rsiStatusEl.className = "indicator-status text-emerald";
        } else if (ind.rsi >= 50) {
          rsiStatusEl.textContent = `Bullish Momentum (${ind.rsi.toFixed(1)})`;
          rsiStatusEl.className = "indicator-status text-emerald";
        } else {
          rsiStatusEl.textContent = `Bearish Momentum (${ind.rsi.toFixed(1)})`;
          rsiStatusEl.className = "indicator-status text-amber";
        }
      }
    }

    // 5. Brackets
    if (d.brackets) {
      const b = d.brackets;
      document.getElementById("bracket-atr-info").textContent = `ATR 14: ₹${b.atr?.toFixed(2) || "--"}`;
      document.getElementById("bracket-entry").textContent = `₹${b.entry_price?.toFixed(2) || "--"}`;
      document.getElementById("bracket-stop").textContent = `₹${b.stop_loss?.toFixed(2) || "--"}`;
      document.getElementById("bracket-target").textContent = `₹${b.target?.toFixed(2) || "--"}`;
      document.getElementById("bracket-rr").textContent = b.risk_reward_ratio || "1:1.33";
    }
  }

  // 6. Kotak Neo Status List
  if (data.kotak_status) {
    const ks = data.kotak_status;
    const listEl = document.getElementById("kotak-status-list");
    if (listEl) {
      listEl.innerHTML = `
        <li>SDK Installed: <span class="${ks.sdk_installed ? 'text-emerald' : 'text-rose'}">${ks.sdk_installed ? 'Yes' : 'No'}</span></li>
        <li>Credentials: <span class="${ks.has_credentials ? 'text-emerald' : 'text-amber'}">${ks.has_credentials ? 'Configured' : 'Missing in .env'}</span></li>
        <li>Authentication: <span class="${ks.is_authenticated ? 'text-emerald' : 'text-muted'}">${ks.is_authenticated ? 'Active Session' : 'Offline / Paper'}</span></li>
      `;
    }
  }
}

// --- Synchronized Status Badges Helper ---
function setTunnelStatusBadges(isOnline, detailText = "") {
  const sourceBadge = document.getElementById("ai-source-badge");
  const settingsBadge = document.getElementById("local-ai-status-badge");
  const teleStatus = document.getElementById("tele-ai-status");

  if (isOnline) {
    if (sourceBadge) {
      sourceBadge.textContent = "● Laptop AI Tunnel Online";
      sourceBadge.style.color = "#10b981";
      sourceBadge.style.borderColor = "#10b981";
      sourceBadge.style.background = "rgba(16, 185, 129, 0.1)";
    }
    if (settingsBadge) {
      settingsBadge.textContent = "● Laptop AI Tunnel Online";
      settingsBadge.className = "badge font-mono text-emerald";
      settingsBadge.style.borderColor = "#10b981";
      settingsBadge.style.background = "rgba(16, 185, 129, 0.1)";
    }
    if (teleStatus) {
      teleStatus.textContent = detailText ? `Online (${detailText})` : "Online (Active Tunnel)";
      teleStatus.className = "text-emerald";
    }
  } else {
    if (sourceBadge) {
      sourceBadge.textContent = "○ Laptop Tunnel Offline";
      sourceBadge.style.color = "#f59e0b";
      sourceBadge.style.borderColor = "#f59e0b";
      sourceBadge.style.background = "rgba(245, 158, 11, 0.1)";
    }
    if (settingsBadge) {
      settingsBadge.textContent = "○ Laptop AI Tunnel Offline";
      settingsBadge.className = "badge font-mono text-amber";
      settingsBadge.style.borderColor = "#f59e0b";
      settingsBadge.style.background = "rgba(245, 158, 11, 0.1)";
    }
    if (teleStatus) {
      teleStatus.textContent = detailText ? `Offline (${detailText})` : "Offline (Run start.bat on laptop)";
      teleStatus.className = "text-amber";
    }
  }
}

// --- Fetch Autonomous AI Prediction with Confidence & Reason ---
async function fetchAIPrediction() {
  let pred = null;
  let source = "cloud_backend";

  // 1. First attempt to query the user's Localhost AI Model / Tunnel
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2200);
    const headers = {
      "Accept": "application/json",
      "ngrok-skip-browser-warning": "1"
    };
    const token = localStorage.getItem("eternal_ai_token") || AI_SECRET_TOKEN || DEFAULT_AI_TOKEN;
    if (token) {
      headers["X-AI-Secret-Token"] = token;
    }

    const localRes = await fetch(`${LOCAL_AI_BASE}/api/ai/predict`, {
      signal: controller.signal,
      mode: "cors",
      headers: headers
    });
    clearTimeout(timeoutId);
    if (localRes.ok) {
      pred = await localRes.json();
      source = "localhost";
    }
  } catch (err) {
    // Localhost / tunnel server unreachable, fall back to backend
  }

  // 2. Fall back to backend API endpoint
  if (!pred) {
    try {
      const res = await fetch(`${getApiBase()}/api/ai/predict`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        pred = await res.json();
        source = (pred.routed_via === "localhost_ai_service" || pred.source === "localhost_ai_model") ? "localhost" : "cloud_backend";
      }
    } catch (err) {
      console.warn("AI prediction fetch failed:", err);
      return;
    }
  }

  if (pred) {
    renderAIPrediction(pred, source);
  }
}

function renderAIPrediction(pred, source = "localhost") {
  // 1. Accuracy Badge & Source Badge
  const accBadge = document.getElementById("ai-accuracy-badge");
  if (accBadge && pred.model_accuracy != null) {
    accBadge.textContent = `Signal Win Rate: ${pred.model_accuracy}%`;
    accBadge.title = "Balanced directional out-of-sample accuracy across active market signals (Target 1:3 RRR)";
  }

  const confBadge = document.getElementById("ai-conviction-badge");
  if (confBadge && pred.high_conf_accuracy != null) {
    confBadge.textContent = `High-Conf: ${pred.high_conf_accuracy}%`;
    confBadge.title = "Precision on trades where model confidence is >= 50%";
  }

  const oosEl = document.getElementById("stat-oos-acc");
  if (oosEl && pred.model_accuracy != null) oosEl.textContent = `${pred.model_accuracy}%`;
  const highConfEl = document.getElementById("stat-high-conf");
  if (highConfEl && pred.high_conf_accuracy != null) highConfEl.textContent = `${pred.high_conf_accuracy}%`;
  const regimeEl = document.getElementById("stat-regime-acc");
  if (regimeEl && pred.regime_accuracy != null) regimeEl.textContent = `${pred.regime_accuracy}%`;

  // Synchronize all status badges across cards and settings
  setTunnelStatusBadges(
    source === "localhost",
    source === "localhost" ? "Via Cloud Tunnel" : "Tunnel Inactive / Cloud Fallback"
  );

  // 2. Signal Badge
  const badge = document.getElementById("signal-badge");
  if (badge) {
    badge.textContent = pred.signal || "HOLD";
    badge.className = "signal-badge";
    if (pred.signal === "BUY") badge.classList.add("badge-buy");
    else if (pred.signal === "SELL") badge.classList.add("badge-sell");
    else badge.classList.add("badge-wait");
  }

  // 3. Confidence Bar & Value
  const confVal = document.getElementById("ai-confidence-val");
  const confNum = pred.confidence != null ? pred.confidence : 0;
  if (confVal) confVal.textContent = pred.confidence != null ? `${pred.confidence}%` : "N/A";
  const confBar = document.getElementById("ai-confidence-bar");
  if (confBar) confBar.style.width = `${Math.min(100, Math.max(0, confNum))}%`;

  // 4. Probability Pills
  const probs = pred.probabilities || {};
  const pBuy = document.getElementById("prob-buy");
  const pHold = document.getElementById("prob-hold");
  const pSell = document.getElementById("prob-sell");
  if (pBuy) pBuy.textContent = `BUY: ${probs.BUY != null ? probs.BUY + '%' : 'N/A'}`;
  if (pHold) pHold.textContent = `HOLD: ${probs.HOLD != null ? probs.HOLD + '%' : 'N/A'}`;
  if (pSell) pSell.textContent = `SELL: ${probs.SELL != null ? probs.SELL + '%' : 'N/A'}`;

  // 5. Decision Reason
  const reasonEl = document.getElementById("signal-reason");
  if (reasonEl) reasonEl.textContent = pred.reason || "Analyzing multi-factor feature set...";

  // 6. Meta
  const metaEl = document.getElementById("signal-meta");
  if (metaEl) {
    metaEl.textContent = `Asset: ${pred.symbol || 'ETERNAL.NS'} | Retrained: ${pred.last_train_time || 'Active'} | Conviction: ${pred.note || ''}`;
  }

  // 7. Brackets
  const brkAtr = document.getElementById("bracket-atr-info");
  const brkEntry = document.getElementById("bracket-entry");
  const brkStop = document.getElementById("bracket-stop");
  const brkTarget = document.getElementById("bracket-target");
  const brkRr = document.getElementById("bracket-rr");

  if (pred.brackets) {
    const b = pred.brackets;
    if (brkAtr) brkAtr.textContent = `ATR 14: ₹${b.atr?.toFixed(2) || "--"}`;
    if (brkEntry) brkEntry.textContent = `₹${b.entry_price?.toFixed(2) || "--"}`;
    if (brkStop) brkStop.textContent = `₹${b.stop_loss?.toFixed(2) || "--"}`;
    if (brkTarget) brkTarget.textContent = `₹${b.target?.toFixed(2) || "--"}`;
    if (brkRr) brkRr.textContent = b.risk_reward_ratio || "1:3.00";
  } else {
    if (brkAtr) brkAtr.textContent = "ATR: N/A";
    if (brkEntry) brkEntry.textContent = "N/A";
    if (brkStop) brkStop.textContent = "N/A";
    if (brkTarget) brkTarget.textContent = "N/A";
    if (brkRr) brkRr.textContent = "N/A";
  }
}

// --- Fetch Day-by-Day Learning History & Render Accuracy Chart ---
async function fetchAIAccuracyTrend() {
  let data = null;

  // 1. Try Localhost AI Model
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2200);
    const headers = {
      "Accept": "application/json",
      "ngrok-skip-browser-warning": "1"
    };
    if (AI_SECRET_TOKEN) {
      headers["X-AI-Secret-Token"] = AI_SECRET_TOKEN;
    }
    const localRes = await fetch(`${LOCAL_AI_BASE}/api/ai/accuracy-trend`, {
      signal: controller.signal,
      mode: "cors",
      headers: headers
    });
    clearTimeout(timeoutId);
    if (localRes.ok) data = await localRes.json();
  } catch (e) {}

  // 2. Fall back to backend
  if (!data) {
    try {
      const res = await fetch(`${getApiBase()}/api/ai/accuracy-trend`);
      if (res.ok) data = await res.json();
    } catch (err) {
      console.warn("Learning history fetch failed:", err);
      return;
    }
  }

  if (data) {
    const hist = data.history || [];
    renderAccuracyTimeline(hist);
    drawAccuracyChart(hist);

    // Sync top-level accuracy cards and badges with real measured data
    const latest = (hist.length > 0) ? hist[hist.length - 1] : null;
    const curAcc = (latest && latest.accuracy != null) ? latest.accuracy : data.current_accuracy;
    const highConf = (latest && latest.high_conf_accuracy != null) ? latest.high_conf_accuracy : null;
    const regime = (latest && latest.regime_accuracy != null) ? latest.regime_accuracy : null;

    if (curAcc != null) {
      const oosEl = document.getElementById("stat-oos-acc");
      if (oosEl) oosEl.textContent = `${curAcc}%`;
      const accBadge = document.getElementById("ai-accuracy-badge");
      if (accBadge) accBadge.textContent = `Signal Win Rate: ${curAcc}%`;
    }
    if (highConf != null) {
      const highConfEl = document.getElementById("stat-high-conf");
      if (highConfEl) highConfEl.textContent = `${highConf}%`;
      const confBadge = document.getElementById("ai-conviction-badge");
      if (confBadge) confBadge.textContent = `High-Conf: ${highConf}%`;
    }
    if (regime != null) {
      const regimeEl = document.getElementById("stat-regime-acc");
      if (regimeEl) regimeEl.textContent = `${regime}%`;
    }
  }
}

function renderAccuracyTimeline(history) {
  const listEl = document.getElementById("learning-timeline-list");
  if (!listEl) return;
  if (!history || history.length === 0) {
    listEl.innerHTML = `<li class="text-muted" style="font-style: italic;">No validated accuracy yet (Awaiting out-of-sample audit at market close).</li>`;
    return;
  }
  const items = history.slice(-4).reverse().map(h => `
    <li>
      <span class="text-white font-bold">${h.date}</span>: Accuracy <span class="text-emerald font-bold">${h.accuracy != null ? h.accuracy + '%' : 'N/A'}</span> (${h.samples} candles) — <span class="text-muted">${h.event}</span>
    </li>
  `).join("");
  listEl.innerHTML = items;
}

function drawAccuracyChart(history) {
  const canvas = document.getElementById("accuracy-chart");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = (rect.width || 350) * dpr;
  canvas.height = 150 * dpr;
  ctx.scale(dpr, dpr);

  const w = rect.width || 350;
  const h = 150;
  ctx.clearRect(0, 0, w, h);

  if (!history || history.length === 0) {
    ctx.fillStyle = "#94a3b8";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("No validated accuracy yet", w / 2, h / 2);
    return;
  }

  const accs = history.map(h => h.accuracy);
  const minAcc = Math.max(0, Math.min(...accs) - 5);
  const maxAcc = Math.min(100, Math.max(...accs) + 5);
  const range = (maxAcc - minAcc) || 1;

  const getY = (val) => h - 25 - ((val - minAcc) / range) * (h - 45);
  const stepX = (w - 40) / Math.max(1, history.length - 1);

  // Draw Grid Lines
  ctx.strokeStyle = "#1F2937";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 3; i++) {
    const y = 15 + (i / 3) * (h - 40);
    ctx.beginPath();
    ctx.moveTo(10, y);
    ctx.lineTo(w - 10, y);
    ctx.stroke();

    const labelVal = maxAcc - (i / 3) * range;
    ctx.fillStyle = "#6B7280";
    ctx.font = "9px monospace";
    ctx.fillText(`${labelVal.toFixed(0)}%`, 12, y - 3);
  }

  // Draw Line
  ctx.strokeStyle = "#10B981";
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  history.forEach((item, i) => {
    const x = 30 + i * stepX;
    const y = getY(item.accuracy);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Draw Points & Labels
  history.forEach((item, i) => {
    const x = 30 + i * stepX;
    const y = getY(item.accuracy);
    ctx.fillStyle = "#10B981";
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, 2 * Math.PI);
    ctx.fill();

    ctx.fillStyle = "#F9FAFB";
    ctx.font = "10px monospace";
    ctx.fillText(`${item.accuracy}%`, x - 12, y - 8);
  });
}

// --- Control Actions ---
function bindControls() {
  document.getElementById("btn-start")?.addEventListener("click", () => postAction("/api/controls/start"));
  document.getElementById("btn-pause")?.addEventListener("click", () => postAction("/api/controls/pause"));
  document.getElementById("btn-analyze")?.addEventListener("click", () => postAction("/api/analyze", "Analysis complete"));
  document.getElementById("btn-stop")?.addEventListener("click", () => {
    if (confirm("EMERGENCY: Halt all trading operations and lock the agent?")) {
      postAction("/api/controls/emergency-stop", "EMERGENCY STOP ACTIVATED!");
    }
  });
  document.getElementById("btn-reset")?.addEventListener("click", () => postAction("/api/controls/reset"));

  document.getElementById("select-mode")?.addEventListener("change", (e) => {
    const newMode = e.target.value;
    postAction("/api/controls/mode", `Mode set to ${newMode}`, { mode: newMode });
  });

  document.getElementById("btn-refresh-chart")?.addEventListener("click", fetchMarketData);
  document.getElementById("btn-refresh-logs")?.addEventListener("click", fetchLogs);
  document.getElementById("btn-clear-logs")?.addEventListener("click", async () => {
    if (confirm("Clear all recorded paper trading logs?")) {
      const res = await fetch(`${getApiBase()}/api/logs`, {
        method: "DELETE",
        headers: getAuthHeaders()
      });
      if (res.ok) {
        showToast("Journal cleared.");
        fetchLogs();
      }
    }
  });

  document.getElementById("btn-kotak-login")?.addEventListener("click", async () => {
    const totp = document.getElementById("kotak-totp-input").value.trim();
    const mpin = document.getElementById("kotak-mpin-input")?.value.trim() || null;
    if (!totp) return alert("Please enter your 6-digit TOTP code.");
    postAction("/api/kotak/login", "Authentication request submitted", { totp, mpin });
  });
}

async function postAction(endpoint, successMsg = null, payload = null) {
  try {
    const options = {
      method: "POST",
      headers: getAuthHeaders({ "Content-Type": "application/json" })
    };
    if (payload) options.body = JSON.stringify(payload);

    const res = await fetch(`${getApiBase()}${endpoint}`, options);
    const data = await res.json();
    if (res.status === 401 && (data.detail || "").includes("X-Broker-Key")) {
      const brokerKey = prompt("Broker API Key required. Please enter X-Broker-Key:");
      if (brokerKey) {
        sessionStorage.setItem("eternal_broker_key", brokerKey.trim());
        return postAction(endpoint, successMsg, payload);
      }
    }
    if (data.error || (res.status >= 400 && data.detail)) {
      showToast(data.error || data.detail, true);
    } else {
      showToast(successMsg || data.message || "Action successful");
      fetchStatus();
    }
  } catch (err) {
    showToast(`Request failed: ${err.message}`, true);
  }
}

// --- Fetch Market Data & Render Chart ---
async function fetchMarketData() {
  try {
    const res = await fetch(`${getApiBase()}/api/market-data?range_period=5d`);
    if (!res.ok) return;
    const data = await res.json();
    cachedCandles = data.candles || [];

    if (cachedCandles.length > 0) {
      updateTelemetryFromCandles(cachedCandles[cachedCandles.length - 1]);
    }

    renderCandlesTable(cachedCandles);
    requestAnimationFrame(() => drawCanvasChart(cachedCandles));
  } catch (err) {
    console.error("Market data fetch failed:", err);
  }
}

function updateTelemetryFromCandles(latest) {
  if (!latest) return;
  const ltpEl = document.getElementById("quote-ltp");
  if (ltpEl && typeof latest.close === "number") {
    ltpEl.textContent = `₹${latest.close.toFixed(2)}`;
  }
  const openEl = document.getElementById("quote-open");
  if (openEl && typeof latest.open === "number") openEl.textContent = `₹${latest.open.toFixed(2)}`;
  const highEl = document.getElementById("quote-high");
  if (highEl && typeof latest.high === "number") highEl.textContent = `₹${latest.high.toFixed(2)}`;
  const lowEl = document.getElementById("quote-low");
  if (lowEl && typeof latest.low === "number") lowEl.textContent = `₹${latest.low.toFixed(2)}`;
  const volEl = document.getElementById("quote-vol");
  if (volEl && typeof latest.volume === "number") volEl.textContent = `${Math.round(latest.volume / 1000)}K`;

  const emaFastEl = document.getElementById("ind-ema-fast");
  if (emaFastEl && (emaFastEl.textContent.includes("--") || emaFastEl.textContent.trim() === "")) {
    if (typeof latest.ema_fast === "number") emaFastEl.textContent = `₹${latest.ema_fast.toFixed(2)}`;
  }
  const emaSlowEl = document.getElementById("ind-ema-slow");
  if (emaSlowEl && (emaSlowEl.textContent.includes("--") || emaSlowEl.textContent.trim() === "")) {
    if (typeof latest.ema_slow === "number") emaSlowEl.textContent = `₹${latest.ema_slow.toFixed(2)}`;
  }
  const vwapEl = document.getElementById("ind-vwap");
  if (vwapEl && (vwapEl.textContent.includes("--") || vwapEl.textContent.trim() === "")) {
    if (typeof latest.vwap === "number") vwapEl.textContent = `₹${latest.vwap.toFixed(2)}`;
  }
  const rsiEl = document.getElementById("ind-rsi");
  if (rsiEl && (rsiEl.textContent.includes("--") || rsiEl.textContent.trim() === "")) {
    if (typeof latest.rsi === "number") {
      rsiEl.textContent = latest.rsi.toFixed(2);
      const rsiBar = document.getElementById("ind-rsi-bar");
      if (rsiBar) rsiBar.style.width = `${Math.min(100, Math.max(0, latest.rsi))}%`;
    }
  }
  const atrBadge = document.getElementById("bracket-atr-info");
  if (atrBadge && (atrBadge.textContent.includes("--") || atrBadge.textContent.includes("N/A"))) {
    if (typeof latest.atr === "number") atrBadge.textContent = `ATR 14: ₹${latest.atr.toFixed(2)}`;
  }
}

function renderCandlesTable(candles) {
  const tbody = document.querySelector("#candles-table tbody");
  if (!tbody || candles.length === 0) return;

  const rows = candles.slice(-25).reverse().map(c => {
    const ts = c.timestamp ? (c.timestamp.includes("T") ? c.timestamp.replace("T", " ").slice(0, 19) : c.timestamp) : "--";
    const open = typeof c.open === "number" ? c.open.toFixed(2) : c.open;
    const high = typeof c.high === "number" ? c.high.toFixed(2) : c.high;
    const low = typeof c.low === "number" ? c.low.toFixed(2) : c.low;
    const close = typeof c.close === "number" ? c.close.toFixed(2) : c.close;
    const isUp = c.close >= c.open;
    const vol = typeof c.volume === "number" ? c.volume.toLocaleString() : (c.volume || 0);
    const emaF = typeof c.ema_fast === "number" ? c.ema_fast.toFixed(2) : "--";
    const emaS = typeof c.ema_slow === "number" ? c.ema_slow.toFixed(2) : "--";
    const vwap = typeof c.vwap === "number" ? c.vwap.toFixed(2) : "--";
    const rsi = typeof c.rsi === "number" ? c.rsi.toFixed(2) : "--";
    const atr = typeof c.atr === "number" ? c.atr.toFixed(2) : "--";

    return `
      <tr>
        <td>${ts}</td>
        <td>₹${open}</td>
        <td>₹${high}</td>
        <td>₹${low}</td>
        <td class="${isUp ? 'text-emerald' : 'text-rose'} font-bold">₹${close}</td>
        <td>${vol}</td>
        <td class="text-cyan">₹${emaF}</td>
        <td class="text-cyan">₹${emaS}</td>
        <td class="text-amber">₹${vwap}</td>
        <td>${rsi}</td>
        <td>₹${atr}</td>
      </tr>
    `;
  }).join("");

  tbody.innerHTML = rows;
}

// Lightweight HTML5 2D Canvas Chart (Runs completely offline & responsive)
function drawCanvasChart(candles) {
  try {
    const canvas = document.getElementById("price-chart");
    if (!canvas) return;

    const dataToUse = (candles && candles.length >= 2) ? candles : cachedCandles;
    if (!dataToUse || dataToUse.length < 2) return;

    const container = document.getElementById("chart-canvas-wrapper") || canvas.parentElement;
    let containerWidth = container ? container.clientWidth : 0;
    if (containerWidth <= 0) {
      const tabPane = document.getElementById("tab-chart");
      const mainEl = document.querySelector(".main-content");
      containerWidth = (tabPane && tabPane.clientWidth > 0) ? tabPane.clientWidth : (mainEl && mainEl.clientWidth > 0 ? mainEl.clientWidth - 40 : window.innerWidth - 60);
    }
    const isMobile = window.innerWidth <= 768;
    const isSmall = window.innerWidth <= 480;
    const width = Math.max(260, containerWidth - 16);
    const height = isSmall ? 280 : (isMobile ? 320 : 380);
    const dpr = window.devicePixelRatio || 1;

    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);

    const ctx = canvas.getContext("2d");
    if (ctx.resetTransform) {
      ctx.resetTransform();
    }
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

  // Take recent 50 candles
  const slice = dataToUse.slice(-50);
  const minPrice = Math.min(...slice.map(c => c.low));
  const maxPrice = Math.max(...slice.map(c => c.high));
  const priceRange = (maxPrice - minPrice) || 1.0;

  const topPadding = 30;
  const bottomPadding = 40;
  const rightPadding = 65;
  const leftPadding = 15;
  const usableHeight = height - topPadding - bottomPadding;
  const usableWidth = width - leftPadding - rightPadding;

  const getY = (val) => topPadding + usableHeight - ((val - minPrice) / priceRange) * usableHeight;
  const stepX = usableWidth / slice.length;

  // 1. Draw Background Grid and Y-axis Price Labels
  ctx.strokeStyle = "#1e293b";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#94a3b8";
  ctx.font = "11px monospace";

  const numGridLines = 5;
  for (let i = 0; i <= numGridLines; i++) {
    const y = topPadding + (i / numGridLines) * usableHeight;
    ctx.beginPath();
    ctx.moveTo(leftPadding, y);
    ctx.lineTo(leftPadding + usableWidth, y);
    ctx.stroke();

    const priceVal = maxPrice - (i / numGridLines) * priceRange;
    ctx.fillText(`₹${priceVal.toFixed(2)}`, leftPadding + usableWidth + 6, y + 4);
  }

  // 2. Draw Indicator Lines: EMA 20, EMA 50, VWAP
  drawLine(ctx, slice, stepX, leftPadding, c => c.ema_fast, "#06b6d4", getY);
  drawLine(ctx, slice, stepX, leftPadding, c => c.ema_slow, "#a855f7", getY);
  drawLine(ctx, slice, stepX, leftPadding, c => c.vwap, "#f59e0b", getY);

  // 3. Draw Candlesticks & X-axis timestamps
  const candleWidth = Math.max(3, stepX * 0.65);
  ctx.font = "10px monospace";
  ctx.fillStyle = "#64748b";

  slice.forEach((c, i) => {
    const x = leftPadding + i * stepX + stepX / 2;
    const yOpen = getY(c.open);
    const yClose = getY(c.close);
    const yHigh = getY(c.high);
    const yLow = getY(c.low);
    const isUp = c.close >= c.open;

    const candleColor = isUp ? "#10b981" : "#ef4444";
    ctx.strokeStyle = candleColor;
    ctx.fillStyle = candleColor;

    // Wick
    ctx.beginPath();
    ctx.lineWidth = 1.2;
    ctx.moveTo(x, yHigh);
    ctx.lineTo(x, yLow);
    ctx.stroke();

    // Body
    const bodyTop = Math.min(yOpen, yClose);
    const bodyHeight = Math.max(2, Math.abs(yClose - yOpen));
    ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);

    // Timestamp labels every ~8 candles
    if (i % 8 === 0 || i === slice.length - 1) {
      const timeStr = c.timestamp ? (c.timestamp.includes("T") ? c.timestamp.split("T")[1].slice(0, 5) : c.timestamp.slice(11, 16)) : "";
      ctx.fillStyle = "#64748b";
      ctx.fillText(timeStr, x - 14, height - 15);
    }
  });

  // 4. Current LTP Highlight Line
  const lastCandle = slice[slice.length - 1];
  if (lastCandle) {
    const ltpY = getY(lastCandle.close);
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.moveTo(leftPadding, ltpY);
    ctx.lineTo(leftPadding + usableWidth, ltpY);
    ctx.stroke();
    ctx.setLineDash([]);

    // LTP Pill on Right
    ctx.fillStyle = "#0284c7";
    ctx.fillRect(leftPadding + usableWidth + 2, ltpY - 9, 62, 18);
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 10px monospace";
    ctx.fillText(`₹${lastCandle.close.toFixed(2)}`, leftPadding + usableWidth + 5, ltpY + 4);
  }

  // 5. Header Dynamic Legend
  ctx.font = "11px monospace";
  let legendX = leftPadding;

  ctx.fillStyle = lastCandle && lastCandle.close >= lastCandle.open ? "#10b981" : "#ef4444";
  ctx.fillText(`● LTP: ₹${lastCandle ? lastCandle.close.toFixed(2) : "--"}`, legendX, 16);
  legendX += 130;

  ctx.fillStyle = "#06b6d4";
  ctx.fillText(`● EMA20: ₹${lastCandle?.ema_fast ? lastCandle.ema_fast.toFixed(2) : "--"}`, legendX, 16);
  legendX += 140;

  ctx.fillStyle = "#a855f7";
  ctx.fillText(`● EMA50: ₹${lastCandle?.ema_slow ? lastCandle.ema_slow.toFixed(2) : "--"}`, legendX, 16);
  legendX += 140;

  ctx.fillStyle = "#f59e0b";
  ctx.fillText(`● VWAP: ₹${lastCandle?.vwap ? lastCandle.vwap.toFixed(2) : "--"}`, legendX, 16);
  legendX += 130;

  ctx.fillStyle = "#38bdf8";
  ctx.fillText(`● RSI: ${lastCandle?.rsi ? lastCandle.rsi.toFixed(1) : "--"}`, legendX, 16);
  } catch (err) {
    console.error("drawCanvasChart rendering error:", err);
  }
}

function drawLine(ctx, data, stepX, leftPadding, valueExtractor, color, getY) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.8;
  ctx.beginPath();
  let started = false;

  data.forEach((item, i) => {
    const val = valueExtractor(item);
    if (val !== null && val !== undefined && !isNaN(val)) {
      const x = leftPadding + i * stepX + stepX / 2;
      const y = getY(val);
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
  });
  ctx.stroke();
}

// --- Backtest Form Submission ---
function bindBacktestForm() {
  const form = document.getElementById("backtest-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("btn-run-backtest");
    btn.disabled = true;
    btn.textContent = "⏳ Simulating Market Data...";

    const payload = {
      symbol: document.getElementById("bt-symbol").value.trim(),
      range_period: document.getElementById("bt-range").value,
      interval: "5m",
      initial_capital: parseFloat(document.getElementById("bt-capital").value),
      quantity: parseInt(document.getElementById("bt-qty").value),
      stop_loss_atr_mult: parseFloat(document.getElementById("bt-sl-mult").value),
      target_atr_mult: parseFloat(document.getElementById("bt-tp-mult").value)
    };

    try {
      const res = await fetch(`${getApiBase()}/api/backtest`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      btn.disabled = false;
      btn.textContent = "⚡ Execute Backtest";

      if (data.error) {
        showToast(data.error, true);
        return;
      }

      renderBacktestResults(data);
      showToast("Backtest completed successfully!");
    } catch (err) {
      btn.disabled = false;
      btn.textContent = "⚡ Execute Backtest";
      showToast(`Backtest failed: ${err.message}`, true);
    }
  });
}

function renderBacktestResults(data) {
  const m = data.metrics || {};
  document.getElementById("bt-metrics-container").style.display = "grid";
  document.getElementById("bt-trades-card").style.display = "block";

  document.getElementById("bt-win-rate").textContent = `${m.win_rate || 0}%`;
  document.getElementById("bt-trades-count").textContent = 
    `${m.total_trades || 0} Trades (${m.winning_trades || 0} Wins / ${m.losing_trades || 0} Losses)`;

  const netPnlEl = document.getElementById("bt-net-pnl");
  netPnlEl.textContent = `₹${m.net_pnl?.toFixed(2) || "0.00"}`;
  netPnlEl.className = `metric-val font-mono ${(m.net_pnl || 0) >= 0 ? "text-emerald" : "text-rose"}`;
  document.getElementById("bt-gross-pnl").textContent = 
    `Gross: ₹${m.gross_pnl || 0} | Costs: ₹${m.total_costs || 0}`;

  document.getElementById("bt-profit-factor").textContent = m.profit_factor || "0.0";
  document.getElementById("bt-roc").textContent = `Return on Cap: ${m.return_on_capital_pct || 0}%`;

  document.getElementById("bt-max-dd").textContent = `₹${m.max_drawdown || 0}`;
  document.getElementById("bt-max-dd-pct").textContent = `Peak Drawdown: ${m.max_drawdown_pct || 0}%`;

  // Render Trades
  const tbody = document.querySelector("#bt-trades-table tbody");
  if (tbody) {
    const rows = (data.trades || []).slice(0, 100).map(t => `
      <tr>
        <td>${t.trade_id}</td>
        <td class="${t.side === 'BUY' ? 'text-emerald' : 'text-rose'} font-bold">${t.side}</td>
        <td>${t.entry_time.slice(0, 16)}</td>
        <td>${t.exit_time.slice(0, 16)}</td>
        <td>₹${t.entry_price}</td>
        <td>₹${t.exit_price}</td>
        <td>₹${t.gross_pnl}</td>
        <td>₹${t.costs}</td>
        <td class="${t.net_pnl >= 0 ? 'text-emerald' : 'text-rose'} font-bold">₹${t.net_pnl}</td>
        <td><span class="badge">${t.reason}</span></td>
      </tr>
    `).join("");
    tbody.innerHTML = rows || `<tr><td colspan="10" class="text-center">No trades completed under these rules.</td></tr>`;
  }
}

// --- Fetch & Render Audit Logs ---
async function fetchLogs() {
  try {
    const res = await fetch(`${getApiBase()}/api/logs?limit=50`);
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.querySelector("#audit-table tbody");
    if (!tbody) return;

    const rows = (data.logs || []).reverse().map(l => `
      <tr>
        <td>${l.timestamp_ist || '--'}</td>
        <td class="font-bold">${l.symbol || '--'}</td>
        <td><span class="badge">${l.mode || '--'}</span></td>
        <td><span class="signal-badge ${l.signal === 'BUY' ? 'badge-buy' : l.signal === 'SELL' ? 'badge-sell' : 'badge-wait'}" style="font-size: 0.75rem; padding: 0.2rem 0.5rem; min-width: 60px;">${l.signal}</span></td>
        <td>${l.action || '--'}</td>
        <td>₹${l.price || '--'}</td>
        <td class="text-muted" style="max-width: 350px;">${l.reason || '--'}</td>
      </tr>
    `).join("");

    tbody.innerHTML = rows || `<tr><td colspan="7" class="text-center">No log entries found.</td></tr>`;
  } catch (err) {
    console.error("Logs fetch failed:", err);
  }
}

// --- Configuration Form ---
async function fetchConfig() {
  try {
    const res = await fetch(`${getApiBase()}/api/config`);
    if (!res.ok) return;
    currentConfig = await res.json();

    document.getElementById("cfg-symbol").value = currentConfig.symbol || "ETERNAL.NS";
    document.getElementById("cfg-exchange").value = currentConfig.exchange || "NSE";
    document.getElementById("cfg-timeframe").value = currentConfig.timeframe || "5m";
    document.getElementById("cfg-ema-fast").value = currentConfig.ema_fast || 20;
    document.getElementById("cfg-ema-slow").value = currentConfig.ema_slow || 50;
    document.getElementById("cfg-rsi-period").value = currentConfig.rsi_period || 14;
    document.getElementById("cfg-rsi-buy-min").value = currentConfig.rsi_buy_min || 50;
    document.getElementById("cfg-rsi-buy-max").value = currentConfig.rsi_buy_max || 70;
    document.getElementById("cfg-rsi-sell-min").value = currentConfig.rsi_sell_min || 30;
    document.getElementById("cfg-rsi-sell-max").value = currentConfig.rsi_sell_max || 50;
    document.getElementById("cfg-atr-period").value = currentConfig.atr_period || 14;
    document.getElementById("cfg-sl-mult").value = currentConfig.stop_loss_atr_mult || 1.5;
    document.getElementById("cfg-tp-mult").value = currentConfig.target_atr_mult || 2.0;
    document.getElementById("cfg-capital").value = currentConfig.initial_capital || 100000;
    document.getElementById("cfg-max-risk").value = currentConfig.max_risk_per_trade_rupees || 2000;
    document.getElementById("cfg-market-hours").value = String(currentConfig.enforce_market_hours);
  } catch (err) {
    console.warn("Config fetch failed:", err);
  }
}

function bindSettingsForm() {
  document.getElementById("btn-save-settings")?.addEventListener("click", async () => {
    const payload = {
      symbol: document.getElementById("cfg-symbol").value.trim(),
      exchange: document.getElementById("cfg-exchange").value.trim(),
      timeframe: document.getElementById("cfg-timeframe").value,
      ema_fast: parseInt(document.getElementById("cfg-ema-fast").value),
      ema_slow: parseInt(document.getElementById("cfg-ema-slow").value),
      rsi_period: parseInt(document.getElementById("cfg-rsi-period").value),
      rsi_buy_min: parseFloat(document.getElementById("cfg-rsi-buy-min").value),
      rsi_buy_max: parseFloat(document.getElementById("cfg-rsi-buy-max").value),
      rsi_sell_min: parseFloat(document.getElementById("cfg-rsi-sell-min").value),
      rsi_sell_max: parseFloat(document.getElementById("cfg-rsi-sell-max").value),
      atr_period: parseInt(document.getElementById("cfg-atr-period").value),
      stop_loss_atr_mult: parseFloat(document.getElementById("cfg-sl-mult").value),
      target_atr_mult: parseFloat(document.getElementById("cfg-tp-mult").value),
      initial_capital: parseFloat(document.getElementById("cfg-capital").value),
      max_risk_per_trade_rupees: parseFloat(document.getElementById("cfg-max-risk").value)
    };

    try {
      const res = await fetch(`${getApiBase()}/api/config`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        showToast("Configuration saved successfully!");
        fetchStatus();
      } else {
        showToast(data.detail || data.error || "Failed to update config", true);
      }
    } catch (err) {
      showToast(`Error saving config: ${err.message}`, true);
    }
  });
}

// --- Hybrid Cloud & Tunnel Connection Management ---
function initLocalAIModelConnection() {
  // Initial health checks
  checkBackendHealth(false);
  checkLocalAIHealth(false);
}

async function checkBackendHealth(interactive = false) {
  const badge = document.getElementById("render-backend-badge");
  const teleStatus = document.getElementById("tele-backend-status");
  const currentBase = getApiBase();

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);
    const res = await fetch(`${currentBase}/api/status`, {
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    if (res.ok) {
      if (badge) {
        badge.textContent = "Backend: Online";
        badge.className = "badge font-mono text-emerald";
        badge.style.borderColor = "#10b981";
      }
      if (teleStatus) {
        teleStatus.textContent = "Online";
        teleStatus.className = "text-emerald";
      }
      if (interactive) {
        showToast("Connected to Render Backend!");
      }
      return;
    }
  } catch (err) {}

  if (badge) {
    badge.textContent = "Backend: Offline";
    badge.className = "badge font-mono text-rose";
    badge.style.borderColor = "#f43f5e";
  }
  if (teleStatus) {
    teleStatus.textContent = "Offline";
    teleStatus.className = "text-rose";
  }
  if (interactive) {
    showToast("Backend service is currently offline.", true);
  }
}

async function checkLocalAIHealth(interactive = false) {
  const headers = {
    "Accept": "application/json",
    "ngrok-skip-browser-warning": "1"
  };
  const token = localStorage.getItem("eternal_ai_token") || AI_SECRET_TOKEN || DEFAULT_AI_TOKEN;
  if (token) headers["X-AI-Secret-Token"] = token;

  // 1. Try local laptop tunnel directly first (works if browsing on the laptop)
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 1800);
    const res = await fetch(`${LOCAL_AI_BASE}/health`, {
      signal: controller.signal,
      headers: headers,
      mode: "cors"
    });
    clearTimeout(timeoutId);

    if (res.ok) {
      const info = await res.json();
      const accStr = (info.accuracy != null) ? `${info.accuracy}%` : "Online";
      setTunnelStatusBadges(true, `Laptop Direct: ${accStr}`);
      if (interactive) {
        showToast(`Connected to Laptop AI Model! Accuracy: ${accStr}`);
      }
      return;
    }
  } catch (err) {
    // Localhost unreachable
  }

  // 2. Check if Render backend reports an active live tunnel from your laptop
  try {
    const tunnelRes = await fetch(`${getApiBase()}/api/ai/tunnel-status`, {
      headers: getAuthHeaders()
    });
    if (tunnelRes.ok) {
      const tunnelData = await tunnelRes.json();
      if (tunnelData.tunnel_alive) {
        setTunnelStatusBadges(true, "Via Cloud Tunnel");
        if (interactive) {
          showToast("Connected to Laptop AI Tunnel via Cloud Bridge!");
        }
        return;
      }
    }
  } catch (tunnelErr) {
    // Tunnel status fetch failed
  }

  // 3. Laptop Tunnel is OFF / Unreachable
  setTunnelStatusBadges(false, "Tunnel inactive");
  if (interactive) {
    showToast("Laptop AI Tunnel is Offline. Run start.bat on your PC to connect!", true);
  }
}

// --- Toast Notification Helper ---
function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.style.borderLeftColor = isError ? "var(--color-rose)" : "var(--color-primary)";
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3500);
}

// --- Live Order Execution & Management ---
function bindOrderControls() {
  document.getElementById("btn-fetch-orders")?.addEventListener("click", async () => {
    const msg = document.getElementById("order-status-msg");
    if (msg) {
      msg.textContent = "Fetching Kotak Neo positions and orders...";
      msg.className = "text-xs font-mono mt-2 text-cyan";
    }
    try {
      let posRes = await fetch(`${getApiBase()}/api/orders/positions`, { headers: getAuthHeaders() });
      if (posRes.status === 401) {
        const brokerKey = prompt("Broker API Key required. Please enter X-Broker-Key:");
        if (brokerKey) {
          sessionStorage.setItem("eternal_broker_key", brokerKey.trim());
          posRes = await fetch(`${getApiBase()}/api/orders/positions`, { headers: getAuthHeaders() });
        }
      }
      const ordRes = await fetch(`${getApiBase()}/api/orders/history`, { headers: getAuthHeaders() });
      const posData = await posRes.json();
      const ordData = await ordRes.json();

      const posCount = Array.isArray(posData.positions) ? posData.positions.length : 0;
      const ordCount = Array.isArray(ordData.orders) ? ordData.orders.length : 0;

      if (msg) {
        msg.textContent = `Open Positions: ${posCount} | Daily Orders: ${ordCount}`;
        msg.className = "text-xs font-mono mt-2 text-emerald";
      }
      showToast(`Positions: ${posCount}, Orders: ${ordCount}`);
    } catch (err) {
      if (msg) {
        msg.textContent = `Error fetching positions: ${err.message}`;
        msg.className = "text-xs font-mono mt-2 text-rose";
      }
      showToast(`Error: ${err.message}`, true);
    }
  });
}


