# Validation Report — off-chart logic testing

Produced by `reference/validate.py` against `reference/mtf_trend.py`, the
Python twin of the Pine engine. Reproduce with:

```
python3 reference/validate.py
```

## Why synthetic data

Live market data is unreachable from the build environment (the network
policy denies Yahoo Finance and Stooq), so these runs use a regime-switching
price simulator: trending segments with drift, mean-reverting segments
without, and plausible intrabar ranges.

**This validates logic, not tuning.** It proves the state machine labels a
known uptrend as Up and a known range as Sideways, and that nothing peeks at
future bars. It cannot tell you the right lookback for NQ at 9:45am — that
still requires real bars in TradingView.

## Results (all passing)

| Check | Spec ref | Result |
|---|---|---|
| Clean uptrend → Up | §6.1 | Up on 86% of bars |
| Clean downtrend → Down | §6.1 | Down on 72% of bars |
| Quiet range → Sideways | §6.1 | Sideways on 71% of bars |
| Reversal passes through Transition, never a direct Up→Down flip | §6.1 | Transition observed; zero direct flips |
| Cold start reports Insufficient rather than guessing | §6.5 | First 50 bars all Insufficient |
| No lookahead: bar-by-bar replay matches batch computation | §6.5 | 0 mismatches |

## The bug this harness found

Before the fix, a quiet range was labelled **Sideways 7% / Transition 64%** —
the state the indicator exists to show was effectively unreachable. Cause: the
composite required *both* measures to read flat, but a regression t-statistic
over a noisy 50-bar window rarely sits inside a ±1.5 band, so ranges resolved
to "measures disagree" = Transition. Meanwhile the efficiency ratio, the one
measure that actually identifies chop, was computed and displayed but never
consulted in the decision.

Fix: when the two direction measures disagree, efficiency decides whether that
disagreement is chop (Sideways) or a genuine regime handover (Transition).

| Range cutoff | Range: %Sideways | Range: %Transition | Uptrend: %Up |
|---|---|---|---|
| 0.00 (old) | 7 | 64 | 86 |
| 0.15 | 63 | 6 | 86 |
| 0.20 | 70 | 1 | 86 |
| **0.25 (chosen)** | **71** | **0** | **86** |
| 0.35 | 71 | 0 | 86 |
| 0.40 | 71 | 0 | 87 |

`0.25` sits at the knee: it makes Sideways reachable without pushing
Transition to zero on mixed tapes (still 4% there), so genuine reversals are
still flagged. Uptrend detection is untouched at every setting — the gate
filters chop without suppressing trends.

## Parameter sensitivity (§6.4)

Run over a deliberately awkward tape (range → weak trend → range, 750 bars).

| Lookback | Threshold | Flips | %Up | %Sideways | %Transition |
|---|---|---|---|---|---|
| 20 | 1.0 | 96 | 30 | 45 | 8 |
| 20 | 2.5 | 75 | 26 | 54 | 8 |
| 50 | 1.0 | 56 | 34 | 49 | 4 |
| **50** | **1.5** | **54** | **33** | **51** | **4** |
| 50 | 2.5 | 50 | 30 | 55 | 4 |
| 100 | 1.5 | 47 | 34 | 54 | 2 |
| 100 | 2.5 | 43 | 33 | 56 | 2 |

**Lookback dominates flip rate**; threshold mostly shifts bars between Up and
Sideways rather than changing stability much.

Hysteresis: `1 → 66 flips, 2 → 57, 3 → 57, 5 → 40`. Note 2 → 3 buys nothing;
the next real step is 5.

Minimum swing filter: `0.0 → 57, 0.5 → 55, 1.0 → 54`. **Negligible** — this
was expected to be the main anti-flicker lever and empirically is not. The
usage guide was corrected accordingly.

## Current defaults, and what still needs real data

Defaults (`lookback 50, threshold 1.5, hysteresis 2, range cutoff 0.25`) are
now evidence-backed rather than guessed, but on synthetic data. Open items
for real NQ bars:

- Absolute flip rate per session — synthetic tapes can't tell you whether 54
  flips per 750 bars feels right on a 5m NQ chart.
- Behavior across the overnight/RTH handover, where real volatility shifts
  sharply and synthetic data is stationary by construction.
- Fat tails and gaps: real NQ produces single-bar moves the simulator's
  Gaussian steps never generate.
