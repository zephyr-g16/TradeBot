#!/usr/bin/env python3
import json, sys, math, datetime as dt
from pathlib import Path

def load_events(path):
    data = json.loads(Path(path).read_text())
    # ensure chronological
    data.sort(key=lambda e: e.get("raw_timestamp") or 0)
    return data

def to_dt(ts_str):
    # your file has ISO strings like "2025-08-15T08:06:42.156224"
    return dt.datetime.fromisoformat(ts_str)

def analyze(path):
    evs = load_events(path)
    open_buy = None
    closed = []  # list of dicts with buy/sell + pnl

    for e in evs:
        evt = e.get("event", "").lower()
        px  = e.get("price")
        ts  = e.get("timestamp")
        if px is None or not ts:
            continue

        if evt == "buy_executed":
            # if there’s already an open, we assume single position -> overwrite or ignore
            open_buy = {"ts": to_dt(ts), "px": float(px)}
        elif evt == "trailing stop sale" and open_buy:
            sell = {"ts": to_dt(ts), "px": float(px)}
            pnl = sell["px"] - open_buy["px"]             # per-unit PnL
            ret = sell["px"] / open_buy["px"] - 1.0       # percent return
            hold_s = (sell["ts"] - open_buy["ts"]).total_seconds()
            closed.append({
                "buy_ts": open_buy["ts"], "buy_px": open_buy["px"],
                "sell_ts": sell["ts"],   "sell_px": sell["px"],
                "pnl": pnl, "ret": ret, "hold_s": hold_s
            })
            open_buy = None  # position closed

    if not closed:
        print("No closed trades found.")
        return

    # summary stats
    n = len(closed)
    wins   = [c for c in closed if c["pnl"] > 0]
    losses = [c for c in closed if c["pnl"] < 0]
    total  = sum(c["pnl"] for c in closed)
    wr     = len(wins) / n
    avg_win  = (sum(c["pnl"] for c in wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(c["pnl"] for c in losses) / len(losses)) if losses else 0.0
    avg_ret  = sum(c["ret"] for c in closed) / n
    avg_hold = sum(c["hold_s"] for c in closed) / n

    # equity + max drawdown (in PnL units)
    eq, peak, mdd = 0.0, -math.inf, 0.0
    for c in closed:
        eq += c["pnl"]
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)

    def pct(x): return f"{x*100:.2f}%"
    def money(x): return f"{x:.2f}"

    print(f"File: {path}")
    print(f"Trades: {n} | Win rate: {pct(wr)}")
    print(f"Total PnL (per-unit): {money(total)} | Avg win: {money(avg_win)} | Avg loss: {money(avg_loss)}")
    print(f"Avg return/trade: {pct(avg_ret)} | Avg hold: {avg_hold/60:.1f} min")
    print(f"Max drawdown (per-unit): {money(mdd)}")

    # show last few trades
    print("\nRecent trades:")
    for c in closed[-5:]:
        print(f"  {c['buy_ts']} buy {c['buy_px']:.2f} -> {c['sell_ts']} sell {c['sell_px']:.2f}  "
              f"PnL {money(c['pnl'])}  ({pct(c['ret'])})  hold {c['hold_s']/60:.1f}m")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python utils/analyze_sol.py trade_data/SOL/trade_calls.json")
        sys.exit(2)
    analyze(sys.argv[1])