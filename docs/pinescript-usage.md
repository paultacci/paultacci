# Using the NQ Multi-Timeframe Trend Context indicator

## Add it to a chart

1. Open TradingView, open an NQ chart (e.g. `CME_MINI:NQ1!`).
2. Open **Pine Editor** (bottom panel), click **New**, delete the boilerplate.
3. Paste in the full contents of `pinescript/nq_mtf_trend_context.pine`.
4. Click **Add to Chart**.
5. If TradingView reports a compile error, send it to me exactly as shown —
   that's the first checkpoint in `PROGRESS.md` (step 5).

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
- **Table** (top-right by default): one row per configured timeframe —
  current chart timeframe, then up to 4 higher timeframes (defaults: 1H, 4H,
  1D, Weekly off by default). Each row shows the state and a strength label
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
| Regression/efficiency lookback | **The strongest lever on flicker.** Measured: 20 bars = 87 state changes, 50 = 54, 100 = 47 over the same tape. Higher = steadier but slower to react |
| Hysteresis | Real but uneven: 1 → 2 cut flips 66→57, 2 → 3 changed nothing, 5 cut them to 40. Use 2, or jump to 5 if it's still noisy |
| Range cutoff (efficiency) | How much "going nowhere" counts as Sideways rather than Transition when the two direction checks disagree. Raising it makes more chop read as Sideways |
| Slope significance (t-stat) | Higher = more conservative about declaring a trend; shifts bars from Up/Down into Sideways |
| Swing fractal bars | Higher = fewer false swings, more lag on Structure |
| Min swing size (x ATR) | Off by default, and **measured impact was negligible** (57 → 54 flips at 1.0×ATR). Try the lookback first |
| Wait for confirmed close | Off = higher timeframes update live intrabar (faster, can flicker); On = only shows a fully closed higher-timeframe bar (matches backtest exactly, one bar slower) |

Don't change these blind — tune them by watching real NQ price action per
`docs/project-plan.md` step 6/7, and update `PROGRESS.md` when you do.
