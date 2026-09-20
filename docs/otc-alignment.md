# Does our trend definition match OTC's?

**Short answer: it did not. The two disagreed on roughly one bar in three.**
The indicator now ships with OTC's rule as the default, with our enhanced
version available as a toggle.

## The OTC definition (source)

From the Online Trading Campus corpus on the shared drive — Bernd's supply &
demand course, lesson 10, *"How to Read Trend Direction with Supply &
Demand"* (`K9F3_v59xJM.md`, playlist item 10 of 23, published 2024-09-28),
which is step two of his three-step process (location → direction → action):

> Identify the six most recent pivots (three highs, three lows) from current
> price. Two consecutive higher highs / higher lows = uptrend. Two consecutive
> lower highs / lower lows = downtrend. **Anything else = sideways.**

Supporting details from the same lesson:

- The six-pivot count is deliberately arbitrary: *"whether you do eight or
  ten, it's just a rule, but for me the rule is six."*
- Pivots are marked with a **ZigZag on a percentage retrace** (e.g. 3%), and
  he coaches *"reduce the percentage so you get more of these clear pivot
  points."*
- Trend is assessed on the **same timeframe** as the location analysis —
  which matches our per-timeframe design exactly.
- His worked example (Swiss Franc weekly): *"we have a lower high and… a
  higher low… so we have a clear definition here of a weekly sideways trend."*
  A lower high with a higher low is sideways, not a trend.
- There is **no slope, regression, or momentum component**. Direction is
  structure, full stop.

## Where our original definition differed

| | OTC (Bernd) | Ours (before this review) |
|---|---|---|
| Pivots used | **6** — 3 highs, 3 lows | 4 — 2 highs, 2 lows |
| Comparisons required | 2 per side (H1>H2>H3) | 1 per side (H1>H2) |
| Pivot detection | ZigZag, **percentage** retrace | N-bar fractal, optional ×ATR filter (off) |
| Second direction measure | none | regression t-statistic |
| Residual case | **Sideways**, outright | routed through an efficiency gate |

## Measured disagreement on real bars

Running both definitions over the same real data:

| Dataset | Exact agreement | Agreement on direction only |
|---|---|---|
| Index futures 5-min | 59% | 71% |
| NVDA daily | 66% | 72% |
| BTC hourly | 66% | 75% |

The systematic difference is that **OTC is far more conservative about
calling a trend at all**:

| | Up | Down | Sideways | Transition |
|---|---|---|---|---|
| Ours (2-pivot + slope) | 21–22% | 11–13% | 52–59% | 6–13% |
| **OTC six-pivot** | **12–13%** | **6–11%** | **76–82%** | n/a |
| OTC six-pivot + our slope | 9–10% | 3–6% | 67–75% | 9–19% |

OTC calls the market sideways roughly **80% of the time**; our original rule
said ~55%. Put plainly: the old default would have told you "uptrend" about
twice as often as your mentors would. On a 30-minute chart the gap was
starkest — OTC 91% sideways versus ours 33%.

OTC's rule is also markedly steadier: ~1 state change per 23–26 bars versus
~14 for ours.

## What changed, and why

Defaults are now **OTC mode on, three pivots per side** — the rule as taught.
Two reasons beyond simply matching the class:

1. **It speaks the same language as your mentors.** An indicator that
   disagrees with your training a third of the time costs you more in
   second-guessing than it gains in sensitivity.
2. **It answers sooner on high timeframes**, which matters for the monthly
   and weekly rungs you require. Because it counts pivots rather than filling
   a regression window, it becomes decisive after ~27 monthly bars (~2.2
   years) instead of ~77 (~6.4 years):

   | Mode | Monthly row decisive after |
   |---|---|
   | Enhanced, lookback 75 | 77 bars (~6.4 years) |
   | Enhanced, lookback 30 | 32 bars (~2.7 years) |
   | **OTC mode** | **27 bars (~2.2 years)** |

The enhanced definition is still there — one toggle — and everything built
for it (the slope measure, the Transition state, the efficiency gate) remains
tested and available. Turning **OTC mode off** gives you the second opinion,
including a Transition state that flags a trend rolling over, which OTC's
rule has no concept of.

## Known gaps against OTC's method

Worth being explicit about what still does not match:

1. **Pivot detection differs.** OTC uses a ZigZag with a *percentage* retrace
   threshold; we use an N-bar fractal with an optional ×ATR minimum swing.
   These select different pivots on the same chart. The `Min swing size
   (x ATR)` input is the closest analog to "reduce the percentage," but it is
   not the same algorithm. If you want tighter alignment, this is the next
   thing to change.
2. **"Two consecutive higher lows/highs" is read as AND**, i.e. an uptrend
   needs both the highs and the lows rising. Bernd's sideways example (lower
   high + higher low) supports this reading, but the phrasing in the lesson
   summary is ambiguous and worth confirming against the video.
3. **Impulse vs. correction is not modelled.** OTC uses it to decide *where
   to enter* within a trend. This indicator deliberately stops at context and
   has no entry logic, so it is out of scope by design.
4. **"Anticipatory trend analysis"** — Bernd flags predicting the trend shift
   before it happens as a future topic. Our Transition state is arguably a
   crude version of it, but it is not the same thing and shouldn't be
   presented as such.
