# Checkpoint Tracker — NQ Multi-Timeframe Trend Indicator

Update this file as each step actually gets done — it's the single source of
truth for "is this getting done."

- Design spec: `docs/multi-timeframe-market-context-indicator.md`
- Goal & plan: `docs/project-plan.md`
- **Agent handoff / build plan: `BUILD_PLAN.md`**
- Indicator: `pinescript/nq_mtf_trend_context.pine`
- User guide: `docs/pinescript-usage.md`

## Status

| # | Step | Status | Date | Notes |
|---|---|---|---|---|
| 1 | Design spec (structure vs. slope, strength, states) | ✅ Done | 2026-09-20 | Revised in step 5 to split Sideways from Transition |
| 2 | Core Pine engine written | ✅ Done | 2026-09-20 | |
| 3 | Multi-timeframe wiring (non-repainting) | ✅ Done | 2026-09-20 | |
| 4 | Visuals (background/candle color, table, alerts) | ✅ Done | 2026-09-20 | |
| 5 | **Self-review pass of v1** | ✅ Done | 2026-09-20 | 8 findings, all fixed — see below |
| 6 | Build plan for coding agent | ✅ Done | 2026-09-20 | `BUILD_PLAN.md` |
| 7 | **Compile-check on TradingView** | ⬜ Not started | | **Blocking.** Never compiled — no TradingView access from the authoring environment. See BUILD_PLAN Part A |
| 8 | Verify non-repaint behavior | ⬜ Not started | | BUILD_PLAN B2 |
| 9 | Sanity-check states vs. price action | ⬜ Not started | | BUILD_PLAN B3 |
| 10 | Flip-rate measurement | ⬜ Not started | | BUILD_PLAN B4 |
| 11 | Parameter sensitivity spot-check | ⬜ Not started | | BUILD_PLAN B5 |
| 12 | Final doc sync | ⬜ Not started | | BUILD_PLAN B6 |

## Review findings from step 5 (v1 → v2)

| # | Finding | Severity | Fixed |
|---|---|---|---|
| 1 | No `Sideways` state existed — a quiet range and a trend rolling over both collapsed into "Mixed," losing the distinction the goal explicitly asks for | **Design miss vs. goal** | ✅ Split into Sideways (both measures agree "no direction") and Transition (measures conflict); `simpleMode` merges them for display |
| 2 | Table used `color.white` text on uncolored cells — invisible on a light chart theme | Visual bug | ✅ Uses theme-aware `chart.fg_color` |
| 3 | A timeframe *lower* than the chart's could be configured; `request.security` returns unusable values in that direction | Correctness | ✅ Lower timeframes detected and hidden |
| 4 | Spec's explainability requirement was unimplemented — t-stat, structure/slope direction, and raw state were computed then discarded | Spec gap | ✅ Returned and surfaced in per-cell tooltips |
| 5 | Spec's minimum swing filter (`k × ATR`, §9) was missing — it's the documented remedy for noisy-market flicker | Spec gap | ✅ Added as an input, default off |
| 6 | Spec's alignment summary (§7.2) was missing | Spec gap | ✅ Added "Align" row counting agreeing timeframes |
| 7 | Timeframes displayed as raw strings ("60", "240") | UX | ✅ Formatted as 1H / 4H / 1D |
| 8 | History operator `[1]` used on function-local variables — a fragile Pine pattern | Robustness | ✅ Replaced with explicit `var` carry-forward |
| 9 | `lookahead` left implicit on `request.security` | Clarity | ✅ Explicitly `barmerge.lookahead_off` |

## Known unverified risk

The v2 script has **never been compiled**. `BUILD_PLAN.md` Part A lists the
specific constructs most likely to fail, highest risk first (type-qualifier
propagation of `simple int` lengths through the user-defined function into
`ta.*` calls inside `request.security()`), each with a prescribed fallback.

## Open questions / decisions pending

- [ ] Confirm platform: TradingView/Pine Script assumed, not confirmed.
- [ ] Four visible states (default) vs. three via Simple mode — which default?
- [ ] Confirm default timeframe ladder (chart TF + 1H + 4H + 1D).
- [ ] Any default parameter changes arising from flip-rate/sensitivity work.
