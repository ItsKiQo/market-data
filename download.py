# -*- coding: utf-8 -*-
"""
FREE top-up of 1-minute NQ and Gold futures candles from Yahoo Finance
into the data/ folder of this repo. No account, no API key, no cost.

Needs once:  pip install yfinance

Yahoo only serves 1-minute bars for about the last 30 days, in windows of
about a week, so this has to run at least every couple of weeks.
Each run fetches what is missing and merges it into one growing file per market.
"""
import sys
import datetime as dt
from pathlib import Path

SYMBOLS = {"NQ": "NQ=F", "GC": "GC=F"}
MAX_BACK_DAYS = 29      # Yahoo limit for 1-minute bars
CHUNK_DAYS = 6          # safe size of one request

here = Path(__file__).resolve().parent
out_dir = here / "data"
out_dir.mkdir(parents=True, exist_ok=True)
log = out_dir / "update_log.txt"


def say(msg):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line)
    with open(log, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    try:
        import pandas as pd
        import yfinance as yf
    except ImportError:
        say("STOP: package 'yfinance' is missing. Run: pip install yfinance")
        return 1

    now = dt.datetime.now(dt.timezone.utc)
    oldest = now - dt.timedelta(days=MAX_BACK_DAYS)
    bad = 0
    for root, ysym in SYMBOLS.items():
        path = out_dir / f"{root}_1m_yahoo.csv"
        old = None
        start = oldest
        if path.exists():
            old = pd.read_csv(path, parse_dates=["ts_utc"])
            old["ts_utc"] = pd.to_datetime(old["ts_utc"], utc=True)
            if len(old):
                start = max(oldest, old["ts_utc"].max().to_pydatetime() - dt.timedelta(hours=12))
        parts = []
        t = start
        while t < now:
            t2 = min(t + dt.timedelta(days=CHUNK_DAYS), now)
            try:
                df = yf.Ticker(ysym).history(start=t, end=t2, interval="1m", auto_adjust=False)
            except Exception as e:
                say(f"{root}: request {t:%m-%d} -> {t2:%m-%d} failed: {type(e).__name__}: {e}")
                df = None
            if df is not None and len(df):
                df = df.reset_index()
                tcol = df.columns[0]
                df["ts_utc"] = pd.to_datetime(df[tcol], utc=True)
                df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
                parts.append(df[["ts_utc", "open", "high", "low", "close", "volume"]])
            t = t2
        if not parts:
            say(f"{root}: no new bars received")
            bad += 1
            continue
        new = pd.concat(parts, ignore_index=True)
        allb = new if old is None else pd.concat([old, new], ignore_index=True)
        before = 0 if old is None else len(old)
        allb = allb.dropna(subset=["close"]).drop_duplicates("ts_utc", keep="last").sort_values("ts_utc")
        allb.to_csv(path, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
        say(f"{root}: +{len(allb) - before} bars, file now {len(allb)} bars, "
            f"{allb['ts_utc'].min():%Y-%m-%d %H:%M} -> {allb['ts_utc'].max():%Y-%m-%d %H:%M} UTC")
    return 1 if bad == len(SYMBOLS) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        say(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(1)
