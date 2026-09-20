"""Fetch public OHLC datasets used by validate_real.py.

NQ intraday history is not freely downloadable, so these are proxies chosen
for structural similarity rather than being the instrument itself. The
5-minute index-futures set is the closest analog: an index future, intraday,
with real session gaps.

Run: python3 reference/fetch_real_data.py
"""

import csv
import math
import io
import sys
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "data"

SOURCES = {
    "futures_5min.csv": (
        "https://raw.githubusercontent.com/mementum/backtrader/master/datas/2006-min-005.txt",
        {},
    ),
    "futures_daily.csv": (
        "https://raw.githubusercontent.com/mementum/backtrader/master/datas/2005-2006-day-001.txt",
        {},
    ),
    "nvda_daily.csv": (
        "https://raw.githubusercontent.com/mementum/backtrader/master/datas/nvda-1999-2014.txt",
        {},
    ),
    "btc_hourly.csv": (
        "https://raw.githubusercontent.com/bukosabino/ta/master/test/data/datas.csv",
        {"every": 4},  # thin it out to keep the fixture small
    ),
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "trend-indicator-validation"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def normalise(text, every=1):
    """Keep only High/Low/Close, however the source spells them."""
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return []
    cols = {k.lower().split(".")[-1]: k for k in rows[0]}
    try:
        h, l, c = cols["high"], cols["low"], cols["close"]
    except KeyError:
        return []
    out = []
    for i, row in enumerate(rows):
        if i % every:
            continue
        try:
            vals = (float(row[h]), float(row[l]), float(row[c]))
        except (ValueError, TypeError):
            continue
        # Sources use sentinels for missing bars -- the BTC set writes 1.7e308.
        if not all(math.isfinite(v) and 0 < v < 1e9 for v in vals):
            continue
        out.append(vals)
    return out


def main():
    DATA.mkdir(exist_ok=True)
    failures = 0
    for name, (url, opts) in SOURCES.items():
        try:
            bars = normalise(fetch(url), opts.get("every", 1))
            if not bars:
                raise ValueError("no usable rows")
            with open(DATA / name, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["High", "Low", "Close"])
                w.writerows(bars)
            print(f"  {name}: {len(bars)} bars")
        except Exception as exc:
            failures += 1
            print(f"  {name}: FAILED ({exc})")
    return 1 if failures == len(SOURCES) else 0


if __name__ == "__main__":
    sys.exit(main())
