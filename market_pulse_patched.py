# Market_Pulse.py — Market Pulse Bot (webhook, scheduled)
import os, sys, time
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

import requests
import pandas as pd
import yfinance as yf
import yaml
import pytz
from dotenv import load_dotenv

SCRIPT_NAME = os.path.basename(__file__)
HERE = Path(__file__).parent
ENV_PATH = HERE / ".env"
CFG_PATH = HERE / "config.yaml"

def ts(): return time.strftime("%Y-%m-%d %H:%M:%S")
def banner():
    print("=" * 70); print(f"🚀 Starting script: {SCRIPT_NAME}"); print("=" * 70)
def log(level, msg): print(f"[{ts()}] ({SCRIPT_NAME}) [{level}] {msg}")
def info(m): log("INFO", m)
def warn(m): log("WARN", m)
def err(m):  log("ERROR", m)

def load_cfg():
    if CFG_PATH.exists():
        try:
            return yaml.safe_load(CFG_PATH.read_text()) or {}
        except Exception as e:
            warn(f"Could not parse config.yaml: {e}")
    return {}

def cfg(d, path, default=None):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur: return default
        cur = cur[part]
    return cur

def preview_df(df: pd.DataFrame, name: str, rows: int):
    if df is None or getattr(df, "empty", True):
        warn(f"{name}: empty dataframe"); return
    n = min(rows, len(df))
    info(f"{name}: rows={len(df)}; preview top {n}:")
    print(df.head(n).to_string())

def compute_rsi(close: pd.Series, period: int = 14):
    if close is None or close.empty or len(close) < period + 1: return None
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.dropna()
    return float(round(rsi.iloc[-1], 2)) if not rsi.empty else None

def fetch_snapshot(ticker: str, preview_rows: int):
    snap = {"ticker": ticker, "last": None, "chg_pct": None, "rsi": None}
    try:
        info(f"[API] yfinance.download({ticker}, period='1d', interval='1m')")
        df_1m = yf.download(ticker, period="1d", interval="1m", progress=False)
        preview_df(df_1m, f"{ticker} 1m (today)", preview_rows)
        if df_1m is not None and not df_1m.empty:
            last_close = df_1m["Close"].iloc[-1]
            snap["last"] = float(round(last_close, 2))
            if len(df_1m) > 1:
                prev = df_1m["Close"].iloc[-2]
                if prev and prev != 0:
                    snap["chg_pct"] = float(round((last_close - prev) / prev * 100.0, 2))

        info(f"[API] yfinance.download({ticker}, period='7d', interval='15m') for RSI")
        df_15m = yf.download(ticker, period="7d", interval="15m", progress=False)
        preview_df(df_15m, f"{ticker} 15m (7d)", preview_rows)
        if df_15m is not None and not df_15m.empty:
            snap["rsi"] = compute_rsi(df_15m["Close"])
    except Exception as e:
        err(f"{ticker} fetch error: {e}")
    info(f"{ticker} summary: last={snap.get('last')} | Δ%={snap.get('chg_pct')} | RSI={snap.get('rsi')}")
    return snap

def build_message(snaps):
    lines = []
    lines.append("📊 **Market Pulse Bot — Snapshot**")
    lines.append(f"_Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} local_")
    lines.append("")
    lines.append("```")
    lines.append(f"{'Ticker':<8} {'Last':>9} {'Δ%':>7} {'RSI(14)':>8}")
    lines.append("-" * 34)
    for s in snaps:
        last = f"{s.get('last'):.2f}" if isinstance(s.get('last'), (int, float)) else "n/a"
        chg  = f"{s.get('chg_pct'):.2f}" if isinstance(s.get('chg_pct'), (int, float)) else "n/a"
        rsi  = f"{s.get('rsi'):.2f}" if isinstance(s.get('rsi'), (int, float)) else "n/a"
        lines.append(f"{s['ticker']:<8} {last:>9} {chg:>7} {rsi:>8}")
    lines.append("```")
    return "\n".join(lines)

def post_discord(webhook: str, content: str) -> bool:
    try:
        r = requests.post(webhook, json={"content": content}, timeout=30)
        if 200 <= r.status_code < 300:
            info("✅ Posted to Discord successfully."); return True
        err(f"Discord webhook error {r.status_code}: {r.text}"); return False
    except Exception as e:
        err(f"Discord webhook exception: {e}"); return False

def run_once(tickers, webhook, preview_rows):
    snaps = [fetch_snapshot(t, preview_rows) for t in tickers]
    msg = build_message(snaps)
    ok = post_discord(webhook, msg)
    if not ok: err("Failed to post snapshot.")

# ---- Scheduler (US/Eastern market hours) ----
def minutes_since_open(now_et: datetime, open_t: dtime) -> float:
    mo = now_et.replace(hour=open_t.hour, minute=open_t.minute, second=0, microsecond=0)
    return (now_et - mo).total_seconds() / 60.0

def sleep_until(seconds: float):
    # tiny helper to keep logs readable during long sleeps
    mins = int(max(0, seconds) // 60)
    info(f"[SCHED] Sleeping ~{mins} min.")
    time.sleep(max(1.0, seconds))

def main():
    banner()
    # Load env & config
    info(f"Loading .env from: {ENV_PATH}")
    load_dotenv(dotenv_path=ENV_PATH)
    cfg_all = load_cfg()

    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        err("DISCORD_WEBHOOK_URL not set in .env"); sys.exit(1)

    # Tickers: env overrides config.yaml
    env_tickers = os.getenv("TICKERS", "").strip()
    if env_tickers:
        tickers = [t.strip().upper() for t in env_tickers.split(",") if t.strip()]
    else:
        tickers = cfg(cfg_all, "market.tickers", ["SPY","QQQ","DIA"])

    log_level  = (cfg(cfg_all, "log.level", "INFO") or "INFO").upper()
    sample_rows= int(cfg(cfg_all, "log.sample_rows", 3))
    early_int  = int(cfg(cfg_all, "market.update_schedule.early_interval_minutes", 30))
    early_dur  = int(cfg(cfg_all, "market.update_schedule.early_duration_minutes", 150))
    later_int  = int(cfg(cfg_all, "market.update_schedule.later_interval_minutes", 60))
    open_str   = cfg(cfg_all, "market.market_open", "09:30")
    close_str  = cfg(cfg_all, "market.market_close", "16:00")

    info(f"Tickers: {', '.join(tickers)}")
    info(f"Schedule: every {early_int}m for first {early_dur}m after open, then every {later_int}m until close")
    info(f"Market hours (ET): {open_str}–{close_str}")

    # Timezones
    ET = pytz.timezone("US/Eastern")
    open_h, open_m   = map(int, open_str.split(":"))
    close_h, close_m = map(int, close_str.split(":"))
    MARKET_OPEN  = dtime(open_h, open_m)
    MARKET_CLOSE = dtime(close_h, close_m)

    # Main loop
    while True:
        now_et = datetime.now(ET)
        today_open  = now_et.replace(hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute, second=0, microsecond=0)
        today_close = now_et.replace(hour=MARKET_CLOSE.hour, minute=MARKET_CLOSE.minute, second=0, microsecond=0)

        # If within market hours: run and then sleep for the correct interval
        if today_open.time() <= now_et.time() <= today_close.time():
            mins_open = minutes_since_open(now_et, MARKET_OPEN)
            interval  = early_int if mins_open <= early_dur else later_int
            info(f"[SCHED] Tick @ {now_et.strftime('%Y-%m-%d %H:%M %Z')} (mins since open: {int(mins_open)}) → next in {interval} min")
            run_once(tickers, webhook, sample_rows)
            time.sleep(interval * 60)
            continue

        # Outside market hours: sleep until next open
        if now_et.time() > today_close.time():
            # After close → next open tomorrow (skip weekends)
            next_day = now_et + timedelta(days=1)
            while next_day.weekday() >= 5:  # 5=Sat, 6=Sun
                next_day += timedelta(days=1)
            next_open = next_day.replace(hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute, second=0, microsecond=0, tzinfo=ET)
        else:
            # Before open today
            next_open = today_open

        sleep_secs = (next_open - now_et).total_seconds()
        info(f"[SCHED] Market closed. Next open: {next_open.strftime('%Y-%m-%d %H:%M %Z')}")
        sleep_until(sleep_secs)

if __name__ == "__main__":
    main()
