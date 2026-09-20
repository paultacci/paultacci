# Using the NQ Multi-Timeframe Trend Context indicator

## Add it to a chart

1. Open TradingView, open an NQ chart (e.g. `CME_MINI:NQ1!`).
2. Open **Pine Editor** (bottom panel), click **New**, delete the boilerplate.
3. Paste in the full contents of `pinescript/nq_mtf_trend_context.pine`.
4. Click **Add to Chart**.
5. If TradingView reports a compile error, send it to me exactly as shown —
   that's the first checkpoint in `PROGRESS.md` (step 5).

## Which trend definition is it using?

By default, **OTC mode is on**: direction comes from the six-pivot rule taught
in Bernd's supply & demand course (three highs, three lows; two consecutive
higher highs AND higher lows = uptrend; anything else = sideways). This is
deliberate so the indicator agrees with your class rather than contradicting
it — see `docs/otc-alignment.md` for the measured comparison.

Turn **OTC mode off** for the enhanced definition: structure must also agree
with a volatility-normalized slope, and when they disagree you get a
**Transition** state flagging a trend rolling over — something the OTC rule
has no concept of. It calls trends about twice as often.

## Reading it

- **Chart background/candles** (if enabled): colored by the state of the
  timeframe you're currently viewing.
  - Green = confirmed **uptrend**
  - Red = confirmed **downtrend**
  - Blue = **sideways/range** — both direction checks independently say
    there's no direction. This is the quiet, going-nowhere market.
  - Orange = **transition** — the two direction checks disagree. Usually a
    trend aging out or a reversal forming. Different from sideways on
    purpose: sideways is "nothing happening," transition is "something is
    changing."
  - Gray = **insufficient data** (not enough history/volatility to call it)
- **Table** (top-right by default): one row per enabled timeframe. The full
  ladder is 5m, 15m, 30m, 1H, 90m, 4H, 6H, 1D, 2D, 1W, 1M; enabled by default
  are 30m, 1H, 90m, 4H, 6H, 1D, 1W, 1M (5m, 15m and 2D are off to keep the
  table readable — turn them on in settings). Rows below your chart's own
  timeframe are hidden automatically, because a lower timeframe pulled into a
  higher-timeframe chart returns values this engine can't stand behind. Each row shows the state and a strength label
  (Weak / Moderate / Strong), which tells you how clean the move is,
  independent of its direction. The bottom **Align** row counts how many
  displayed timeframes agree — all-up or all-down means the whole ladder is
  lined up.
- **Hover any table cell** for the numbers behind the label: the raw state
  before hysteresis (shows you a flip is pending), what structure says, the
  slope t-stat, and the efficiency ratio. Nothing is hidden.
- If you only ever want three buckets, turn on **Simple mode**, which merges
  Transition into Sideways for display.
- **Alert**: fires whenever the chart-timeframe state changes (Up→Down,
  Up→Mixed, etc.) — set it up via TradingView's alert dialog on this
  indicator if you want a notification instead of watching the chart.

## What's actually driving the color, in plain terms

Each timeframe's state comes from two independent checks that both have to
agree before it calls something a trend:

1. **Structure** — has price actually made a higher high + higher low (or
   lower high + lower low)? This only updates once a swing is confirmed, so
   it's slower but very literal.
2. **Slope** — is the recent price drift statistically real relative to how
   noisy the market's been (not just "it went up a little")? This reacts
   faster but can wobble more.

If both agree on a direction → Up or Down. If both independently say "no
direction" → Sideways. If they disagree → Transition. If either doesn't have
enough data → Insufficient. The indicator will not force a directional label
just to look decisive. Full reasoning and the two candidate methods compared
are in `docs/multi-timeframe-market-context-indicator.md`.

## Key settings you'll likely tune

| Setting | What it trades off |
|---|---|
| Regression/efficiency lookback | **The strongest lever on flicker.** Default 75. Lower = faster but noisier; higher = steadier but slower |
| Hysteresis | Default 3. Raise to 5 if you want noticeably fewer colour changes and will accept slower confirmation |
| Range cutoff (efficiency) | How much "going nowhere" counts as Sideways rather than Transition when the two direction checks disagree. Raising it makes more chop read as Sideways |
| Slope significance (t-stat) | Higher = more conservative about declaring a trend; shifts bars from Up/Down into Sideways |
| Swing fractal bars | Higher = fewer false swings, more lag on Structure |
| Min swing size (x ATR) | Off by default, and **measured impact was negligible** (57 → 54 flips at 1.0×ATR). Try the lookback first |
| Wait for confirmed close | Off = higher timeframes update live intrabar (faster, can flicker); On = only shows a fully closed higher-timeframe bar (matches backtest exactly, one bar slower) |

### Two validated presets

| | Lookback | Threshold | Hysteresis | Character |
|---|---|---|---|---|
| **Balanced (default)** | 75 | 1.5 | 3 | ~1 colour change per 14-16 bars, median ~14 bars to confirm a real turn |
| **Steady** | 100 | 1.5 | 5 | ~1 change per 22 bars, slower to confirm — fewer distractions |

Both were picked by measuring across four real datasets (index futures 5-min
and daily, NVDA daily, BTC hourly) rather than tuned to one chart. See
`docs/validation-report.md` for the numbers.

### If the monthly or weekly row says "Insufficient"

That's the honest answer, not a bug: a timeframe can't report until it has
enough of its own bars. In OTC mode the monthly row needs ~27 monthly bars
(~2.2 years); with OTC mode off and lookback 75, it needs ~77 (~6.4 years).
If it won't populate, either leave OTC mode on or lower the lookback.

Don't change these blind — tune them by watching real NQ price action per
`docs/project-plan.md`, and update `PROGRESS.md` when you do.
