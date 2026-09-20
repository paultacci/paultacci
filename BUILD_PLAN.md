# Build Plan — NQ Multi-Timeframe Trend Context Indicator

**Audience:** a coding agent picking this up cold, to review and implement.
**Read first:** `docs/multi-timeframe-market-context-indicator.md` (design
spec), then `docs/project-plan.md` (goal/plan), then the code at
`pinescript/nq_mtf_trend_context.pine`.

---

## 1. What this is and what "done" means

The owner (an NQ futures trader) wants **one indicator he can add to his
chart that tells him, at a glance, whether the market is in an uptrend,
downtrend, or sideways** — across several timeframes at once, without it
lying to him when the answer is genuinely unclear.

**Definition of done:**

1. The script compiles in TradingView's Pine Editor with zero errors.
2. It adds to an NQ chart (`CME_MINI:NQ1!`) and renders: colored background,
   a multi-timeframe table, and working tooltips.
3. States read correctly against eyeballed price action: a visibly trending
   session shows Up/Down; a visibly rangebound session shows Sideways.
4. Higher-timeframe values do not repaint — a state shown live on a closed
   bar still reads the same when the chart is reloaded later.
5. It does not flicker so much as to be unusable (target: on a 5m NQ chart,
   the chart-timeframe state should not change more than a handful of times
   per session under default settings).

**Non-goals — do not add these:** entry/exit signals, backtest strategy
conversion, position sizing, session/Globex-specific logic, anything that
collapses the multi-timeframe read into a single trade recommendation.

---

## 2. Current state

| File | Contents | Status |
|---|---|---|
| `docs/multi-timeframe-market-context-indicator.md` | Full design spec: two direction measures, separate strength, state definitions, evaluation criteria, cross-market adaptation | Complete, authoritative |
| `docs/project-plan.md` | Goal, outline, step plan | Complete |
| `docs/pinescript-usage.md` | End-user install/read guide | Needs update to 5-state model |
| `pinescript/nq_mtf_trend_context.pine` | v2 implementation | **Written but never compiled** |
| `PROGRESS.md` | Checkpoint tracker | Live |

### Algorithm summary (as implemented)

Per timeframe, two independent direction measures plus a separate strength
measure feed a hysteresis state machine:

- **Structure** — `ta.pivothigh/pivotlow(N, N)` confirmed swings; HH+HL = up,
  LH+LL = down, anything else = no clean sequence. Optional minimum swing
  size filter (`k × ATR`) to reject noise swings.
- **Slope** — Pearson correlation of `close` against `bar_index` over `L`
  bars, converted to a regression t-statistic via
  `t = r·√(L−2)/√(1−r²)`. Above/below `±threshold` = up/down, inside = flat.
  This is the volatility normalization: it measures drift relative to noise,
  not raw point movement.
- **Strength** — Kaufman efficiency ratio: `|net move| / total path length`
  over `L`. Bucketed Weak/Moderate/Strong. Deliberately not derived from
  either direction measure's sign.
- **States** — `0` insufficient, `1` up, `-1` down, `2` sideways (both
  measures independently say "no direction"), `3` transition (measures
  disagree). Hysteresis `H` requires a new raw state to persist `H` bars
  before the confirmed state flips.

---

## 3. Part A — Review tasks (do these first)

I wrote this code **without the ability to compile it** — TradingView is not
reachable from the authoring environment. The following are specific,
known-uncertain areas. Verify each in the Pine Editor and fix what breaks.

### A1. Type-qualifier propagation — ✅ already designed out

`f_calc()` originally took lengths as parameters and passed them to
`ta.atr()`, `ta.pivothigh()`, `ta.correlation()` and `math.sum()`, which want
**`simple int`** arguments — Pine can downgrade a value to `series int` across
a function boundary, especially inside `request.security()`. The function now
takes only `_waitForClose` and reads the length inputs from globals, which
keeps the qualifier intact. **Do not "clean this up" by re-parameterising it.**

### A2. `var` state inside a tuple-returning UDF called from `request.security()`

`f_calc()` keeps `var` state (swing history, hysteresis counters). Confirm:
(a) it compiles, (b) each `request.security()` call maintains **independent**
state per timeframe — verify by setting two timeframes to obviously different
values and confirming their table rows differ.

### A3. Request-call budget

Four `request.security()` calls each returning a **6-element tuple**. Confirm
this stays under Pine's `request.*` limit. If it errors, drop the tooltip
diagnostics (`t`, `sd`, `pd`) back out of the tuple and show only state, raw,
and ER — tooltips lose detail but the core survives.

### A4. Smaller syntax risks — confirm each

- `float idx = bar_index` (int→float local declaration inside a function).
- `math.sum(math.abs(ta.change(close)), _lenL)` — confirm name/signature.
- `chart.fg_color` / `chart.bg_color` availability in v6.
- `table.cell(..., tooltip=...)` parameter support.
- `f_row()` — a UDF that calls `table.cell()` internally; confirm Pine allows
  table mutation from inside a user-defined function.
- `timeframe.in_seconds(tf2)` where `tf2` comes from `input.timeframe()`.
- `alertcondition(ta.change(chState) != 0, ...)` — `ta.change` on an int series.

### A4b. Keep the Pine script and the Python twin in sync

`reference/mtf_trend.py` is an executable definition of the same engine, and
`reference/validate.py` tests it (`python3 reference/validate.py`, no
dependencies, runs in seconds). **Any logic change to the Pine script must be
mirrored there and the harness re-run** — that harness is what caught the
Sideways bug described in `docs/validation-report.md`. If you change the state
machine and only touch the `.pine` file, the two silently diverge and the
tests start validating a version that no longer ships.

### A5. Logic review (not syntax)

Read the state machine against spec §6.1 and confirm the implementation
matches the table there exactly, particularly:

- Sideways requires **both** `structDir == 2` and `slopeDir == 2`.
- Any single measure reporting insufficient forces the whole state to
  insufficient (never silently treat missing data as "flat").
- Hysteresis counts *consecutive* bars of the same candidate state, and
  resets when the candidate changes.

---

## 4. Part B — Implementation tasks

Ordered. Each has an acceptance criterion; don't mark one done without it.

### B1. Get it compiling and on a chart
Fix everything from Part A until the script loads on `CME_MINI:NQ1!`.
**Accept:** no errors, table renders, background colors.

### B2. Verify non-repainting behavior
With `waitForClose = true`, note the 1H/4H/1D states at a specific bar. Reload
the chart and compare. Then repeat with `waitForClose = false` and confirm the
higher-timeframe values now *do* update intrabar (this proves the toggle is
actually wired to real behavior, not decorative).
**Accept:** documented before/after showing the toggle changes behavior as
described, and that `true` is stable across reload.

### B3. Sanity-check states against visible price action
Load a known strongly trending NQ day and a known chop day (use bar replay).
**Accept:** trending day reads Up/Down with Moderate/Strong efficiency; chop
day reads Sideways with Weak efficiency. If a chop day reads as a trend, the
slope threshold is too low — report the finding, don't silently retune.

### B3b. Already measured off-chart — confirm, don't redo
`docs/validation-report.md` has state mix, flip rate, confirmation delay and
parameter sweeps across four real datasets, plus static parse results. Read it
before doing any tuning work so you are confirming findings on NQ rather than
rediscovering them.

### B4. Measure flip rate (spec §6.2)
Count confirmed-state changes on the chart timeframe over one full session at
defaults. If it exceeds ~6–8 flips/session on 5m, tune in this order:
(1) raise hysteresis `H`, (2) enable min swing size (`0.5 × ATR`), (3) raise
slope threshold. Record what each change did.
**Accept:** a short table of setting → flip count → subjective usability.

### B5. Parameter sensitivity spot-check (spec §6.4)
Already run on synthetic data — see `docs/validation-report.md` for the grid.
**Do not redo that work; confirm or refute it on real bars.** Specifically:
lookback dominated flip rate (20 → 87 flips, 100 → 47), hysteresis 2 → 3
bought nothing, and the min-swing filter was negligible. Check whether real
NQ agrees, since synthetic data has no fat tails, gaps, or session effects.
**Accept:** findings appended to the validation report; propose new defaults
with reasoning, but **do not change defaults without the owner's sign-off** —
he trades this, the call is his.

### B6. Update docs to match reality
`docs/pinescript-usage.md` still describes the old four-state model and lacks
the new inputs (`minSwingMult`, `simpleMode`, `Sideways`/`Transition` colors,
tooltips, alignment row).
**Accept:** docs describe exactly what the shipped script does.

---

## 5. Part C — Open decisions for the owner (do not decide these alone)

1. **Platform.** TradingView/Pine was assumed, not confirmed. If he's on
   NinjaTrader, ThinkorSwim, or Sierra Chart, the engine logic ports but the
   whole rendering layer is rewritten. Confirm before deep tuning work.
2. **Four visible states vs three.** The spec preserves Sideways and
   Transition separately; `simpleMode` merges them. Default is currently
   *separate*. Confirm which he wants as default.
3. **Default timeframe ladder.** Currently chart TF + 1H + 4H + 1D, with
   Weekly available but off.
4. **Any default parameter change** arising from B4/B5.

---

## 6. Working agreement

- Update `PROGRESS.md` as steps complete — it's the accountability record.
- Commit to branch `claude/multi-timeframe-market-indicator-vnpamf`.
- Keep the engine free of strategy/session logic (spec §1). If a request
  seems to need it, raise it rather than quietly coupling them.
- When a fix changes behavior the spec describes, update the spec in the same
  commit so the two never drift.
