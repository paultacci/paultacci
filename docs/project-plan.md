# Project Plan — NQ Multi-Timeframe Trend Context Indicator

## Goal (the actual deliverable)

A single indicator you can add to a TradingView chart that gives you an
**at-a-glance visual read of market state per timeframe**: is this
**uptrend**, **downtrend**, or **sideways/mixed** — with an honest
**"not enough data yet"** state instead of a forced guess. It must be:

- **Standalone** — no dependency on any entry strategy or session/Globex logic.
- **Visual** — chart background/candles colored by state, plus a table showing
  every configured timeframe at once (e.g. "15m: Up · 1H: Up · 4H: Mixed · 1D: Up").
- **Explainable** — every state is backed by numbers you can see (strength
  score, which of the two direction checks disagreed, etc.), not a black box.
- **Usable today** — copy-paste into TradingView's Pine Editor, add to an NQ
  chart, done.

Platform decision (made by me, not yet confirmed by you): **TradingView /
Pine Script v6**. This is the assumption everything below is built on — flag
it now if you're actually trading off NinjaTrader, ThinkorSwim, or Sierra
Chart and I'll adapt.

## Outline

1. **Foundation** — build the core single-timeframe engine (already fully
   specified in `docs/multi-timeframe-market-context-indicator.md`): confirmed
   swing structure, volatility-normalized slope, efficiency-ratio strength,
   composite state with hysteresis.
2. **Multi-timeframe layer** — run that engine across your chart's timeframe
   plus up to 4 configurable higher timeframes, without repainting.
3. **Visual layer** — background/candle coloring + on-chart table + alerts.
4. **Validate** — compile-check in TradingView, sanity-check on a live NQ
   chart across a trending day and a choppy day, confirm historical replay
   matches what the indicator showed live.
5. **Tune** — adjust default parameters based on what you see on real NQ
   charts (this is the step that needs your eyes on a chart, not just code).
6. **Document & handoff** — a short usage guide: what each color/number means,
   how to retune it.

## Implementation plan

| Step | What | Output | Status |
|---|---|---|---|
| 1 | Core engine: pivot-based structure, correlation→t-stat slope, efficiency ratio, hysteresis state machine | Pine function `f_calc()` | Done (v1) |
| 2 | Multi-timeframe wiring via `request.security`, non-repainting via prior-closed-bar technique | Chart TF + 4 configurable HTFs | Done (v1) |
| 3 | Visuals: background color, optional candle color, on-chart table, color legend | Full indicator script | Done (v1) |
| 4 | Alerts on state change | `alertcondition` | Done (v1) |
| 5 | **You compile-check it in TradingView** — paste into Pine Editor, "Add to chart," report any errors | Confirmed working script on your chart | **Next — needs you** |
| 6 | Visual tuning pass — sit with it on a live/replay NQ chart, flag anything that looks wrong (too laggy, too flickery, wrong color reads as wrong trend) | Adjusted defaults | Pending step 5 |
| 7 | Parameter sensitivity spot-check (per spec §6.4) — try 2-3 alternate settings on a volatile day vs a quiet day | Tuned defaults documented | Pending |
| 8 | Usage guide finalized | `docs/pinescript-usage.md` | Pending |

Deliverable file: **`pinescript/nq_mtf_trend_context.pine`**.

## What I need from you at each checkpoint

- **Step 5 (now):** Paste the script into TradingView, add it to an NQ chart,
  tell me: did it compile clean? Does the table show up? Do colors look
  reasonable?
- **Step 6:** Watch it through one trending session and one choppy/rangebound
  session. Tell me what looked wrong (e.g. "flipped colors 5 times in an
  hour on the 5m" or "took forever to catch the reversal on the 1H").
- **Step 7:** Approve or reject proposed default changes based on step 6.
