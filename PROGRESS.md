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
| 7 | Python reference engine + validation harness | ✅ Done | 2026-09-20 | `reference/` — all 6 logic checks pass |
| 8 | Off-chart logic validation & sensitivity sweep | ✅ Done | 2026-09-20 | `docs/validation-report.md` — found and fixed the Sideways bug |
| 9 | Eliminate top compile risk | ✅ Done | 2026-09-20 | `f_calc()` now reads global inputs instead of taking length params |
| 10 | **Compile-check on TradingView** | ⬜ Not started | | **Blocking.** Never compiled — no TradingView access from the build environment. BUILD_PLAN Part A |
| 11 | Verify non-repaint behavior on chart | ⬜ Not started | | BUILD_PLAN B2 |
| 12 | Sanity-check states vs. real NQ price action | ⬜ Not started | | BUILD_PLAN B3 — logic is validated, tuning is not |
| 13 | Flip-rate measurement on real bars | ⬜ Not started | | BUILD_PLAN B4 |

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

## Review findings from step 8 (v2 → v3), found by the test harness

| # | Finding | Severity | Fixed |
|---|---|---|---|
| 10 | **Sideways was effectively unreachable** — a quiet range read as Sideways only 7% of bars and Transition 64%, because a t-stat over a noisy window is almost never "flat," so ranges resolved to "measures disagree." The efficiency ratio, the one measure that identifies chop, was displayed but never used in the decision | **Critical — defeated the stated goal** | ✅ Efficiency now decides whether a disagreement is chop or a real handover. Range: 7% → 71% Sideways, uptrend detection unchanged at 86% |
| 11 | Guidance claimed the min-swing filter was the first anti-flicker lever; measured impact is negligible (57 → 54 flips) | Wrong advice | ✅ Usage guide corrected — lookback is the real lever (87 → 47 flips) |
| 12 | Length parameters passed through a function boundary into `ta.atr()` etc. risked a `simple int` vs `series int` compile error inside `request.security()` | Top compile risk | ✅ `f_calc()` reads the global inputs directly |

## Known unverified risk

The script has **never been compiled** — TradingView is unreachable from the
build environment. `BUILD_PLAN.md` Part A lists the constructs most likely to
fail, each with a prescribed fallback. The highest-risk item (type-qualifier
propagation into `ta.*` calls inside `request.security()`) has since been
designed out rather than left to chance.

Separately: the engine's **logic** is now validated off-chart via
`reference/`, but its **tuning** is not. Synthetic data cannot tell you how
the defaults feel on a real 5m NQ chart at the open.

## Open questions / decisions pending

- [ ] Confirm platform: TradingView/Pine Script assumed, not confirmed.
- [ ] Four visible states (default) vs. three via Simple mode — which default?
- [ ] Confirm default timeframe ladder (chart TF + 1H + 4H + 1D).
- [ ] Any default parameter changes arising from flip-rate/sensitivity work.
