"""Reference implementation of the multi-timeframe trend-context engine.

Mirrors pinescript/nq_mtf_trend_context.pine bar for bar. Exists so the state
logic can be tested off-chart and so any future port (NinjaTrader, Python
backtest) has an executable definition to check against rather than prose.

Strictly causal: update() only ever sees bars up to and including the current
one, which is what makes the replay test in validate.py meaningful.
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
    fractal_n: int = 2
    lookback: int = 75
    slope_threshold: float = 1.5
    hysteresis: int = 3
    atr_len: int = 14
    min_swing_mult: float = 0.0
    vol_floor: float = 0.0
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

    def _update_swings(self):
        """Confirm a pivot only once fractal_n bars have closed after it."""
        n = self.fractal_n
        i = len(self.closes) - 1 - n
        if i < n:
            return
        window_h = self.highs[i - n:i + n + 1]
        window_l = self.lows[i - n:i + n + 1]
        cand_h, cand_l = self.highs[i], self.lows[i]

        no_filter = self.min_swing_mult <= 0 or self.atr is None
        min_leg = 0.0 if no_filter else self.min_swing_mult * self.atr

        last_low = self.swing_lows[-1] if self.swing_lows else None
        last_high = self.swing_highs[-1] if self.swing_highs else None

        if cand_h == max(window_h) and window_h.count(cand_h) == 1:
            if no_filter or last_low is None or (cand_h - last_low) >= min_leg:
                self.swing_highs.append(cand_h)
        if cand_l == min(window_l) and window_l.count(cand_l) == 1:
            if no_filter or last_high is None or (last_high - cand_l) >= min_leg:
                self.swing_lows.append(cand_l)

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
