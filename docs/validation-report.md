# Validation Report

Two harnesses, both runnable without a chart:

```
python3 reference/validate.py        # synthetic regimes: is the logic right?
python3 reference/fetch_real_data.py # pull public OHLC datasets
python3 reference/validate_real.py   # real bars: how does it behave?
```

## Data used, and its limits

NQ intraday history is not freely downloadable, and this build environment's
network policy blocks the usual market-data hosts. Public OHLC datasets on
GitHub are reachable, so validation runs against four real series chosen for
structural coverage rather than for being NQ:

| Dataset | Bars | Why it's here |
|---|---|---|
| Index futures, 5-minute | 2,142 | Closest available NQ analog: an index future, intraday, real session gaps |
| Index futures, daily | 512 | Same instrument, slower timeframe |
| NVDA daily 1999–2014 | 4,012 | Real crashes and manias; single-name equity with overnight gaps |
| BTC hourly | 11,561 | 24/7 market with no session breaks — tests the spec §9 cross-market claims |

**This is not NQ.** It establishes that the engine behaves sensibly across
market types and timeframes; it does not establish the right settings for NQ
at the cash open. That still needs real NQ bars in TradingView.

## Behavior on real bars (at current defaults)

| Dataset | Up | Down | Sideways | Transition | Stability |
|---|---|---|---|---|---|
| Index futures 5-min | 22% | 13% | 52% | 13% | 1 change per 14 bars |
| Index futures daily | 34% | 3% | 54% | 9% | 1 per 14 |
| NVDA daily | 21% | 13% | 59% | 6% | 1 per 16 |
| BTC hourly | 22% | 11% | 58% | 9% | 1 per 14 |

Markets read as directionless roughly half the time and trending the rest,
consistently across instrument types — which matches how markets actually
behave, and is the sanity check that matters most here.

**Zero direct Up↔Down flips on every dataset.** The indicator never jumps
between opposite trends without a neutral state in between. Of that neutral
time, 81–90% is Sideways and 10–19% Transition.

## Confirmation delay (spec §6.3)

Measured against ex-post turning points from a large-threshold zigzag used
purely as a grading key (it looks ahead by construction, which is exactly why
it never appears in the engine).

| Dataset | Median delay | p90 |
|---|---|---|
| Index futures 5-min | 28 bars | 50 |
| Index futures daily | 14 bars | 23 |
| NVDA daily | 15 bars | 33 |
| BTC hourly | 18 bars | 44 |

The engine also never catches roughly a quarter to a third of the smaller
legs at all. That is by design, not a defect: it is a context indicator with
a confirmation requirement, so it deliberately sits in Sideways through minor
swings rather than calling each one a trend. If you need every swing, this is
the wrong tool.

## The bug the harness found: Sideways was unreachable

Before the fix, the composite required *both* measures to read flat, but a
regression t-statistic over a noisy window rarely is — so ranges resolved to
"measures disagree" = Transition. The efficiency ratio, the one measure that
identifies chop, was computed and displayed but never consulted.

Fix: when the measures disagree, efficiency decides whether that is chop
(Sideways) or a genuine handover (Transition).

Measured on the real 5-minute index futures set:

| Range cutoff | %Sideways | %Transition | %Up | %Down |
|---|---|---|---|---|
| 0.00 (old behavior) | **3** | **61** | 22 | 13 |
| 0.15 | 38 | 26 | 23 | 13 |
| **0.25 (chosen)** | **48** | **16** | 22 | 13 |
| 0.35 | 58 | 6 | 22 | 13 |
| 0.50 | 64 | 1 | 22 | 13 |

Real data showed the bug to be worse than synthetic did (3% vs 7% Sideways).
Note Up and Down are **identical at every cutoff** — the gate provably filters
chop without touching trend detection. `0.25` keeps Transition alive at 16%;
by `0.50` it is nearly gone, which would just swap one unreachable state for
another. `reference/validate.py` now has an anti-regression test for exactly
that.

## Default selection (spec §6.4)

Defaults were changed from `L=50, H=2` to **`L=75, threshold=1.5, H=3`**,
averaged across all four datasets:

| Setting | Bars per flip (higher = steadier) | Median delay (lower = faster) |
|---|---|---|
| L=50, H=2 (previous default) | 11.1 | 18.8 |
| L=50, H=5 | 18.2 | 20.1 |
| L=100, H=2 | 13.7 | 15.6 |
| **L=75, H=3 (new default)** | **14.5** | **14.4** |
| L=100, H=5 | 21.6 | 19.4 |
| L=100, thr=2.5, H=5 | 22.3 | 24.8 |

`L=75, H=3` **strictly dominates the previous default on both axes** — 31%
steadier *and* 23% faster to confirm. That is not a tradeoff, so it was taken.

If you want maximum steadiness and will accept slower confirmation, **L=100,
H=5** is the other defensible point on the frontier (21.6 bars per flip).

### A caution worth recording

On the 5-minute futures set *alone*, `L=100/H=5` looked best. Across all four
datasets, `L=75/H=3` won. Optimizing on one tape would have picked the wrong
answer — which is precisely the overfitting spec §6.4 warns about. Any future
retuning should clear the same multi-dataset bar.

## Other findings

- **Min swing filter is not the anti-flicker lever.** Measured impact was
  negligible (57 → 54 flips). Lookback dominates. Earlier guidance said the
  opposite and was corrected.
- **Hysteresis is uneven**: 1→2 helps, 2→3 helped little on synthetic but
  contributed on real data, 5 is the next real step.
- **Real feeds contain garbage.** The BTC set uses `1.7e308` as a
  missing-data sentinel in 1,454 rows and crashed the engine with an
  `OverflowError`. The engine now carries the last good bar forward on any
  non-finite or non-positive print — the same situation as a halt, which spec
  §9 requires handling.

## Pine script static checks

The `.pine` file has still never been run by TradingView, but it now passes
two static checks via the `pynescript` parser:

- **Parses cleanly** as both v5 and v6 (2,881 AST nodes, no syntax errors),
  which rules out the indentation, paren and line-continuation errors that
  most often bite when writing Pine without a compiler.
- **Every built-in it calls exists**: `ta.atr`, `ta.change`, `ta.correlation`,
  `ta.pivothigh`, `ta.pivotlow`, `math.abs/sqrt/sum`, `str.tostring`,
  `table.new/cell`, `request.security`, `timeframe.in_seconds`, the `input.*`
  family, `alertcondition`, `bgcolor`, `barcolor`, `color.new`, `na`.

What static parsing still cannot confirm: type-qualifier rules
(`simple` vs `series`), `request.*` call budget, and runtime behavior. Those
need the real compiler.
