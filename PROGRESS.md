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
| 10 | Real-market-data validation (4 datasets) | ✅ Done | 2026-09-20 | `reference/validate_real.py` — index futures 5m/daily, NVDA daily, BTC hourly |
| 11 | Confirmation-delay measurement (spec §6.3) | ✅ Done | 2026-09-20 | Median 14–28 bars depending on timeframe |
| 12 | Evidence-based default selection | ✅ Done | 2026-09-20 | L=50/H=2 → **L=75/H=3**, dominant on both axes across all 4 datasets |
| 13 | Pine static analysis (parse + built-in check) | ✅ Done | 2026-09-20 | Parses clean, 2,881 nodes; every built-in verified real |
| 14 | **Compile-check on TradingView** | ⬜ Not started | | **Blocking.** Syntax is now statically verified; type-qualifier and runtime behavior still need the real compiler |
| 15 | Verify non-repaint behavior on chart | ⬜ Not started | | BUILD_PLAN B2 |
| 16 | Confirm settings feel right on real NQ | ⬜ Not started | | Defaults are evidence-based but not NQ-specific |
| 17 | Validate trend definition vs. OTC corpus | ✅ Done | 2026-09-20 | `docs/otc-alignment.md` — they disagreed on ~1 bar in 3; OTC's rule is now the default |
| 18 | Expand to the full 11-timeframe ladder | ✅ Done | 2026-09-20 | 5m→1M, all required rungs present; outputs packed to stay within Pine's request budget |
| 19 | Validate the ladder on resampled real data | ✅ Done | 2026-09-20 | `reference/validate_mtf.py` |

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

## Findings from step 10-13 (real data + static analysis)

| # | Finding | Severity | Resolution |
|---|---|---|---|
| 13 | On **real** bars the Sideways bug was worse than synthetic showed: 3% Sideways / 61% Transition without the efficiency gate | Confirms #10 | ✅ Gate validated on real data: 48% / 16%, with Up/Down identical at every cutoff |
| 14 | Previous defaults (L=50, H=2) were **Pareto-dominated** — L=75/H=3 is 31% steadier *and* 23% faster to confirm, across all four datasets | Tuning | ✅ Defaults changed; "Steady" preset documented as the alternative |
| 15 | Optimizing on the 5-min futures set alone picked L=100/H=5; the multi-dataset average picked L=75/H=3. Single-tape tuning would have chosen wrong | Method | ✅ Recorded as a standing requirement for any future retuning |
| 16 | Real feeds contain garbage: the BTC set uses `1.7e308` as a missing-data sentinel and crashed the engine with `OverflowError` | Robustness | ✅ Engine carries the last good bar forward on any non-finite print (same as a halt, spec §9) |
| 17 | The synthetic reversal test asserted Transition specifically; real data shows reversals legitimately bridge via Sideways ~85% of the time | Bad test | ✅ Test now asserts the real invariant (Up and Down never adjacent — holds on 100% of real bars) plus an anti-regression check that Transition stays reachable |
| 18 | Measurement bug: the zigzag grading key initialized `direction = 0`, letting the extreme track price both ways, so it found zero turning points and delay silently reported `nan` | Bad test | ✅ Rewritten; delay is now measured |

## Findings from step 17-19 (OTC alignment + full ladder)

| # | Finding | Severity | Resolution |
|---|---|---|---|
| 19 | **Our trend definition did not match OTC's.** Bernd's six-pivot rule (3 highs, 3 lows, anything else = sideways) calls sideways ~80% of the time; ours said ~55%. Exact agreement 59-66% on real data | **Methodology mismatch** | ✅ OTC rule implemented and made the default; enhanced version kept as a toggle |
| 20 | OTC's rule answers high timeframes much sooner — it counts pivots instead of filling a lookback window (~27 monthly bars vs ~77) | Practical | ✅ Directly benefits the required 1W/1M rungs |
| 21 | Pine's `request.*` budget would be strained by 11 timeframes × 6 outputs | Scaling | ✅ Four state ints packed into one float; 3 series per timeframe |
| 22 | Two tests encoded assumptions from the pre-OTC default (Transition must exist; direction must wait for the lookback). Both are false in OTC mode *by design* | Bad test | ✅ Tests now name the mode they exercise and assert per-mode guarantees |
| 23 | Pivot detection still differs from OTC's (N-bar fractal vs. percentage ZigZag) | **Open gap** | ⬜ Documented in `docs/otc-alignment.md` as the next alignment step |

## Known unverified risk

The script has **never been run by TradingView**. It now passes static
analysis (`pynescript`): it parses cleanly as v5 and v6, and every built-in it
calls is real. That rules out syntax, indentation and typo errors. What static
analysis cannot check — and what still needs the real compiler — is
`simple` vs `series` type-qualifier rules, the `request.*` call budget, and
runtime behavior. `BUILD_PLAN.md` Part A lists these with fallbacks.

Tuning is now evidence-based across four real datasets, but **none of them is
NQ**. They establish the engine behaves sensibly across market types; they
cannot tell you how it feels on a 5m NQ chart at the cash open.

## Open questions / decisions pending

- [x] Platform confirmed: **TradingView / Pine Script** (2026-09-20).
- [ ] Four visible states (default) vs. three via Simple mode — which default?
- [ ] Confirm default timeframe ladder (chart TF + 1H + 4H + 1D).
- [ ] Balanced (L=75/H=3, current) vs. Steady (L=100/H=5) preset as default —
      both validated; this is a feel preference, so it's Paul's call.
