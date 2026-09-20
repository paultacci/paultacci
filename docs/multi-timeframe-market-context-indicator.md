# Multi-Timeframe Market-Context Indicator — Specification

## 1. Purpose and scope

This document specifies a **standalone market-context indicator**: a read-only
description of "what kind of market this is right now," computed independently
per timeframe. It answers *"is this instrument trending up, trending down,
mixed/transitioning, or not yet knowable, and how strongly?"* — nothing more.

Explicit non-goals:

- **No entry/exit logic.** The indicator never emits buy/sell/flatten signals.
  It is a context layer that any strategy (or a human) can consult; it must not
  assume, reference, or depend on a particular strategy's rules.
- **No session dependency.** The indicator does not anchor to CME Globex
  session boundaries (17:00–16:00 CT), RTH windows, or any exchange-specific
  session calendar. Bars are plain time-based OHLC bars in a configured
  timezone (UTC by default); session-aware bucketing, if ever wanted, is a
  separate, optional feature layered on top — never a hidden assumption inside
  this indicator.
- **No single "trend score."** Direction and strength are reported as two
  separate axes, and both track a state machine that can rest in "mixed" or
  "insufficient data" — the design deliberately resists collapsing everything
  into one number that always outputs a confident up/down.

## 2. High-level design

For each configured timeframe, the indicator maintains three independent
signals, computed only from closed bars (no lookahead):

| Signal | Question it answers | Basis |
|---|---|---|
| **Structure direction** | What has price *confirmed* it's doing? | Sequence of confirmed swing highs/lows (HH/HL vs LH/LL) |
| **Slope direction** | What is the *current* volatility-adjusted drift? | Regression slope of price over a lookback, normalized by volatility |
| **Trend strength** | How *strong/clean* is the move, independent of its direction? | Move efficiency / directional consistency (not derived from either direction signal's sign) |

These three feed a small state machine that classifies each timeframe into one
of four states — **Up**, **Down**, **Mixed/Transition**, **Insufficient Data**
— and every field that produced the classification is retained for output, so
the label is always explainable, never a black box.

## 3. Direction measure 1: confirmed price structure

### 3.1 Definition

Use fractal-style swing detection: a bar `i` is a **swing high** if its high is
the maximum among the `N` bars before and `N` bars after it (symmetric
fractal, `N` configurable, default `N=2`). A swing low is defined
symmetrically on lows. A swing is **confirmed** only once the `N` bars *after*
it have closed — this is the source of its inherent lag (see §6.1).

Structure direction from the last two confirmed swing highs (`SH1` newer,
`SH2` older) and last two confirmed swing lows (`SL1` newer, `SL2` older):

| Pattern | Label |
|---|---|
| `SH1 > SH2` and `SL1 > SL2` | Higher-high / higher-low → **Up** |
| `SH1 < SH2` and `SL1 < SL2` | Lower-high / lower-low → **Down** |
| Any other combination (e.g. `HH` + `LL`, or `LH` + `HL`) | **Mixed** (expansion or contraction — structure disagrees with itself) |
| Fewer than 2 confirmed swing highs *and* 2 confirmed swing lows exist yet | **Insufficient data** |

### 3.2 Properties

- **Repaint risk:** none, *if and only if* a swing is only ever reported after
  its `N`-bar confirmation window has fully elapsed. A common implementation
  bug is to plot the swing at bar `i` immediately (visually "in the past") —
  this looks clean on a historical chart but is unavailable at that time live.
  The spec requires confirmed-swing timestamps and confirmation timestamps to
  both be recorded and exposed (see §5).
- **Lag:** fixed, `N` bars per swing, plus however many bars until the *next*
  opposing swing forms and confirms. This is a real, structural delay — it
  cannot be tuned away, only traded off against noise (larger `N` = fewer
  false swings, more lag).
- **Noise sensitivity:** low. Because it requires actual higher/lower
  extremes, it does not react to small intrabar wiggles the way a slope
  measure can.

## 4. Direction measure 2: volatility-normalized slope

### 4.1 Definition

Over a lookback window of `L` closed bars, fit an ordinary least-squares
regression of price (or log-price — see §8) against bar index. Take the
slope's **t-statistic**: `t = slope / standard_error(slope)`. This is
equivalent to normalizing the raw slope by the noise in the fit, which is the
volatility-normalization step (it plays the same role as dividing raw slope by
ATR, but also accounts for how well the data fits a line, not just how
choppy it is).

- `t > +threshold` → **Up**
- `t < -threshold` → **Down**
- `-threshold ≤ t ≤ +threshold` → **Mixed** (statistically indistinguishable
  from flat)
- Fewer than `L` bars of history exist yet → **Insufficient data**

`threshold` is a configurable parameter (a reasonable default is `1.5`–`2.0`,
i.e. roughly a 90–95% one-sided confidence band that the slope is non-zero).

### 4.2 Properties

- **Repaint risk:** none — every input (`L` closed bars) is fixed once each
  bar closes and never revised, provided the regression window is trailing
  (never centered/symmetric, which would use future bars).
- **Lag:** shorter than structure-based lag in typical use; reacts within a
  fraction of `L` bars of an actual regime change, at the cost of more
  whipsaw near the threshold boundary.
- **Noise sensitivity:** higher than structure. A single volatile bar can
  swing `t` across the threshold and back, which is why label stability
  (§6.2) matters more here than for the structure measure.
- **Degenerate case:** near-zero-volatility instruments/periods can produce a
  standard error near zero and an unstable/huge `t`. Guard by falling back to
  **Insufficient data** whenever the fit's standard error is below a small
  epsilon relative to price, or the sample variance of price is ~0 (e.g. a
  halted or extremely thin market).

### 4.3 Structure vs. slope — comparison

| Property | Confirmed structure | Vol-normalized slope |
|---|---|---|
| Repaint risk (if implemented correctly) | None | None |
| Typical confirmation lag | High, discrete (multiples of `N`) | Lower, continuous |
| Noise sensitivity | Low | Moderate–high |
| Interpretability | Very high ("price made a higher low") | Moderate (needs the regression explained) |
| Failure mode | Mislabels ranges as trends late | Whipsaws near threshold in choppy markets |
| Degenerate inputs | None (ordinal comparison only) | Needs epsilon-guard for near-zero volatility |

The two are reported side by side rather than merged into one number — this
is the point of comparing them. Agreement between the two is itself a useful,
explainable signal (see §5).

## 5. Trend strength (kept separate from direction)

Strength must **not** be derived from the same statistic as either direction
measure's sign, or "strength" silently becomes a restatement of "direction"
and the two axes stop being independent. Recommended measure: **Kaufman's
Efficiency Ratio (ER)** over the same lookback `L` used for slope:

```
ER = |price[t] - price[t-L]| / sum(|price[i] - price[i-1]| for i in t-L+1..t)
```

`ER` ranges 0 (pure noise / round-trip chop — total path length far exceeds
net displacement) to 1 (a perfectly straight, efficient move). It says nothing
about *which* direction the move was in — only how clean it was — which is
exactly the separation the spec calls for. Bucket it for reporting, e.g.
`weak (<0.3)`, `moderate (0.3–0.6)`, `strong (>0.6)`, with the raw value also
exposed for downstream tuning.

An acceptable alternative/cross-check is ADX (strength only, ignoring
`+DI`/`-DI`) or the inverse of the Choppiness Index; ER is preferred here
because it is simple, bounded, and cheaply explainable ("price covered X% of
its total travel distance in a straight line").

## 6. State machine and evaluation criteria

### 6.1 Composite state

Per timeframe, combine structure direction, slope direction, and ER. Note
that the non-directional case splits into **two distinct states** — this is a
deliberate revision to the original four-state design, because "the market is
quiet and going nowhere" and "the two measures are actively fighting each
other" are different conditions that call for different responses, and
collapsing them into one "Mixed" bucket destroys that information:

| Structure | Slope | Resulting state |
|---|---|---|
| Up | Up | **Up**, strength = ER bucket |
| Down | Down | **Down**, strength = ER bucket |
| No clear sequence | Statistically flat | **Sideways/Range** — both measures independently say "no direction" |
| Up | Down (or vice versa) | **Transition** — measures directly conflict |
| Up or Down | Flat | **Transition** — structure still claims a trend the slope no longer supports |
| No clear sequence | Up or Down | **Transition** — drift without confirming structure |
| Insufficient (either) | anything | **Insufficient data** |

Sideways is the *agreement* case for "no trend"; Transition is the
*disagreement* case. Disagreement is treated as information, not noise to be
argued away — it usually means a trend is aging or a reversal may be forming,
which is exactly when a "confident" single-number indicator is most
misleading. A consumer that genuinely only wants three buckets can merge
Transition into Sideways at the display layer, but the engine must not
discard the distinction upstream.

### 6.2 Label stability (avoiding flapping)

Raw state, recomputed every bar, will flap near boundaries (a `t`-stat
hovering at the threshold, a swing barely edging past its predecessor).
Require **hysteresis**: a state change only takes effect after it has held for
`H` consecutive bars (default `H=2`), and report both the *raw* instantaneous
state and the *confirmed/debounced* state, so downstream consumers can pick
their own risk tolerance for lag vs. responsiveness. Track and report, per
timeframe:

- flips per N bars (of the confirmed state),
- average dwell time in each state,
- fraction of bars spent in Mixed/Insufficient vs. directional states.

A well-tuned instance should show materially fewer flips than the raw,
un-debounced state while adding only `H` bars of extra lag — measure this
trade-off explicitly rather than assuming it.

### 6.3 Confirmation delay

Define delay empirically per transition: using a large-threshold, offline-only
zigzag as an ex-post "ground truth" turning point locator (never used live —
it is only for backtesting evaluation, since it inherently repaints), measure
bars from the ground-truth turn to the indicator's confirmed state flip.
Report the distribution (median, 90th percentile), not just an average,
separately for the structure measure, the slope measure, and the debounced
composite — because their delay characteristics differ by design (§4.3).

### 6.4 Parameter sensitivity

Sweep the core parameters independently and report how much the *confirmed*
state timeline changes, not just single-point performance:

- fractal `N` ∈ {2, 3, 5}
- regression lookback `L` ∈ {20, 50, 100}
- slope threshold ∈ {1.0, 1.5, 2.0, 2.5}
- hysteresis `H` ∈ {1, 2, 3}

For each combination, compute flip rate and confirmation delay (§6.2–6.3)
across multiple historical regimes (trending, ranging, high- and
low-volatility periods). Plot delay vs. flip-rate as a Pareto frontier per
parameter; pick defaults from the knee of that curve rather than from a single
best-backtest run, to avoid overfitting the defaults to one regime.

### 6.5 Historical vs. live consistency

This is the most common place these indicators quietly break:

1. **No centered windows.** Every filter (regression, ATR/vol estimate,
   fractal check) must be strictly trailing/causal. A centered moving average
   or a fractal that only requires `N` bars *before* the point (not after) is
   a repaint bug in disguise.
2. **Bar-by-bar replay test.** Compute the indicator two ways on the same
   historical data: (a) vectorized, full history at once, and (b) an
   event-driven simulation that only ever sees bars up to and including the
   "current" one, appended one at a time. The two must produce **bit-identical**
   confirmed-state timelines. Any divergence indicates a lookahead leak.
3. **Confirmed vs. raw separation in storage.** Persist both the raw
   (pre-hysteresis) and confirmed state with the bar index/timestamp at which
   each was *knowable*, not just the bar it describes — this is what makes a
   later live/historical diff possible at all.
4. **Live warm-up.** On a freshly started live instance, the first `max(L, N
   confirmation window)` bars must report **Insufficient data**, matching
   exactly what a historical run would show at the same relative position
   from an instrument's/timeframe's start — never silently backfill using data
   the live process didn't have.

## 7. Multi-timeframe configuration and aggregation

### 7.1 Configurable timeframes

Timeframes are a user-supplied ordered list (e.g. `5m, 15m, 1h, 4h, 1D`), each
independently configured with its own `N`, `L`, threshold, and `H` if desired
(sane defaults scale a base configuration by the timeframe's relative bar
count — see §8). Prefer timeframes that nest cleanly (each an integer multiple
of the previous) so that higher-timeframe bars close on lower-timeframe
boundaries; this is a recommendation for reporting clarity, not a hard
requirement, since each timeframe's state machine runs independently either
way.

### 7.2 Aggregate view

Do not compress the multi-timeframe view into a single number. Report:

- each timeframe's full state record (§7.3), and
- a simple **alignment summary**: how many/which timeframes agree on
  direction, and whether agreement is monotonic across the timeframe ladder
  (e.g. all of `1h/4h/1D` agree Up while `5m` is Mixed → "higher-timeframe
  uptrend, lower-timeframe pullback" is a derivable, explainable statement,
  not a hidden score).

### 7.3 Explainable output schema

Every timeframe emits a self-contained record; nothing about the label should
require re-deriving it from raw bars to explain:

```json
{
  "symbol": "NQ",
  "timeframe": "1h",
  "as_of_bar_close": "2026-09-19T14:00:00Z",
  "state": {
    "raw": "up",
    "confirmed": "up",
    "confirmed_since": "2026-09-19T09:00:00Z",
    "bars_in_state": 5
  },
  "structure": {
    "direction": "up",
    "last_swing_high": {"price": 19850.25, "bar_time": "2026-09-18T20:00:00Z", "confirmed_at": "2026-09-18T22:00:00Z"},
    "prior_swing_high": {"price": 19790.00, "bar_time": "2026-09-17T15:00:00Z"},
    "last_swing_low": {"price": 19710.50, "bar_time": "2026-09-19T02:00:00Z", "confirmed_at": "2026-09-19T04:00:00Z"},
    "prior_swing_low": {"price": 19640.75, "bar_time": "2026-09-16T11:00:00Z"},
    "fractal_n": 2,
    "insufficient_data": false
  },
  "slope": {
    "direction": "up",
    "t_stat": 2.31,
    "threshold": 1.5,
    "lookback_bars": 50,
    "insufficient_data": false
  },
  "strength": {
    "efficiency_ratio": 0.42,
    "bucket": "moderate"
  },
  "agreement": {
    "structure_vs_slope": "agree",
  },
  "params_hash": "sha256:…"
}
```

`params_hash` lets any consumer verify which parameter set produced a given
historical record — required for the sensitivity analysis in §6.4 to be
auditable after the fact.

## 8. NQ (Nasdaq-100 e-mini) as first implementation

Reference defaults, to be validated (not assumed) via the sensitivity sweep
in §6.4:

| Parameter | Default | Rationale |
|---|---|---|
| Timeframes | `5m, 15m, 1h, 4h, 1D` | Common discretionary/algorithmic ladder; each a clean multiple of the last except 1D |
| Fractal `N` | 2–3 | NQ's intraday noise needs at least 2 confirming bars per side to avoid noise swings |
| Regression input | **log price**, not raw price | NQ's price level has drifted from ~7,000 to ~20,000+ over recent years; log returns keep the regression's slope/threshold meaningfully comparable across time and price regimes |
| Lookback `L` | 50 bars per timeframe | Roughly 4 hours on the 5m chart, ~2 days on the 1h chart — long enough to smooth single-bar noise, short enough to react within a session |
| Slope threshold (t-stat) | 1.5 | Starting point; tune per §6.4 |
| Hysteresis `H` | 2 bars | Cuts flapping without adding a full extra bar of lag on top of confirmation delay |
| Volatility/epsilon guard | ATR(14) trailing, used only to flag "near-zero volatility" edge cases (e.g. extended halts) | NQ rarely truly flatlines, but the guard should exist for illiquid pre-market/holiday-adjacent bars |

Bars are plain UTC time-based candles — no CME session boundary (17:00 CT
open) is used to reset any window, per the "independent of Globex" scoping in
§1. Overnight gaps (e.g. across the CME daily maintenance break, or weekend
close) are absorbed naturally by the log-return-based regression rather than
treated as a special case.

## 9. Adaptations required for other markets

The mechanics (fractal swings, regression t-stat, ER) are market-agnostic,
but several **NQ-specific assumptions must be revisited** before reuse:

| Assumption made for NQ | Why it may not hold elsewhere | Adaptation needed |
|---|---|---|
| Continuous, near-24h trading with only brief daily maintenance breaks | Equities (single-name stocks) trade ~6.5h/day with an overnight gap every day; FX/crypto trade continuously with no scheduled break at all | For single-name equities, gaps are the norm, not the exception — log-return regression handles the *math*, but "insufficient data" and confirmation-delay evaluation should exclude/flag overnight and weekend gaps explicitly rather than counting them as ordinary bars. For 24/7 crypto, there is no maintenance-break analog to worry about at all. |
| Consistently high, roughly stationary volatility regime | Low-volatility instruments (major FX pairs in quiet ranges, short-dated rates) can have long stretches near-zero price movement | The near-zero-volatility epsilon guard (§4.2) becomes load-bearing, not an edge case — expect it to trigger routinely, and tune ATR-relative thresholds per instrument rather than reusing NQ's. |
| Log-price regression appropriate because of large multi-year price-level drift | Instruments with a bounded or mean-reverting price level (interest-rate futures, some FX pairs, spreads) may not benefit from log transform, or may need the regression run on the spread/level directly | Decide log vs. raw per instrument class; for spread/relative-value instruments (e.g. calendar spreads), the price series can cross zero, where log-price is undefined and raw-price (or a different normalization) must be used. |
| Fractal `N=2–3` filters noise appropriately | Thinner, noisier, or more gap-prone markets (small/mid-cap equities, illiquid futures) can produce spurious fractals from single erratic prints | Scale swing significance by a minimum-move filter (e.g. require the swing to exceed `k × ATR`, not just be a local extreme) rather than relying on `N` alone — needed for any market where an outlier print is more common than in NQ. |
| Trading halts are rare/short | Single-name equities can halt for news/circuit breakers for extended periods; some markets have daily limit-up/limit-down closures | Treat a halt as an explicit "insufficient data" condition (no synthetic bars), and ensure the live warm-up logic (§6.5.4) re-applies correctly after a halt resumes, the same way it does after a cold start. |
| One exchange, one continuous futures-style time series | Instruments that roll (futures contracts other than a continuous/back-adjusted series) introduce artificial price jumps at roll dates | Either always operate on a back-adjusted continuous series, or explicitly exclude the roll bar from both the swing and regression inputs so it isn't mistaken for a genuine directional move. |
| Timeframe ladder `5m…1D` matches typical NQ intraday holding horizons | A slower-moving asset class (e.g. long-only equity portfolios, macro rates) may only care about `1D, 1W, 1M` | Timeframe set and per-timeframe lookback/threshold defaults should scale to the asset's natural holding-period distribution, not be copied verbatim from an intraday futures configuration. |

## 10. Summary of guarantees this design provides

- **Independence:** no reference to any session calendar or entry/exit
  strategy anywhere in the computation.
- **Two distinct, comparable direction measures**, reported side by side with
  their agreement/disagreement exposed rather than merged.
- **Strength reported on its own axis**, computed so it cannot silently
  collapse into a restatement of direction.
- **Mixed/Transition and Insufficient Data are first-class states**, not
  fallbacks papered over by forcing a directional label.
- **Every output is explainable**: the record that produces a label carries
  the exact swing points, t-stat, ER, and parameter hash that produced it.
- **Confirmation delay, label stability, parameter sensitivity, and
  historical/live consistency are evaluation criteria with concrete
  measurement procedures** (§6), not just design aspirations.
