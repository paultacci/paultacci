# Checkpoint Tracker — NQ Multi-Timeframe Trend Indicator

Update this file as each step actually gets done — it's the single source of
truth for "is this getting done." See `docs/project-plan.md` for the full
plan and `docs/multi-timeframe-market-context-indicator.md` for the design
spec this is built from.

## Status

| # | Step | Status | Date | Notes |
|---|---|---|---|---|
| 1 | Design spec (structure vs. slope, strength, states) | ✅ Done | 2026-09-20 | `docs/multi-timeframe-market-context-indicator.md` |
| 2 | Core Pine engine written | ✅ Done | 2026-09-20 | `pinescript/nq_mtf_trend_context.pine` |
| 3 | Multi-timeframe wiring (non-repainting) | ✅ Done | 2026-09-20 | Same file |
| 4 | Visuals (background/candle color, table, alerts) | ✅ Done | 2026-09-20 | Same file |
| 5 | **Compile-check on TradingView** | ⬜ Not started | | **Blocking — needs Paul to paste script into TradingView and confirm it compiles/adds to chart** |
| 6 | Visual tuning on a live/replay NQ chart | ⬜ Not started | | Needs a trending session + a choppy session observed |
| 7 | Parameter sensitivity spot-check | ⬜ Not started | | |
| 8 | Usage guide | ⬜ Not started | | |

## How to update this file

When a step completes, change ⬜ to ✅, fill in the date, and add a one-line
note. If something breaks or a step reveals new work, add a row rather than
silently expanding an existing one, so history stays visible.

## Open questions / decisions pending

- [ ] Confirm platform: TradingView/Pine Script assumed — confirm or correct.
- [ ] Confirm default timeframe ladder once on a real chart (currently:
      chart TF, 1H, 4H, 1D, optional Weekly).
- [ ] Confirm visual style holds up (background shading + table) vs. wanting
      candle coloring on by default too.
