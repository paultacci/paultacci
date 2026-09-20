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
  - Green = confirmed uptrend
  - Red = confirmed downtrend
  - Orange = mixed/transition (the two direction checks disagree)
  - Gray = insufficient data yet (not enough history/volatility to call it)
- **Table** (top-right by default): one row per configured timeframe —
  current chart timeframe, then up to 4 higher timeframes (defaults: 1H, 4H,
  1D, Weekly off by default). Each row shows the state and a strength label
  (Weak / Moderate / Strong), which tells you how clean the move is,
  independent of its direction.
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

If both agree → Up or Down. If they disagree, or either doesn't have enough
data yet → Mixed or Insufficient — the indicator will not force a directional
label just to look decisive. Full reasoning and the two candidate methods
compared are in `docs/multi-timeframe-market-context-indicator.md`.

## Key settings you'll likely tune

| Setting | What it trades off |
|---|---|
| Swing fractal bars | Higher = fewer false swings, more lag on Structure |
| Regression/efficiency lookback | Higher = smoother Slope reading, slower to react |
| Slope significance (t-stat) | Higher = fewer Mixed calls from Slope, more conservative |
| Hysteresis | Higher = fewer color flips, more lag on every state change |
| Wait for confirmed close | Off = higher timeframes update live intrabar (faster, can flicker); On = only shows a fully closed higher-timeframe bar (matches backtest exactly, one bar slower) |

Don't change these blind — tune them by watching real NQ price action per
`docs/project-plan.md` step 6/7, and update `PROGRESS.md` when you do.
