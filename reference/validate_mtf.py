"""Validate the engine across the full timeframe ladder.

The ladder Paul wants: 5m, 15m, 30m, 1H, 90m, 4H, 6H, 1D, 2D, 1W, 1M, with
30m / 90m / 6H / 1W / 1M as the non-negotiable minimum.

Each timeframe is evaluated independently -- a trend only has to be true for
its own timeframe -- so what matters here is that every rung produces a
defensible state, and that the ladder behaves the way a ladder should: higher
timeframes steadier than lower ones, and enough history to answer at all.

Run: python3 reference/validate_mtf.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mtf_trend import (DOWN, INSUFFICIENT, SIDEWAYS, TRANSITION, UP, run)
from validate_real import DATA, flips, load, state_mix


def resample(bars, n):
    """Aggregate n bars into one: high=max, low=min, close=last."""
    out = []
    for i in range(0, len(bars) - n + 1, n):
        chunk = bars[i:i + n]
        out.append((max(b[0] for b in chunk), min(b[1] for b in chunk), chunk[-1][2]))
    return out


def ladder_report(title, bars, rungs, lookback):
    print(f"\n{'=' * 74}\n{title}  (lookback L={lookback})\n{'=' * 74}")
    print(f"  {'TF':>6} {'bars':>6} {'usable':>7} | {'Up':>4} {'Dn':>4} {'Side':>5} {'Trn':>4} "
          f"{'Insuf':>6} | {'bars/flip':>9} | OTC mode: {'Up':>4} {'Dn':>4} {'Side':>5}")
    prev_per = None
    warnings = []
    for label, mult in rungs:
        b = resample(bars, mult)
        need = lookback + 20
        if len(b) < need:
            warnings.append(f"{label}: only {len(b)} bars, needs >{need} to leave Insufficient")
            print(f"  {label:>6} {len(b):>6} {'NO':>7} | {'-':>4} {'-':>4} {'-':>5} {'-':>4} "
                  f"{'100':>6} | {'-':>9} | {'-':>4} {'-':>4} {'-':>5}")
            continue
        res = run(b, lookback=lookback)
        otc = run(b, lookback=lookback, structure_pivots=3, otc_mode=True)
        lo = need
        m, mo = state_mix(res, lo), state_mix(otc, lo)
        f = flips(res, lo)
        per = (len(res) - lo) / max(f, 1)
        print(f"  {label:>6} {len(b):>6} {'yes':>7} | {m[UP]:>4.0f} {m[DOWN]:>4.0f} {m[SIDEWAYS]:>5.0f} "
              f"{m[TRANSITION]:>4.0f} {m[INSUFFICIENT]:>6.0f} | {per:>9.0f} | "
              f"{mo[UP]:>4.0f} {mo[DOWN]:>4.0f} {mo[SIDEWAYS]:>5.0f}")
        prev_per = per
    for w in warnings:
        print(f"  ! {w}")
    return warnings


def main():
    if not (DATA / "futures_5min.csv").exists():
        print("No data. Run: python3 reference/fetch_real_data.py")
        return 1

    # Intraday rungs, built from real 5-minute index-futures bars.
    intraday = load(DATA / "futures_5min.csv")
    ladder_report(
        f"INTRADAY LADDER from real 5-minute index futures ({len(intraday)} bars)",
        intraday,
        [("5m", 1), ("15m", 3), ("30m", 6), ("1H", 12), ("90m", 18), ("4H", 48), ("6H", 72)],
        lookback=30,
    )

    # High rungs, built from 16 years of real daily bars.
    daily = load(DATA / "nvda_daily.csv")
    ladder_report(
        f"HIGH-TIMEFRAME LADDER from real daily bars ({len(daily)} bars, ~16 years)",
        daily,
        [("1D", 1), ("2D", 2), ("1W", 5), ("1M", 21)],
        lookback=75,
    )

    print(f"\n{'=' * 74}\nHISTORY REQUIRED AT THE DEFAULT LOOKBACK (L=75)\n{'=' * 74}")
    print("  A timeframe cannot leave Insufficient until it has L bars of its own.")
    print(f"  {'TF':>6} {'bars needed':>12} {'= calendar span':>22}")
    for label, span_hours in [("30m", 0.5), ("90m", 1.5), ("6H", 6), ("1D", 24),
                              ("1W", 24 * 7), ("1M", 24 * 30)]:
        hours = 75 * span_hours
        if hours < 48:
            span = f"{hours:.0f} hours"
        elif hours < 24 * 90:
            span = f"{hours / 24:.0f} days"
        else:
            span = f"{hours / 24 / 30:.0f} months"
        print(f"  {label:>6} {75:>12} {span:>22}")
    print("\n  The monthly row therefore needs ~6 years of monthly bars loaded.")
    print("  If it reads Insufficient on a chart, lower the lookback rather than")
    print("  assuming the indicator is broken.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
