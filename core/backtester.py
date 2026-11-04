from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd
import numpy as np

from config import Settings, settings as default_settings
from core.indicators import calculate_indicators
from core.strategy import evaluate_signal


def run_backtest(
    df: pd.DataFrame,
    config: Optional[Settings] = None,
    export_csv: bool = True
) -> Dict[str, Any]:
    """
    Runs an event-driven historical backtest on OHLCV candles without lookahead bias.
    Signals generated on bar i trigger entry at bar i+1 Open.
    Intra-candle stop-loss and take-profit hits are evaluated using High and Low.
    """
    cfg = config or default_settings

    if df is None or len(df) < 50:
        return {
            "success": False,
            "error": "Insufficient historical data for backtesting (minimum 50 candles required).",
            "trades": [],
            "metrics": {},
        }

    # Ensure indicators are calculated
    data = calculate_indicators(
        df,
        ema_fast=cfg.ema_fast,
        ema_slow=cfg.ema_slow,
        rsi_period=cfg.rsi_period,
        atr_period=cfg.atr_period,
    )

    quantity = cfg.default_quantity
    cost_rate = cfg.cost_rate_per_side
    trades: List[Dict[str, Any]] = []
    position: Optional[Dict[str, Any]] = None

    dates = data.index.date if isinstance(data.index, pd.DatetimeIndex) else [None] * len(data)

    for i in range(len(data) - 1):
        row = data.iloc[i]
        next_row = data.iloc[i + 1]

        current_day = dates[i]
        next_day = dates[i + 1]

        # 1. Close open position before session end (No overnight holding)
        if position is not None and next_day is not None and current_day != next_day:
            exit_price = float(row["close"])
            if position["side"] == "BUY":
                gross = (exit_price - position["entry"]) * quantity
            else:
                gross = (position["entry"] - exit_price) * quantity

            costs = (position["entry"] + exit_price) * quantity * cost_rate
            trades.append({
                "trade_id": len(trades) + 1,
                "side": position["side"],
                "entry_time": str(position["time"]),
                "exit_time": str(data.index[i]),
                "entry_price": round(position["entry"], 2),
                "exit_price": round(exit_price, 2),
                "quantity": quantity,
                "gross_pnl": round(gross, 2),
                "costs": round(costs, 2),
                "net_pnl": round(gross - costs, 2),
                "reason": "End of Session",
            })
            position = None

        # 2. Check Intra-Candle Stop-Loss or Target for active position
        if position is not None:
            high = float(row["high"])
            low = float(row["low"])
            exit_price = None
            reason = None

            if position["side"] == "BUY":
                stop_hit = low <= position["stop"]
                target_hit = high >= position["target"]

                # Conservative rule: if both hit in same 5m candle, stop takes priority
                if stop_hit:
                    exit_price = position["stop"]
                    reason = "Stop-loss"
                elif target_hit:
                    exit_price = position["target"]
                    reason = "Target"
            else:  # SELL / SHORT
                stop_hit = high >= position["stop"]
                target_hit = low <= position["target"]

                if stop_hit:
                    exit_price = position["stop"]
                    reason = "Stop-loss"
                elif target_hit:
                    exit_price = position["target"]
                    reason = "Target"

            if exit_price is not None:
                if position["side"] == "BUY":
                    gross = (exit_price - position["entry"]) * quantity
                else:
                    gross = (position["entry"] - exit_price) * quantity

                costs = (position["entry"] + exit_price) * quantity * cost_rate
                trades.append({
                    "trade_id": len(trades) + 1,
                    "side": position["side"],
                    "entry_time": str(position["time"]),
                    "exit_time": str(data.index[i]),
                    "entry_price": round(position["entry"], 2),
                    "exit_price": round(exit_price, 2),
                    "quantity": quantity,
                    "gross_pnl": round(gross, 2),
                    "costs": round(costs, 2),
                    "net_pnl": round(gross - costs, 2),
                    "reason": reason,
                })
                position = None

        # If still in a trade, do not take another signal
        if position is not None:
            continue

        # Do not enter if current candle is the last of the day
        if next_day is not None and current_day != next_day:
            continue

        # 3. Evaluate Signal for New Trade Entry
        decision = evaluate_signal(row, cfg)
        sig = decision["signal"]
        atr = float(row.get(f"ATR{cfg.atr_period}", 0.0))

        if sig in ("BUY", "SELL") and atr > 0:
            entry_price = float(next_row["open"])

            if sig == "BUY":
                stop = entry_price - (cfg.stop_loss_atr_mult * atr)
                target = entry_price + (cfg.target_atr_mult * atr)
            else:
                stop = entry_price + (cfg.stop_loss_atr_mult * atr)
                target = entry_price - (cfg.target_atr_mult * atr)

            position = {
                "side": sig,
                "time": data.index[i + 1],
                "entry": entry_price,
                "stop": stop,
                "target": target,
                "atr": atr,
            }

    # 4. Close any leftover open position at final candle
    if position is not None:
        last = data.iloc[-1]
        exit_price = float(last["close"])
        if position["side"] == "BUY":
            gross = (exit_price - position["entry"]) * quantity
        else:
            gross = (position["entry"] - exit_price) * quantity

        costs = (position["entry"] + exit_price) * quantity * cost_rate
        trades.append({
            "trade_id": len(trades) + 1,
            "side": position["side"],
            "entry_time": str(position["time"]),
            "exit_time": str(data.index[-1]),
            "entry_price": round(position["entry"], 2),
            "exit_price": round(exit_price, 2),
            "quantity": quantity,
            "gross_pnl": round(gross, 2),
            "costs": round(costs, 2),
            "net_pnl": round(gross - costs, 2),
            "reason": "End of Test",
        })
        position = None

    # Compute Performance Analytics
    if not trades:
        return {
            "success": True,
            "trades": [],
            "metrics": {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "net_pnl": 0.0,
                "gross_pnl": 0.0,
                "total_costs": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "max_drawdown_pct": 0.0,
                "avg_trade_pnl": 0.0,
                "side_breakdown": {},
                "reason_breakdown": {},
            },
        }

    res = pd.DataFrame(trades)
    total_trades = len(res)
    winning_trades = int((res["net_pnl"] > 0).sum())
    losing_trades = int((res["net_pnl"] < 0).sum())
    win_rate = round((winning_trades / total_trades) * 100.0, 2)

    gross_pnl = round(float(res["gross_pnl"].sum()), 2)
    total_costs = round(float(res["costs"].sum()), 2)
    net_pnl = round(float(res["net_pnl"].sum()), 2)

    total_wins = res.loc[res["net_pnl"] > 0, "net_pnl"].sum()
    total_losses = abs(res.loc[res["net_pnl"] < 0, "net_pnl"].sum())
    profit_factor = round(total_wins / total_losses, 2) if total_losses > 0 else (999.0 if total_wins > 0 else 0.0)

    # Calculate Drawdown
    equity_curve = res["net_pnl"].cumsum() + cfg.initial_capital
    peak = equity_curve.cummax()
    drawdown = peak - equity_curve
    max_dd = round(float(drawdown.max()), 2)
    max_dd_pct = round(float((drawdown / peak).max() * 100.0), 2)

    # Breakdowns
    side_breakdown = {}
    for side, group in res.groupby("side"):
        side_breakdown[side] = {
            "trades": len(group),
            "wins": int((group["net_pnl"] > 0).sum()),
            "losses": int((group["net_pnl"] < 0).sum()),
            "net_pnl": round(float(group["net_pnl"].sum()), 2),
            "win_rate": round(float((group["net_pnl"] > 0).mean() * 100.0), 2),
        }

    reason_breakdown = {}
    for reason, group in res.groupby("reason"):
        reason_breakdown[reason] = {
            "trades": len(group),
            "net_pnl": round(float(group["net_pnl"].sum()), 2),
        }

    metrics = {
        "symbol": cfg.symbol,
        "candles_analyzed": len(data),
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "gross_pnl": gross_pnl,
        "total_costs": total_costs,
        "net_pnl": net_pnl,
        "return_on_capital_pct": round((net_pnl / cfg.initial_capital) * 100.0, 2),
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "max_drawdown_pct": max_dd_pct,
        "avg_win": round(float(res.loc[res["net_pnl"] > 0, "net_pnl"].mean()), 2) if winning_trades > 0 else 0.0,
        "avg_loss": round(float(res.loc[res["net_pnl"] < 0, "net_pnl"].mean()), 2) if losing_trades > 0 else 0.0,
        "side_breakdown": side_breakdown,
        "reason_breakdown": reason_breakdown,
    }

    if export_csv and cfg.backtest_csv_file:
        try:
            res.to_csv(cfg.backtest_csv_file, index=False)
        except Exception:
            pass

    return {
        "success": True,
        "trades": trades,
        "metrics": metrics,
    }

