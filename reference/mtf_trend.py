"""Reference implementation of the multi-timeframe trend-context engine.

Mirrors the per-timeframe engine in pinescript/nq_mtf_trend_context.pine so
the state logic can be tested off-chart, and so any future port has an
executable definition to check against rather than prose.

Strictly causal: update() only ever sees bars up to and including the current
one, which is what makes the replay test in validate.py meaningful.

PARITY WITH THE PINE SCRIPT -- two deliberate differences, verified by audit:

1. `waitForClose` is not modelled here. In Pine it reports the previous bar's
   values so a higher timeframe pulled through request.security() cannot drift
   while its bar is still forming. That is a multi-timeframe plumbing concern
   with no meaning for a single series, so this engine always corresponds to
   the Pine path with waitForClose = false.

2. The volatility floor differs in units. Pine expresses it as a multiple of
   syminfo.mintick (default 10x, so 2.5 points on NQ); here `vol_floor` is an
   absolute price distance and defaults to 0, i.e. off. On any liquid
   instrument the floor is inert either way -- NQ's ATR is orders of magnitude
   above 2.5 points -- but the two are not the same knob and should not be
   compared directly.

Everything else was checked line by line and matches: ZigZag seeding and
reversal logic, the structure comparison for 2/3/4 pivots per side, the
correlation t-statistic, the efficiency ratio window, the OTC and enhanced
composition rules, and the hysteresis counter.
"""

from dataclasses import dataclass, field
from math import isfinite

INSUFFICIENT, UP, DOWN, SIDEWAYS, TRANSITION = 0, 1, -1, 2, 3

STATE_NAMES = {
    INSUFFICIENT: "Insufficient",
    UP: "Up",
    DOWN: "Down",
    SIDEWAYS: "Sideways",
    TRANSITION: "Transition",
}

# Direction codes shared by the structure and slope measures.
DIR_NONE, DIR_UP, DIR_DOWN, DIR_FLAT = 0, 1, -1, 2


@dataclass
class TrendEngine:
    lookback: int = 75
    slope_threshold: float = 1.5
    hysteresis: int = 3
    atr_len: int = 14
    vol_floor: float = 0.0

    # ZigZag reversal threshold: "pct" is OTC-faithful, "atr" auto-scales
    # across the timeframe ladder. See _reversal_threshold().
    zz_mode: str = "atr"
    zz_pct: float = 3.0
    zz_atr_mult: float = 1.5
    range_er: float = 0.25

    # 2 = compare the last two swing highs and lows (one comparison per side).
    # 3 = the OTC "six-pivot rule" (Bernd, supply & demand course lesson 10):
    #     three highs and three lows, requiring two consecutive higher highs
    #     AND higher lows for an uptrend. Stricter; anything else is sideways.
    structure_pivots: int = 3
    otc_mode: bool = True  # structure alone decides direction, as taught

    highs: list = field(default_factory=list)
    lows: list = field(default_factory=list)
    closes: list = field(default_factory=list)

    swing_highs: list = field(default_factory=list)
    swing_lows: list = field(default_factory=list)
    zz_dir: int = 0
    zz_ext: float = None

    atr: float = None
    _tr_seed: list = field(default_factory=list)

    confirmed_state: int = INSUFFICIENT
    pending_state: int = INSUFFICIENT
    pending_count: int = 0

    def _update_atr(self):
        if len(self.closes) < 2:
            return
        h, l, pc = self.highs[-1], self.lows[-1], self.closes[-2]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        if self.atr is None:
            self._tr_seed.append(tr)
            if len(self._tr_seed) == self.atr_len:
                self.atr = sum(self._tr_seed) / self.atr_len
        else:
            self.atr = (self.atr * (self.atr_len - 1) + tr) / self.atr_len

    def _reversal_threshold(self):
        """Absolute price distance that counts as a reversal.

        Percent mode is what OTC teaches (a ZigZag set to e.g. 3%). ATR mode
        exists because one percentage cannot serve a ladder from 5m to 1M --
        3% is a routine move on a monthly chart and a once-a-year event on a
        5-minute one -- so it scales the same idea to each timeframe's own
        volatility.
        """
        if self.zz_mode == "pct":
            base = self.zz_ext if self.zz_ext is not None else self.closes[-1]
            return abs(base) * self.zz_pct / 100.0
        if self.atr is None:
            return None
        return self.atr * self.zz_atr_mult

    def _update_swings(self):
        """ZigZag pivot detection, matching the tool OTC marks pivots with.

        A pivot is recorded only when price retraces from the running extreme
        by the reversal threshold, so pivots strictly alternate high/low/high
        and each one is fixed the moment it is recorded. The still-forming
        leg's extreme is never published -- that is the part of a ZigZag that
        repaints, and publishing it would be lookahead.
        """
        h, l = self.highs[-1], self.lows[-1]
        if self.zz_ext is None:
            self.zz_ext, self.zz_dir = h, 1
            return
        thr = self._reversal_threshold()
        if thr is None or thr <= 0:
            return

        if self.zz_dir > 0:
            if h > self.zz_ext:
                self.zz_ext = h
            elif (self.zz_ext - l) >= thr:
                self.swing_highs.append(self.zz_ext)
                self.zz_dir, self.zz_ext = -1, l
        else:
            if l < self.zz_ext:
                self.zz_ext = l
            elif (h - self.zz_ext) >= thr:
                self.swing_lows.append(self.zz_ext)
                self.zz_dir, self.zz_ext = 1, h

    def _structure_dir(self):
        """Newest-first sequences of swing highs and lows.

        With structure_pivots=3 this is the OTC six-pivot rule: an uptrend
        needs two consecutive higher highs AND two consecutive higher lows.
        Bernd's worked example -- a lower high with a higher low -- lands in
        the residual case, which he calls sideways outright.
        """
        k = self.structure_pivots
        if len(self.swing_highs) < k or len(self.swing_lows) < k:
            return DIR_NONE
        hs = self.swing_highs[-k:][::-1]
        ls = self.swing_lows[-k:][::-1]
        rising = all(hs[i] > hs[i + 1] for i in range(k - 1)) and \
                 all(ls[i] > ls[i + 1] for i in range(k - 1))
        falling = all(hs[i] < hs[i + 1] for i in range(k - 1)) and \
                  all(ls[i] < ls[i + 1] for i in range(k - 1))
        if rising:
            return DIR_UP
        if falling:
            return DIR_DOWN
        return DIR_FLAT

    def _slope(self):
        """Regression t-stat of close against bar index, via Pearson r."""
        L = self.lookback
        if len(self.closes) - 1 < L:
            return None, DIR_NONE
        y = self.closes[-L:]
        x = list(range(L))
        mx, my = sum(x) / L, sum(y) / L
        sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
        sxx = sum((a - mx) ** 2 for a in x)
        syy = sum((b - my) ** 2 for b in y)
        if sxx <= 0 or syy <= 0:
            return None, DIR_NONE
        r = sxy / (sxx * syy) ** 0.5
        denom = 1 - r * r
        t = r * ((L - 2) ** 0.5) / (denom ** 0.5) if denom > 1e-4 else (999.0 if r > 0 else -999.0)

        if self.atr is not None and self.vol_floor > 0 and self.atr < self.vol_floor:
            return t, DIR_NONE
        if t > self.slope_threshold:
            return t, DIR_UP
        if t < -self.slope_threshold:
            return t, DIR_DOWN
        return t, DIR_FLAT

    def _efficiency(self):
        L = self.lookback
        if len(self.closes) < L + 1:
            return 0.0
        seg = self.closes[-(L + 1):]
        net = abs(seg[-1] - seg[0])
        path = sum(abs(seg[i + 1] - seg[i]) for i in range(len(seg) - 1))
        return net / path if path > 0 else 0.0

    def _compose(self, struct_dir, slope_dir, er):
        if self.otc_mode:
            # As taught: structure alone decides, and the residual is sideways.
            # No slope vote, so no Transition state exists in this mode.
            if struct_dir == DIR_NONE:
                return INSUFFICIENT
            return {DIR_UP: UP, DIR_DOWN: DOWN}.get(struct_dir, SIDEWAYS)
        if struct_dir == DIR_NONE or slope_dir == DIR_NONE:
            return INSUFFICIENT
        if struct_dir == DIR_UP and slope_dir == DIR_UP:
            return UP
        if struct_dir == DIR_DOWN and slope_dir == DIR_DOWN:
            return DOWN
        if struct_dir == DIR_FLAT and slope_dir == DIR_FLAT:
            return SIDEWAYS
        # The measures disagree. Efficiency decides what kind of disagreement:
        # price going nowhere is chop, price travelling decisively is a real
        # regime handover. Without this, ranges read as permanent Transition,
        # because a t-stat over a noisy window is almost never flat.
        return SIDEWAYS if er < self.range_er else TRANSITION

    def update(self, high, low, close):
        # Real feeds emit unusable prints: halts, gaps, and sentinel values
        # like 1.7e308 standing in for "missing". Carrying the last good bar
        # forward keeps bar alignment and asserts no movement, rather than
        # letting garbage poison every window it touches.
        if not all(isfinite(v) and v > 0 for v in (high, low, close)):
            if not self.closes:
                return self._emit(DIR_NONE, DIR_NONE, None, 0.0)
            high, low, close = self.highs[-1], self.lows[-1], self.closes[-1]

        self.highs.append(high)
        self.lows.append(low)
        self.closes.append(close)

        self._update_atr()
        self._update_swings()

        struct_dir = self._structure_dir()
        tstat, slope_dir = self._slope()
        er = self._efficiency()
        raw = self._compose(struct_dir, slope_dir, er)

        if raw != self.confirmed_state:
            if raw == self.pending_state:
                self.pending_count += 1
            else:
                self.pending_state = raw
                self.pending_count = 1
            if self.pending_count >= self.hysteresis:
                self.confirmed_state = self.pending_state
                self.pending_count = 0
        else:
            self.pending_state = raw
            self.pending_count = 0

        return self._emit(struct_dir, slope_dir, tstat, er, raw)

    def _emit(self, struct_dir, slope_dir, tstat, er, raw=None):
        return {
            "state": self.confirmed_state,
            "raw": self.confirmed_state if raw is None else raw,
            "structure": struct_dir,
            "slope": slope_dir,
            "tstat": tstat,
            "efficiency": er,
            "atr": self.atr,
        }


def run(bars, **kwargs):
    """bars: iterable of (high, low, close). Returns list of per-bar results."""
    eng = TrendEngine(**kwargs)
    return [eng.update(h, l, c) for h, l, c in bars]
