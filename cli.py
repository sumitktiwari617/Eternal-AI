import sys
import os
import time
import argparse
from datetime import datetime
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure current directory is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings, update_settings
from execution.engine import engine
from execution.logger import get_recent_logs
from core.backtester import run_backtest
from core.rsi_engine import run_pure_rsi_backtest
from data.fetcher import fetch_historical_candles
from core.risk_manager import calculate_trade_brackets

# Autonomous AI Engine imports
from ai.model import ai_model
from ai.explainer import generate_decision_reason
from ai.auto_learner import auto_learner


def format_currency(val: Optional[float]) -> str:
    if val is None:
        return "₹--.--"
    return f"₹{val:,.2f}"


def print_banner():
    print("=" * 65)
    print("      ⚡ ETERNAL AI TRADING AGENT — CLI TERMINAL ⚡      ")
    print("      Intraday Momentum Engine (NSE / Kotak Neo)        ")
    print("=" * 65)


def cmd_status(args=None):
    print_banner()
    state = engine.get_dashboard_state()

    print(f"Time (IST):         {state['server_time_ist']}")
    print(f"Target Asset:       {state['symbol']} ({state['exchange']})")
    print(f"Timeframe:          {state['timeframe']}")
    print(f"Agent State:        {state['agent_state']}")
    print(f"Agent Mode:         {state['agent_mode']}")
    print(f"Emergency Stop:     {'ACTIVE 🛑' if state['emergency_stop'] else 'CLEARED ✅'}")
    print(f"Real Orders:        {'ENABLED ⚠️' if state['real_orders_enabled'] else 'DISABLED (Paper Only) ✅'}")
    print("-" * 65)

    q = state.get("last_quote")
    if q:
        sign = "+" if q.get("change", 0) >= 0 else ""
        print(f"Last Price (LTP):   {format_currency(q.get('ltp'))} | Change: {sign}{q.get('change', 0):.2f} ({sign}{q.get('change_pct', 0):.2f}%)")
        print(f"Day Range:          High: {format_currency(q.get('high'))} | Low: {format_currency(q.get('low'))} | Open: {format_currency(q.get('open'))}")
        print(f"Volume:             {q.get('volume', 0):,} shares")
        print(f"Quote Timestamp:    {q.get('timestamp')}")
    else:
        print("Market Quote:       Not loaded yet. Run 'analyze' to fetch latest.")

    print("-" * 65)
    d = state.get("last_decision")
    if not d:
        recent = get_recent_logs(limit=1, config=settings)
        if recent:
            last = recent[-1]
            d = {
                "signal": last.get("signal"),
                "action": last.get("action"),
                "reason": last.get("reason"),
                "indicators": last.get("indicators", {}),
                "brackets": last.get("brackets", {}),
                "timestamp": last.get("timestamp_ist"),
            }

    if d:
        print(f"Latest Signal:      [{d.get('signal')}] -> {d.get('action')}")
        print(f"Reason:             {d.get('reason')}")
        ind = d.get("indicators", {})
        print(f"Price & Indicators: Price: {format_currency(ind.get('price'))} | EMA20: {format_currency(ind.get('ema_fast'))} | EMA50: {format_currency(ind.get('ema_slow'))} | VWAP: {format_currency(ind.get('vwap'))} | RSI14: {ind.get('rsi')} | ATR: {format_currency(ind.get('atr'))}")
        brk = d.get("brackets", {})
        if brk:
            print(f"Trade Brackets:     Entry: {format_currency(brk.get('entry_price'))} | Stop: {format_currency(brk.get('stop_loss'))} | Target: {format_currency(brk.get('target'))} | R:R: {brk.get('risk_reward_ratio')}")
    else:
        print("Latest Signal:      No analysis cycle run yet.")

    print("-" * 65)
    ks = state.get("kotak_status", {})
    print(f"Kotak Neo SDK:      {'Installed' if ks.get('sdk_installed') else 'Not Installed (Using Yahoo Finance)'}")
    print(f"Kotak Credentials:  {'Configured' if ks.get('has_credentials') else 'Not Set (Paper Mode)'}")
    print(f"Kotak Auth Session: {'Active' if ks.get('is_authenticated') else 'Inactive'}")
    print("=" * 65)


def cmd_analyze(args=None):
    symbol = getattr(args, "symbol", None) or settings.symbol
    if symbol != settings.symbol:
        update_settings({"symbol": symbol})

    print(f"\n🔍 Fetching latest market candles for {symbol} ({settings.timeframe})...")
    res = engine.run_single_analysis()

    if not res.get("success"):
        print(f"❌ Analysis failed: {res.get('error')}")
        return

    d = res.get("decision", {})
    ind = d.get("indicators", {})
    brk = d.get("brackets", {})

    print("\n" + "=" * 65)
    print(f"📊 ETERNAL MARKET ANALYSIS: {symbol}")
    print("=" * 65)
    print(f"Timestamp:          {d.get('timestamp')}")
    print(f"LTP (Price):        {format_currency(ind.get('price'))}")
    print(f"Fast EMA (20):      {format_currency(ind.get('ema_fast'))}")
    print(f"Slow EMA (50):      {format_currency(ind.get('ema_slow'))}")
    print(f"Intraday VWAP:      {format_currency(ind.get('vwap'))}")
    print(f"Wilder's RSI (14):  {ind.get('rsi')}")
    print(f"ATR (14 Volatility):{format_currency(ind.get('atr'))}")
    print("-" * 65)
    print(f"AI DECISION:        ▶ {d.get('signal')} ({d.get('action')}) ◀")
    print(f"RATIONALE:          {d.get('reason')}")
    print("-" * 65)
    print("SUGGESTED TRADE BRACKETS:")
    print(f"  • Entry Reference:{format_currency(brk.get('entry_price'))}")
    print(f"  • Stop-Loss (1.5x):{format_currency(brk.get('stop_loss'))}")
    print(f"  • Target (2.0x):  {format_currency(brk.get('target'))}")
    print(f"  • Risk/Reward:    {brk.get('risk_reward_ratio')}")
    print(f"  • Suggested Qty:  {brk.get('suggested_quantity')} shares")
    print(f"  • Max Risk:       {format_currency(brk.get('estimated_max_risk_rupees'))}")
    print(f"  • Target Profit:  {format_currency(brk.get('estimated_target_profit_rupees'))}")
    print("=" * 65)
    print(f"Paper trade audit logged to: {settings.paper_log_file}\n")


def cmd_backtest(args=None):
    symbol = getattr(args, "symbol", None) or settings.symbol
    range_period = getattr(args, "range", "60d") or "60d"
    interval = getattr(args, "interval", "5m") or "5m"
    capital = getattr(args, "capital", None) or settings.initial_capital
    qty = getattr(args, "qty", None) or settings.default_quantity

    print(f"\n⚡ Running Backtest on {symbol} (Range: {range_period}, Interval: {interval})...")
    df = fetch_historical_candles(symbol=symbol, range_period=range_period, interval=interval, config=settings)

    if df is None or len(df) < 50:
        print(f"❌ Error: Insufficient candle history for {symbol}. Fetched {len(df) if df is not None else 0} candles.")
        return

    res = run_backtest(df, config=settings, export_csv=True)
    if not res.get("success"):
        print(f"❌ Backtest failed: {res.get('error')}")
        return

    m = res.get("metrics", {})
    trades = res.get("trades", [])

    print("\n" + "=" * 65)
    print(f"🏆 BACKTEST PERFORMANCE SUMMARY: {symbol}")
    print("=" * 65)
    print(f"Candles Analyzed:   {m.get('candles_analyzed', 0):,}")
    print(f"Initial Capital:    {format_currency(capital)}")
    print(f"Total Completed:    {m.get('total_trades', 0)} trades")
    print(f"Winning Trades:     {m.get('winning_trades', 0)} ✅")
    print(f"Losing Trades:      {m.get('losing_trades', 0)} ❌")
    print(f"Win Rate:           {m.get('win_rate', 0)}%")
    print("-" * 65)
    print(f"Gross P&L:          {format_currency(m.get('gross_pnl', 0))}")
    print(f"Estimated Friction: {format_currency(m.get('total_costs', 0))} (0.05% per side)")
    print(f"NET PROFIT/LOSS:    {format_currency(m.get('net_pnl', 0))}")
    print(f"Return on Capital:  {m.get('return_on_capital_pct', 0)}%")
    print(f"Profit Factor:      {m.get('profit_factor', 0)}")
    print(f"Max Drawdown:       {format_currency(m.get('max_drawdown', 0))} ({m.get('max_drawdown_pct', 0)}%)")
    print(f"Average Win:        {format_currency(m.get('avg_win', 0))}")
    print(f"Average Loss:       {format_currency(m.get('avg_loss', 0))}")
    print("-" * 65)

    print("SIDE BREAKDOWN:")
    for side, sdata in m.get("side_breakdown", {}).items():
        print(f"  • {side:5s} -> {sdata.get('trades')} trades | Win Rate: {sdata.get('win_rate')}% | Net P&L: {format_currency(sdata.get('net_pnl'))}")

    print("EXIT REASONS:")
    for reason, rdata in m.get("reason_breakdown", {}).items():
        print(f"  • {reason:15s} -> {rdata.get('trades')} trades | Net P&L: {format_currency(rdata.get('net_pnl'))}")

    print("=" * 65)
    print(f"Trade records saved to: {settings.backtest_csv_file} ({len(trades)} trades)\n")


def cmd_backtest_rsi(args=None):
    symbol = getattr(args, "symbol", None) or settings.symbol
    range_period = getattr(args, "range", "6mo") or "6mo"
    interval = getattr(args, "interval", "1h") or "1h"
    capital = getattr(args, "capital", None) or 100000.0
    qty = getattr(args, "qty", None) or 100
    allow_short = getattr(args, "short", False)

    print(f"\n⚡ Running 6-Month Pure RSI 9 & 14 Backtest on {symbol} (Interval: {interval})...")
    df = fetch_historical_candles(symbol=symbol, range_period=range_period, interval=interval, config=settings)

    if df is None or len(df) < 25:
        print(f"❌ Error: Insufficient candle history for {symbol}. Fetched {len(df) if df is not None else 0} candles.")
        return

    res = run_pure_rsi_backtest(
        df,
        initial_capital=capital,
        quantity=qty,
        min_rsi_slow=50.0,
        overbought_rsi=70.0,
        allow_short=allow_short,
        stop_loss_pct=0.04
    )

    if not res.get("success"):
        print(f"❌ Backtest failed: {res.get('error')}")
        return

    m = res.get("metrics", {})
    trades = res.get("trades", [])

    print("\n" + "=" * 65)
    print(f"📈 6-MONTH PURE RSI (9 & 14) PERFORMANCE REPORT: {symbol}")
    print("=" * 65)
    print(f"Strategy:           {m.get('strategy')}")
    print(f"Testing Period:     {m.get('date_start', '')[:10]} to {m.get('date_end', '')[:10]} (6 Months)")
    print(f"Candles Analyzed:   {m.get('candles_analyzed', 0):,} ({interval} bars)")
    print(f"Initial Capital:    {format_currency(capital)}")
    print(f"Trade Quantity:     {qty} shares")
    print(f"Total Completed:    {m.get('total_trades', 0)} trades")
    print(f"Winning Trades:     {m.get('winning_trades', 0)} ✅")
    print(f"Losing Trades:      {m.get('losing_trades', 0)} ❌")
    print(f"Win Rate:           {m.get('win_rate', 0)}%")
    print("-" * 65)
    print(f"Gross P&L:          {format_currency(m.get('gross_pnl', 0))}")
    print(f"Friction Costs:     {format_currency(m.get('friction_costs', 0))} (0.05% brokerage)")
    print(f"NET PROFIT/LOSS:    {format_currency(m.get('net_pnl', 0))}")
    print(f"Return on Capital:  {m.get('return_on_capital_pct', 0)}%")
    print(f"Profit Factor:      {m.get('profit_factor', 0)}")
    print(f"Max Drawdown:       {format_currency(m.get('max_drawdown', 0))} ({m.get('max_drawdown_pct', 0)}%)")
    print(f"Average Win:        {format_currency(m.get('avg_win', 0))}")
    print(f"Average Loss:       {format_currency(m.get('avg_loss', 0))}")
    print(f"Win/Loss Ratio:     {m.get('win_loss_ratio', 0)}")
    print("-" * 65)

    print("SAMPLE COMPLETED TRADES (Recent 10):")
    for t in trades[-10:]:
        print(f"  #{t.get('trade_id'):2d} [{t.get('side'):4s}] {t.get('entry_time')[:10]} @ {format_currency(t.get('entry_price'))} -> {t.get('exit_time')[:10]} @ {format_currency(t.get('exit_price'))} | Net: {format_currency(t.get('net_pnl'))} ({t.get('reason')})")

    csv_path = "eternal_rsi_backtest_results.csv"
    import pandas as pd
    pd.DataFrame(trades).to_csv(csv_path, index=False)
    print("=" * 65)
    print(f"Full trade-by-trade history exported to: {csv_path} ({len(trades)} trades)\n")


def cmd_ai(args=None):
    symbol = getattr(args, "symbol", None) or settings.symbol
    print_banner()
    print(f"🤖 Running Autonomous AI Inference for {symbol}...")
    
    # Ensure 6-month model is loaded/trained
    auto_learner.ensure_initial_training()

    df = fetch_historical_candles(symbol=symbol, range_period="5d", interval=settings.timeframe, config=settings)
    if df is None or len(df) < 20:
        print(f"❌ Error: Insufficient candle history for {symbol}.")
        return

    pred = ai_model.predict(df, confidence_threshold=55.0)
    reason = generate_decision_reason(pred)

    price = pred["latest_price"]
    atr_norm = pred["feature_snapshot"].get("atr_normalized", 1.0)
    atr = max(0.5, (atr_norm / 100.0) * price)

    brackets = calculate_trade_brackets(
        entry_price=price,
        atr=atr,
        side=pred["signal"] if pred["signal"] in ("BUY", "SELL") else "BUY",
        config=settings
    )

    print("\n" + "=" * 65)
    print(f"🧠 ETERNAL AUTONOMOUS AI PREDICTION: {symbol}")
    print("=" * 65)
    print(f"LTP (Price):        {format_currency(price)}")
    print(f"AI SIGNAL:          ▶ {pred['signal']} ◀")
    print(f"CONFIDENCE:         {pred['confidence']}%")
    print(f"MODEL ACCURACY:     {pred['model_accuracy']}% (6-Month Out-Of-Sample)")
    probs = pred["probabilities"]
    print(f"PROBABILITIES:      BUY: {probs.get('BUY', 0)}% | HOLD: {probs.get('HOLD', 0)}% | SELL: {probs.get('SELL', 0)}%")
    print("-" * 65)
    print(f"DECISION REASON:    \n\"{reason}\"")
    print("-" * 65)
    print("RECOMMENDED BRACKETS:")
    print(f"  • Entry Reference:{format_currency(brackets.get('entry_price'))}")
    print(f"  • Stop-Loss:      {format_currency(brackets.get('stop_loss'))}")
    print(f"  • Target:         {format_currency(brackets.get('target'))}")
    print(f"  • Risk / Reward:  {brackets.get('risk_reward_ratio')}")
    print(f"  • Suggested Qty:  {brackets.get('suggested_quantity')} shares")
    print("=" * 65)
    print(f"Model status: Auto-trained on 6-month historical data.")
    print(f"Next automatic retraining: Daily at 15:30 IST (Market close).\n")


def cmd_monitor(args=None):
    interval = getattr(args, "interval", None) or settings.poll_interval_seconds
    print_banner()
    print(f"🔄 Starting Live CLI Monitoring (Polling interval: {interval}s)...")
    print("Press Ctrl+C to stop monitoring.")
    engine.start()

    try:
        while True:
            res = engine.run_single_analysis()
            if res.get("success"):
                d = res.get("decision", {})
                ind = d.get("indicators", {})
                now_str = datetime.now().strftime("%H:%M:%S")
                print(f"[{now_str}] LTP: {format_currency(ind.get('price'))} | EMA20: {format_currency(ind.get('ema_fast'))} | VWAP: {format_currency(ind.get('vwap'))} | RSI: {ind.get('rsi')} -> SIGNAL: {d.get('signal')} ({d.get('action')})")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
        engine.pause()


def cmd_emergency_stop(args=None):
    res = engine.emergency_stop()
    print(f"\n🛑 {res.get('message')}\n")


def cmd_reset(args=None):
    res = engine.reset()
    print(f"\n🔄 {res.get('message')}\n")


def cmd_server(args=None):
    host = getattr(args, "host", None) or settings.server_host
    port = getattr(args, "port", None) or settings.server_port
    print_banner()
    print(f"🚀 Launching Web Interface & REST API on http://{host}:{port}")
    print("Press Ctrl+C to terminate.")
    import uvicorn
    uvicorn.run("backend.app:app", host=host, port=port, reload=False)


def cmd_ai_server(args=None):
    host = getattr(args, "host", None) or settings.ai_service_host
    port = getattr(args, "port", None) or settings.ai_service_port
    print_banner()
    print("🧠 LOCALHOST AI MODEL MICROSERVICE")
    print(f"🚀 Running locally on http://{host}:{port}")
    print(f"   • Predict Endpoint:   http://{host}:{port}/api/ai/predict")
    print(f"   • Accuracy Trend:     http://{host}:{port}/api/ai/accuracy-trend")
    print(f"   • Retrain Trigger:    http://{host}:{port}/api/ai/retrain")
    print(f"   • Interactive Docs:   http://{host}:{port}/docs")
    print(f"   • Autonomous Retrain: Active (Daily at 15:30 IST Indian Market Close)")
    print("-" * 65)
    print("Ready to receive requests from Local or Cloud-Hosted Backend & Frontend.")
    print("Press Ctrl+C to terminate.")
    print("=" * 65)
    import uvicorn
    uvicorn.run("ai.server:app", host=host, port=port, reload=False)


def interactive_menu():
    while True:
        print_banner()
        print("1. 🤖 Run Autonomous AI Prediction (Signal, Confidence & Reason)")
        print("2. 🧠 Launch Localhost AI Model Microservice (Port 8001)")
        print("3. View Dashboard & System Status")
        print("4. Run Instant Market Analysis & Technical Indicators")
        print("5. Execute Historical Strategy Backtest (Intraday)")
        print("6. Execute 6-Month Pure RSI 9 & 14 Backtest")
        print("7. Start Continuous Terminal Monitoring")
        print("8. Launch Full-Stack Web Dashboard & REST Server (Port 8000)")
        print("9. 🛑 EMERGENCY STOP")
        print("10. 🔄 Reset / Clear Emergency Stop")
        print("0. Exit")
        print("-" * 65)
        choice = input("Enter choice (0-10): ").strip()

        if choice == "1":
            cmd_ai()
        elif choice == "2":
            cmd_ai_server()
            break
        elif choice == "3":
            cmd_status()
        elif choice == "4":
            cmd_analyze()
        elif choice == "5":
            cmd_backtest()
        elif choice == "6":
            cmd_backtest_rsi()
        elif choice == "7":
            cmd_monitor()
        elif choice == "8":
            cmd_server()
            break
        elif choice == "9":
            cmd_emergency_stop()
        elif choice == "10":
            cmd_reset()
        elif choice == "0":
            print("Exiting ETERNAL CLI. Goodbye!")
            sys.exit(0)
        else:
            print("Invalid choice. Please select 0-10.")
        
        input("\nPress Enter to continue...")


def main():
    parser = argparse.ArgumentParser(description="ETERNAL AI Trading Agent CLI")
    subparsers = parser.add_subparsers(dest="command")

    # AI Prediction
    p_ai = subparsers.add_parser("ai", help="Run real-time Autonomous AI Inference with Confidence & Reason")
    p_ai.add_argument("--symbol", type=str, default=None, help="Target asset symbol (e.g. ETERNAL.NS)")

    # AI Model Dedicated Microservice
    p_aisrv = subparsers.add_parser("ai-server", help="Launch Localhost AI Model Microservice (Port 8001)")
    p_aisrv.add_argument("--host", type=str, default="127.0.0.1", help="Host address")
    p_aisrv.add_argument("--port", type=int, default=8001, help="Port number")

    # Status
    subparsers.add_parser("status", help="Display agent status and telemetry")

    # Analyze
    p_analyze = subparsers.add_parser("analyze", help="Perform single market analysis")
    p_analyze.add_argument("--symbol", type=str, default=None, help="Target asset symbol (e.g. ETERNAL.NS)")

    # Backtest Intraday
    p_bt = subparsers.add_parser("backtest", help="Execute historical strategy backtest")
    p_bt.add_argument("--symbol", type=str, default=None, help="Symbol to backtest")
    p_bt.add_argument("--range", type=str, default="60d", help="Historical range (5d, 1mo, 60d)")
    p_bt.add_argument("--interval", type=str, default="5m", help="Candle interval (5m, 15m)")
    p_bt.add_argument("--capital", type=float, default=None, help="Initial capital in ₹")
    p_bt.add_argument("--qty", type=int, default=None, help="Quantity per trade")

    # Backtest Pure RSI 9 & 14 (6 Months)
    p_rsi = subparsers.add_parser("backtest-rsi", help="Execute 6-month Pure RSI 9 & 14 Backtest")
    p_rsi.add_argument("--symbol", type=str, default=None, help="Symbol to backtest")
    p_rsi.add_argument("--range", type=str, default="6mo", help="Historical range (6mo, 1y)")
    p_rsi.add_argument("--interval", type=str, default="1h", help="Candle interval (1h, 1d)")
    p_rsi.add_argument("--capital", type=float, default=None, help="Initial capital in ₹")
    p_rsi.add_argument("--qty", type=int, default=100, help="Quantity per trade")
    p_rsi.add_argument("--short", action="store_true", help="Allow short selling")

    # Monitor
    p_mon = subparsers.add_parser("monitor", help="Start continuous live polling")
    p_mon.add_argument("--interval", type=int, default=30, help="Polling interval in seconds")

    # Emergency Stop
    subparsers.add_parser("emergency-stop", help="Activate emergency stop")

    # Reset
    subparsers.add_parser("reset", help="Reset emergency stop to idle")

    # Server
    p_server = subparsers.add_parser("server", help="Launch FastAPI web server")
    p_server.add_argument("--host", type=str, default="127.0.0.1", help="Host address")
    p_server.add_argument("--port", type=int, default=8000, help="Port number")

    args = parser.parse_args()

    if args.command == "ai":
        cmd_ai(args)
    elif args.command == "ai-server":
        cmd_ai_server(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "backtest":
        cmd_backtest(args)
    elif args.command == "backtest-rsi":
        cmd_backtest_rsi(args)
    elif args.command == "monitor":
        cmd_monitor(args)
    elif args.command == "emergency-stop":
        cmd_emergency_stop(args)
    elif args.command == "reset":
        cmd_reset(args)
    elif args.command == "server":
        cmd_server(args)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
