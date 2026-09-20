"""Validation harness for the trend-context engine.

Covers the evaluation criteria in the design spec that can be checked without
a live chart:
  - does the state machine label known regimes correctly (spec 6.1)
  - label stability / flip rate (spec 6.2)
  - parameter sensitivity (spec 6.4)
  - historical vs. live consistency, i.e. no lookahead (spec 6.5)

Data is synthetic. That validates LOGIC, not tuning -- final parameter choices
still have to be made against real NQ bars in TradingView.

Run: python3 reference/validate.py
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mtf_trend import STATE_NAMES, UP, DOWN, SIDEWAYS, TRANSITION, INSUFFICIENT, TrendEngine, run


def make_bars(closes, noise=0.35, seed=7):
    """Turn a close path into OHLC bars with plausible intrabar range."""
    rng = random.Random(seed)
    bars = []
    for i, c in enumerate(closes):
        prev = closes[i - 1] if i else c
        base = abs(c - prev) + abs(c) * 1e-4
        up = base * rng.uniform(0.2, 1.2) * noise
        dn = base * rng.uniform(0.2, 1.2) * noise
        bars.append((max(c, prev) + up, min(c, prev) - dn, c))
    return bars


def path_trend(n, drift_sigmas, sigma=0.0011, start=20000.0, seed=1):
    rng = random.Random(seed)
    c, out = start, []
    for _ in range(n):
        c *= 1 + rng.gauss(drift_sigmas * sigma, sigma)
        out.append(c)
    return out


def path_range(n, sigma=0.0011, start=20000.0, seed=2, pull=0.05):
    """Mean-reverting (Ornstein-Uhlenbeck-ish) path: no net direction."""
    rng = random.Random(seed)
    anchor, c, out = start, start, []
    for _ in range(n):
        c *= 1 + rng.gauss(0, sigma) + pull * (anchor / c - 1)
        out.append(c)
    return out


def dominant(results, lo, hi):
    """Most common confirmed state over a slice."""
    seg = [r["state"] for r in results[lo:hi]]
    return max(set(seg), key=seg.count) if seg else None


def pct(results, state, lo, hi):
    seg = [r["state"] for r in results[lo:hi]]
    return 100.0 * seg.count(state) / len(seg) if seg else 0.0


def flips(results, lo=0, hi=None):
    seg = [r["state"] for r in results[lo:hi if hi is not None else len(results)]]
    return sum(1 for a, b in zip(seg, seg[1:]) if a != b)


# --------------------------------------------------------------------------
def test_regimes():
    print("\n=== 1. Regime labelling (spec 6.1) ===")
    cases = [
        ("clean uptrend",   path_trend(400, +0.40, seed=11), UP),
        ("clean downtrend", path_trend(400, -0.40, seed=12), DOWN),
        ("quiet range",     path_range(400, seed=13),        SIDEWAYS),
    ]
    ok = True
    for name, closes, expect in cases:
        res = run(make_bars(closes), lookback=50)
        got = dominant(res, 120, len(res))
        share = pct(res, expect, 120, len(res))
        good = got == expect
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name:<16} dominant={STATE_NAMES[got]:<12} "
              f"{STATE_NAMES[expect]} for {share:.0f}% of bars")
    return ok


def test_reversal_shows_transition():
    print("\n=== 2. Reversal passes through Transition, not straight Up->Down ===")
    up = path_trend(300, +0.40, seed=21)
    down = path_trend(300, -0.40, start=up[-1], seed=22)
    res = run(make_bars(up + down), lookback=50)
    states = [r["state"] for r in res]
    # walk the handover window and look for a non-directional state between
    seg = states[280:420]
    saw_transition = TRANSITION in seg
    direct_flip = any(a == UP and b == DOWN for a, b in zip(states, states[1:]))
    good = saw_transition and not direct_flip
    print(f"  {'PASS' if good else 'FAIL'}  transition seen={saw_transition}  "
          f"direct Up->Down flip={direct_flip}")
    return good


def test_insufficient_first():
    print("\n=== 3. Cold start reports Insufficient, never a guess (spec 6.5) ===")
    res = run(make_bars(path_trend(120, +0.4, seed=31)), lookback=50)
    early = [r["state"] for r in res[:50]]
    good = all(s == INSUFFICIENT for s in early)
    print(f"  {'PASS' if good else 'FAIL'}  first 50 bars all Insufficient "
          f"(saw: {sorted({STATE_NAMES[s] for s in early})})")
    return good


def test_no_lookahead():
    print("\n=== 4. No lookahead: replay matches batch exactly (spec 6.5) ===")
    closes = path_trend(150, +0.3, seed=41)
    closes += path_range(150, seed=42, start=closes[-1])
    bars = make_bars(closes)
    batch = run(bars, lookback=50)

    mismatches = 0
    for t in range(60, len(bars), 7):  # sample; full sweep is O(n^2)
        prefix = run(bars[:t + 1], lookback=50)[-1]
        if prefix["state"] != batch[t]["state"] or prefix["raw"] != batch[t]["raw"]:
            mismatches += 1
    good = mismatches == 0
    print(f"  {'PASS' if good else 'FAIL'}  {mismatches} mismatch(es) across sampled bars")
    return good


def test_stability_and_sensitivity():
    print("\n=== 5. Label stability + parameter sensitivity (spec 6.2, 6.4) ===")
    # A deliberately awkward tape: weak trend inside noise.
    closes = path_range(250, seed=51)
    closes += path_trend(250, +0.22, start=closes[-1], seed=52)
    closes += path_range(250, seed=53, start=closes[-1])
    bars = make_bars(closes)

    print("\n  Hysteresis effect (lookback=50, threshold=1.5):")
    for h in (1, 2, 3, 5):
        res = run(bars, lookback=50, hysteresis=h)
        print(f"    H={h}: {flips(res):3d} state changes over {len(bars)} bars")

    print("\n  Min swing filter effect (hysteresis=2):")
    for m in (0.0, 0.5, 1.0):
        res = run(bars, lookback=50, hysteresis=2, min_swing_mult=m)
        print(f"    min_swing={m:.1f}xATR: {flips(res):3d} state changes")

    print("\n  Lookback x threshold grid (flips / %Up / %Sideways / %Transition):")
    print(f"    {'L':>4} {'thr':>5} {'flips':>6} {'%Up':>6} {'%Side':>7} {'%Trans':>7}")
    for L in (20, 50, 100):
        for thr in (1.0, 1.5, 2.5):
            res = run(bars, lookback=L, slope_threshold=thr, hysteresis=2)
            lo = L + 20
            print(f"    {L:>4} {thr:>5} {flips(res, lo):>6} "
                  f"{pct(res, UP, lo, len(res)):>6.0f} "
                  f"{pct(res, SIDEWAYS, lo, len(res)):>7.0f} "
                  f"{pct(res, TRANSITION, lo, len(res)):>7.0f}")
    return True


def main():
    random.seed(0)
    results = [
        test_regimes(),
        test_reversal_shows_transition(),
        test_insufficient_first(),
        test_no_lookahead(),
        test_stability_and_sensitivity(),
    ]
    print("\n" + "=" * 62)
    print("RESULT:", "all checks passed" if all(results) else "FAILURES PRESENT")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
