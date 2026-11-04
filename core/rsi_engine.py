from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np


def calculate_wilders_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Computes Wilder's smoothed RSI for a price series."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Boundary handling
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    rsi = rsi.where(~((avg_gain == 0) & (avg_loss > 0)), 0.0)
    return rsi.fillna(50.0)


def evaluate_pure_rsi_signal(
    curr_row: pd.Series,
    prev_row: pd.Series,
    min_rsi_slow: float = 50.0,
    overbought_rsi: float = 70.0,
    oversold_rsi: float = 30.0,
    allow_short: bool = True
) -> Dict[str, Any]:
    """
    Evaluates trading signal using STRICTLY RSI 9 and RSI 14 (No EMA, No VWAP).

    Rules:
      BUY (Long Entry):
        - RSI 9 crosses above RSI 14 (Bullish Momentum Crossover)
        - Slower RSI 14 >= min_rsi_slow (Bullish Momentum Regime, default >= 50)
        - RSI 9 < overbought_rsi (Not already overextended)

      SELL (Short Entry - if enabled):
        - RSI 9 crosses below RSI 14 (Bearish Momentum Crossover)
        - Slower RSI 14 <= (100 - min_rsi_slow) (Bearish Momentum Regime, default <= 50)
        - RSI 9 > oversold_rsi (Not already in deep oversold bounce)

      EXIT CONDITIONS:
        - Long Exit: RSI 9 crosses below RSI 14 OR RSI 9 >= overbought_rsi
        - Short Exit: RSI 9 crosses above RSI 14 OR RSI 9 <= oversold_rsi
    """
    r9_curr = float(curr_row.get("RSI9", 50.0))
    r14_curr = float(curr_row.get("RSI14", 50.0))
    r9_prev = float(prev_row.get("RSI9", 50.0))
    r14_prev = float(prev_row.get("RSI14", 50.0))

    bull_cross = (r9_prev <= r14_prev) and (r9_curr > r14_curr)
    bear_cross = (r9_prev >= r14_prev) and (r9_curr < r14_curr)

    if bull_cross and r14_curr >= min_rsi_slow and r9_curr < overbought_rsi:
        return {
            "signal": "BUY",
            "action": "BUY (RSI 9 > RSI 14 Cross)",
            "reason": f"Bullish RSI cross: RSI9 ({r9_curr:.1f}) crossed above RSI14 ({r14_curr:.1f}) in bullish regime (>= {min_rsi_slow}).",
            "rsi9": round(r9_curr, 2),
            "rsi14": round(r14_curr, 2),
        }

    if allow_short and bear_cross and r14_curr <= (100.0 - min_rsi_slow) and r9_curr > oversold_rsi:
        return {
            "signal": "SELL",
            "action": "SELL (RSI 9 < RSI 14 Cross)",
            "reason": f"Bearish RSI cross: RSI9 ({r9_curr:.1f}) crossed below RSI14 ({r14_curr:.1f}) in bearish regime (<= {100.0 - min_rsi_slow}).",
            "rsi9": round(r9_curr, 2),
            "rsi14": round(r14_curr, 2),
        }

    return {
        "signal": "WAIT",
        "action": "WAIT",
        "reason": f"RSI 9 ({r9_curr:.1f}) / RSI 14 ({r14_curr:.1f}) - No fresh crossover alignment.",
        "rsi9": round(r9_curr, 2),
        "rsi14": round(r14_curr, 2),
    }


def run_pure_rsi_backtest(
    df: pd.DataFrame,
    initial_capital: float = 100000.0,
    quantity: int = 100,
    cost_rate_per_side: float = 0.0005,  # 0.05% brokerage/charges
    min_rsi_slow: float = 50.0,
    overbought_rsi: float = 70.0,
    oversold_rsi: float = 30.0,
    allow_short: bool = False,
    stop_loss_pct: Optional[float] = 0.04  # 4% safety stop loss
) -> Dict[str, Any]:
    """
    Executes a pure RSI 9 & RSI 14 backtest on the given DataFrame.
    """
    if df is None or len(df) < 25:
        return {
            "success": False,
            "error": "Insufficient candle history (minimum 25 candles required).",
            "trades": [],
            "metrics": {},
        }

    data = df.copy()
    data.columns = [str(c).lower() for c in data.columns]

    close = data["close"]
    data["RSI9"] = calculate_wilders_rsi(close, 9)
    data["RSI14"] = calculate_wilders_rsi(close, 14)

    trades: List[Dict[str, Any]] = []
    position: Optional[Dict[str, Any]] = None

    for i in range(15, len(data) - 1):
        curr_row = data.iloc[i]
        prev_row = data.iloc[i - 1]
        next_row = data.iloc[i + 1]

        r9_curr = float(curr_row["RSI9"])
        r14_curr = float(curr_row["RSI14"])
        r9_prev = float(prev_row["RSI9"])
        r14_prev = float(prev_row["RSI14"])

        bull_cross = (r9_prev <= r14_prev) and (r9_curr > r14_curr)
        bear_cross = (r9_prev >= r14_prev) and (r9_curr < r14_curr)

        # 1. Manage Active Position Exit
        if position is not None:
            side = position["side"]
            entry = position["entry"]
            entry_time = str(position["time"])
            exit_price = None
            reason = None

            if side == "BUY":
                # Safety Stop Loss %
                if stop_loss_pct and float(curr_row["low"]) <= entry * (1.0 - stop_loss_pct):
                    exit_price = entry * (1.0 - stop_loss_pct)
                    reason = f"Safety Stop ({stop_loss_pct*100:.1f}%)"
                # RSI Overbought Take Profit Target
                elif r9_curr >= overbought_rsi:
                    exit_price = float(curr_row["close"])
                    reason = f"RSI 9 Overbought (Take Profit @ {r9_curr:.1f} >= {overbought_rsi})"
                # Reverse Bearish Crossover Exit
                elif bear_cross:
                    exit_price = float(next_row["open"])
                    reason = f"RSI 9 Bearish Cross RSI 14 ({r9_curr:.1f} < {r14_curr:.1f})"

            elif side == "SELL" and allow_short:
                # Safety Stop Loss %
                if stop_loss_pct and float(curr_row["high"]) >= entry * (1.0 + stop_loss_pct):
                    exit_price = entry * (1.0 + stop_loss_pct)
                    reason = f"Safety Stop ({stop_loss_pct*100:.1f}%)"
                # RSI Oversold Take Profit Target
                elif r9_curr <= oversold_rsi:
                    exit_price = float(curr_row["close"])
                    reason = f"RSI 9 Oversold (Take Profit @ {r9_curr:.1f} <= {oversold_rsi})"
                # Reverse Bullish Crossover Exit
                elif bull_cross:
                    exit_price = float(next_row["open"])
                    reason = f"RSI 9 Bullish Cross RSI 14 ({r9_curr:.1f} > {r14_curr:.1f})"

            if exit_price is not None:
                gross = (exit_price - entry) * quantity if side == "BUY" else (entry - exit_price) * quantity
                costs = (entry + exit_price) * quantity * cost_rate_per_side
                net = gross - costs

                trades.append({
                    "trade_id": len(trades) + 1,
                    "side": side,
                    "entry_time": entry_time,
                    "exit_time": str(data.index[i]),
                    "entry_price": round(entry, 2),
                    "exit_price": round(exit_price, 2),
                    "quantity": quantity,
                    "gross_pnl": round(gross, 2),
                    "costs": round(costs, 2),
                    "net_pnl": round(net, 2),
                    "exit_rsi9": round(r9_curr, 2),
                    "exit_rsi14": round(r14_curr, 2),
                    "reason": reason,
                })
                position = None

        # 2. Check for New Entry (Only if not already in position)
        if position is None:
            sig = evaluate_pure_rsi_signal(
                curr_row, prev_row,
                min_rsi_slow=min_rsi_slow,
                overbought_rsi=overbought_rsi,
                oversold_rsi=oversold_rsi,
                allow_short=allow_short
            )
            if sig["signal"] in ("BUY", "SELL"):
                position = {
                    "side": sig["signal"],
                    "entry": float(next_row["open"]),
                    "time": data.index[i + 1],
                    "entry_rsi9": sig["rsi9"],
                    "entry_rsi14": sig["rsi14"],
                }

    # 3. Close leftover position at final candle
    if position is not None:
        last = data.iloc[-1]
        exit_p = float(last["close"])
        side = position["side"]
        gross = (exit_p - position["entry"]) * quantity if side == "BUY" else (position["entry"] - exit_p) * quantity
        costs = (position["entry"] + exit_p) * quantity * cost_rate_per_side
        net = gross - costs
        trades.append({
            "trade_id": len(trades) + 1,
            "side": side,
            "entry_time": str(position["time"]),
            "exit_time": str(data.index[-1]),
            "entry_price": round(position["entry"], 2),
            "exit_price": round(exit_p, 2),
            "quantity": quantity,
            "gross_pnl": round(gross, 2),
            "costs": round(costs, 2),
            "net_pnl": round(net, 2),
            "exit_rsi9": round(float(last["RSI9"]), 2),
            "exit_rsi14": round(float(last["RSI14"]), 2),
            "reason": "End of 6M Test Period",
        })

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
            }
        }

    tdf = pd.DataFrame(trades)
    total = len(tdf)
    wins = int((tdf["net_pnl"] > 0).sum())
    losses = int((tdf["net_pnl"] < 0).sum())
    win_rate = round((wins / total) * 100.0, 2)

    gross_pnl = round(float(tdf["gross_pnl"].sum()), 2)
    costs = round(float(tdf["costs"].sum()), 2)
    net_pnl = round(float(tdf["net_pnl"].sum()), 2)

    win_sum = float(tdf.loc[tdf["net_pnl"] > 0, "net_pnl"].sum())
    loss_sum = abs(float(tdf.loc[tdf["net_pnl"] < 0, "net_pnl"].sum()))
    profit_factor = round(win_sum / loss_sum, 2) if loss_sum > 0 else 999.0

    # Drawdown
    equity = tdf["net_pnl"].cumsum() + initial_capital
    peak = equity.cummax()
    dd = peak - equity
    max_dd = round(float(dd.max()), 2)
    max_dd_pct = round(float((dd / peak).max() * 100.0), 2)

    avg_win = round(float(tdf.loc[tdf["net_pnl"] > 0, "net_pnl"].mean()), 2) if wins > 0 else 0.0
    avg_loss = round(float(tdf.loc[tdf["net_pnl"] < 0, "net_pnl"].mean()), 2) if losses > 0 else 0.0

    return {
        "success": True,
        "trades": trades,
        "metrics": {
            "strategy": "Pure RSI 9 & RSI 14 (No EMA, No VWAP)",
            "candles_analyzed": len(data),
            "date_start": str(data.index[0]),
            "date_end": str(data.index[-1]),
            "initial_capital": initial_capital,
            "quantity": quantity,
            "total_trades": total,
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate": win_rate,
            "gross_pnl": gross_pnl,
            "friction_costs": costs,
            "net_pnl": net_pnl,
            "return_on_capital_pct": round((net_pnl / initial_capital) * 100.0, 2),
            "profit_factor": profit_factor,
            "max_drawdown": max_dd,
            "max_drawdown_pct": max_dd_pct,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "win_loss_ratio": round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0.0,
        }
    }

