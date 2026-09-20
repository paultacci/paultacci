# Handoff — NQ Multi-Timeframe Trend Indicator

For a fresh session that **has TradingView access**. Everything else is done;
what remains needs a real Pine compiler and a real NQ chart.

Repo: `paultacci/paultacci` · Branch: `claude/multi-timeframe-market-indicator-vnpamf`

---

## What this is

A TradingView indicator that shows, per timeframe, whether the market is in an
**uptrend, downtrend, or sideways** — plus honest "transition" and
"insufficient data" states. It is context only: **no entry/exit signals, no
session/Globex logic**. Paul trades NQ futures and studies at Online Trading
Campus (OTC); the indicator's default trend definition deliberately matches
what OTC teaches so it doesn't contradict his training.

## Read these first, in order

| File | What it gives you |
|---|---|
| `PROGRESS.md` | Status tracker + every finding so far (25 of them) |
| `docs/otc-alignment.md` | The trend definition, sourced to Bernd's lesson with verbatim quotes |
| `pinescript/nq_mtf_trend_context.pine` | **The deliverable** |
| `BUILD_PLAN.md` Part A | Ranked list of things that could fail on compile, each with a fallback |
| `docs/validation-report.md` | What's been measured and how |
| `reference/` | Python twin of the engine + test harnesses |

## The algorithm in one screen

Per timeframe, independently:

1. **ZigZag pivots** — a pivot is recorded only once price retraces from the
   running extreme by a threshold (default **1.5 × ATR**). Pivots strictly
   alternate high/low. The still-forming leg's extreme is never published
   (that's the repainting part).
2. **Structure** — the last 3 highs and 3 lows. **Two higher highs AND two
   higher lows = uptrend**; two lower highs and two lower lows = downtrend;
   **anything else = sideways**. This is OTC's six-pivot rule, confirmed
   verbatim against the lesson captions.
3. **OTC mode (default ON)** — structure alone decides. No slope, no
   Transition state, exactly as taught.
4. **OTC mode OFF** — adds a volatility-normalized slope (regression
   t-statistic) as a second opinion; when the two disagree, the Kaufman
   efficiency ratio decides chop (Sideways) vs. real handover (Transition).
5. **Hysteresis** (default 3 bars) debounces state flips.

11 timeframes: 5m, 15m, 30m, 1H, 90m, 4H, 6H, 1D, 2D, 1W, 1M. Required
minimum is 30m, 90m, 6H, 1W, 1M. Higher timeframes come through
`request.security()`; four state ints are packed into one float so each rung
costs 3 series rather than 6, to stay inside Pine's `request.*` budget.

## Status

**Done:** design spec, engine, multi-timeframe wiring, visuals (background
colour, candle colour, on-chart table, per-cell tooltips, alerts), Python
reference implementation, 9 passing logic tests, validation across 4 real
datasets, evidence-based defaults, OTC alignment, static analysis.

**Not done — needs you:**

1. **Compile it.** The script has *never been run by TradingView*. It passes
   static analysis (`pynescript`: parses clean as v5 and v6; every built-in it
   calls verified to exist), which rules out syntax and typo errors. It cannot
   rule out semantic errors.
2. **Verify non-repainting.** With `waitForClose = true`, note the 1H/4H/1D
   states at a given bar, reload the chart, confirm they're unchanged. Then
   set it false and confirm higher-timeframe rows now *do* update intrabar —
   that proves the toggle is wired to real behavior, not decorative.
3. **Sanity-check against price.** Load a trending NQ day and a chop day (bar
   replay). Trending should read Up/Down; chop should read Sideways. If a chop
   day reads as a trend, report it — don't silently retune.
4. **Confirm it feels right.** Defaults give ~1 state change per 30–35 bars
   across four real datasets. On a live 5m NQ chart that may feel too slow or
   too fast. Paul decides; propose with numbers, don't change defaults alone.

## Where it's most likely to break (ranked)

From `BUILD_PLAN.md` Part A — check these first if compile fails:

1. **`var` state inside a user-defined function called from
   `request.security()`.** `f_calc()` keeps `var` swing history and hysteresis
   counters, and is called 11 times through `request.security()`. Each call
   must maintain *independent* state. Verify by setting two timeframes to
   obviously different values and confirming their rows differ.
2. **Type qualifiers.** `f_calc()` deliberately reads length inputs from
   globals rather than taking them as parameters, because `ta.atr()` and
   friends need `simple int` and Pine can downgrade a value to `series` across
   a function boundary. **Do not "clean this up" by re-parameterising it.**
3. **`request.*` budget.** 11 calls × 3-element tuples. If it errors, drop the
   tooltip diagnostics (`tstat`, struct, slope) from the packed code and keep
   state + efficiency only.
4. **The float packing.** `code = (state+2) + 10*(raw+2) + 100*(struct+2) +
   1000*(slope+2)`, unpacked with `math.floor`/`%`. Max value 4455, all
   integers, so no precision risk — but verify the unpack returns what the
   tooltip claims.
5. **Smaller ones:** `chart.fg_color`, `table.cell(..., tooltip=)`, `f_row()`
   mutating a table from inside a UDF, `timeframe.in_seconds()` on an
   `input.timeframe` value, `alertcondition` on a computed state.

## Rules of engagement

- **Any logic change to the `.pine` must be mirrored in
  `reference/mtf_trend.py`, and `python3 reference/validate.py` must still
  pass.** That harness is what caught the bug where `Sideways` was
  unreachable. If you change only the Pine file, the tests start validating a
  version that doesn't ship.
- Two deliberate Python/Pine differences are documented at the top of
  `mtf_trend.py`: `waitForClose` isn't modelled (it's multi-timeframe
  plumbing), and the volatility floor uses different units. Everything else
  was audited line by line and matches.
- Don't add entry/exit signals, position sizing, or session logic.
- Update `PROGRESS.md` as things get done.
- Commit to `claude/multi-timeframe-market-indicator-vnpamf`.

## Known open questions for Paul

- Four visible states (default) vs. three via **Simple mode**, which merges
  Transition into Sideways.
- Whether the monthly row populates on his chart. In OTC mode it needs ~35
  monthly bars (~3 years) to accumulate six pivots. If it reads Insufficient,
  lower the reversal threshold rather than assuming it's broken.
- Any default change arising from step 4 above.
