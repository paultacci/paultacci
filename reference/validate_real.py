"""Validate the trend engine against real market data.

The synthetic harness in validate.py proves the logic is correct. This one
asks the harder question: how does it behave on real bars, which have fat
tails, gaps, session breaks and regimes that synthetic paths never produce.

Data is fetched from public GitHub repos (see fetch_real_data.py). None of it
is NQ -- NQ intraday history is not freely downloadable -- but the 5-minute
index-futures set is structurally the closest available proxy: an index
future, intraday, with real session gaps.

Run: python3 reference/validate_real.py
"""

import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mtf_trend import (DOWN, INSUFFICIENT, SIDEWAYS, STATE_NAMES, TRANSITION,
                       UP, run)

DATA = Path(__file__).parent / "data"


def load(path, high="High", low="Low", close="Close"):
    bars = []
    with open(path) as fh:
        for row in csv.DictReader(fh):
            try:
                bars.append((float(row[high]), float(row[low]), float(row[close])))
            except (ValueError, KeyError, TypeError):
                continue
    return bars


def state_mix(results, lo=0):
    seg = [r["state"] for r in results[lo:]]
    n = len(seg)
    return {s: 100.0 * seg.count(s) / n for s in (UP, DOWN, SIDEWAYS, TRANSITION, INSUFFICIENT)} if n else {}


def flips(results, lo=0):
    seg = [r["state"] for r in results[lo:]]
    return sum(1 for a, b in zip(seg, seg[1:]) if a != b)


def zigzag_legs(closes, thresh):
    """Ex-post turning points, used ONLY to score the engine.

    This looks ahead by construction, which is exactly why it never appears in
    the engine itself -- it is a grading key, not a signal.
    """
    legs = []
    direction = 1  # provisional; the first reversal settles it
    pivot_i, ext, ext_i = 0, closes[0], 0
    for i, c in enumerate(closes):
        if direction > 0:
            if c > ext:
                ext, ext_i = c, i
            elif (ext - c) / ext > thresh:
                legs.append((pivot_i, ext_i, 1))
                pivot_i, direction, ext, ext_i = ext_i, -1, c, i
        else:
            if c < ext:
                ext, ext_i = c, i
            elif (c - ext) / ext > thresh:
                legs.append((pivot_i, ext_i, -1))
                pivot_i, direction, ext, ext_i = ext_i, 1, c, i
    return legs


def confirmation_delay(results, legs, min_len=10):
    """Bars from a real turning point to the engine agreeing with the new leg."""
    delays, missed = [], 0
    for start, end, direction in legs:
        if end - start < min_len:
            continue
        want = UP if direction > 0 else DOWN
        hit = next((i for i in range(start, end + 1) if results[i]["state"] == want), None)
        if hit is None:
            missed += 1
        else:
            delays.append(hit - start)
    return delays, missed


def report(name, bars, thresh, lookback=50, **kw):
    res = run(bars, lookback=lookback, **kw)
    lo = lookback + 20
    mix = state_mix(res, lo)
    closes = [b[2] for b in bars]
    legs = zigzag_legs(closes, thresh)
    delays, missed = confirmation_delay(res, legs)
    n = len(res) - lo

    print(f"\n--- {name}  ({len(bars)} bars) ---")
    print(f"  state mix:  Up {mix[UP]:.0f}%  Down {mix[DOWN]:.0f}%  "
          f"Sideways {mix[SIDEWAYS]:.0f}%  Transition {mix[TRANSITION]:.0f}%  "
          f"Insufficient {mix[INSUFFICIENT]:.0f}%")
    print(f"  stability:  {flips(res, lo)} state changes over {n} bars "
          f"= 1 per {n / max(flips(res, lo), 1):.0f} bars")
    if delays:
        print(f"  confirmation delay vs {len(legs)} real turning points "
              f"({thresh:.1%} zigzag): median {statistics.median(delays):.0f} bars, "
              f"p90 {sorted(delays)[int(0.9 * len(delays)) - 1]:.0f} bars, "
              f"never caught {missed}/{len(delays) + missed} legs")
    return res


def main():
    if not DATA.exists():
        print("No data. Run: python3 reference/fetch_real_data.py")
        return 1

    print("=" * 70)
    print("REAL MARKET DATA VALIDATION")
    print("=" * 70)

    sets = [
        ("Index futures 5-min (closest NQ proxy)", "futures_5min.csv", 0.004),
        ("Index futures daily", "futures_daily.csv", 0.03),
        ("NVDA daily 1999-2014 (dot-com + 2008)", "nvda_daily.csv", 0.10),
        ("BTC hourly (24/7, no session breaks)", "btc_hourly.csv", 0.06),
    ]
    loaded = []
    for label, fname, thresh in sets:
        p = DATA / fname
        if not p.exists():
            print(f"\n(skipping {label}: {fname} not present)")
            continue
        bars = load(p)
        if len(bars) < 200:
            print(f"\n(skipping {label}: only {len(bars)} bars)")
            continue
        loaded.append((label, bars, thresh))
        report(label, bars, thresh)

    if not loaded:
        return 1

    # Parameter sensitivity on the most NQ-like set available.
    label, bars, thresh = loaded[0]
    print("\n" + "=" * 70)
    print(f"PARAMETER SENSITIVITY ON REAL BARS -- {label}")
    print("=" * 70)
    print(f"  {'L':>4} {'thr':>5} {'H':>3} {'flips':>6} {'1 per':>7} "
          f"{'%Up':>5} {'%Dn':>5} {'%Side':>6} {'%Trans':>7} {'medDelay':>9}")
    closes = [b[2] for b in bars]
    legs = zigzag_legs(closes, thresh)
    for L in (20, 50, 100):
        for tr in (1.5, 2.5):
            for H in (2, 5):
                res = run(bars, lookback=L, slope_threshold=tr, hysteresis=H)
                lo = L + 20
                mix = state_mix(res, lo)
                f = flips(res, lo)
                n = len(res) - lo
                d, _ = confirmation_delay(res, legs)
                md = statistics.median(d) if d else float("nan")
                print(f"  {L:>4} {tr:>5} {H:>3} {f:>6} {n / max(f, 1):>7.0f} "
                      f"{mix[UP]:>5.0f} {mix[DOWN]:>5.0f} {mix[SIDEWAYS]:>6.0f} "
                      f"{mix[TRANSITION]:>7.0f} {md:>9.0f}")

    print("\n  Range cutoff (efficiency gate) on real bars, L=50 thr=1.5 H=2:")
    print(f"  {'cutoff':>7} {'%Side':>6} {'%Trans':>7} {'%Up':>5} {'%Dn':>5} {'flips':>6}")
    for rer in (0.0, 0.15, 0.25, 0.35, 0.50):
        res = run(bars, lookback=50, range_er=rer)
        lo = 70
        mix = state_mix(res, lo)
        print(f"  {rer:>7.2f} {mix[SIDEWAYS]:>6.0f} {mix[TRANSITION]:>7.0f} "
              f"{mix[UP]:>5.0f} {mix[DOWN]:>5.0f} {flips(res, lo):>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
