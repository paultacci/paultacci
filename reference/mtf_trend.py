"""Reference implementation of the multi-timeframe trend-context engine.

Mirrors pinescript/nq_mtf_trend_context.pine bar for bar. Exists so the state
logic can be tested off-chart and so any future port (NinjaTrader, Python
backtest) has an executable definition to check against rather than prose.

Strictly causal: update() only ever sees bars up to and including the current
one, which is what makes the replay test in validate.py meaningful.
"""

from dataclasses import dataclass, field

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
    lookback: int = 50
    slope_threshold: float = 1.5
    hysteresis: int = 2
    atr_len: int = 14
    min_swing_mult: float = 0.0
    vol_floor: float = 0.0
    range_er: float = 0.25

    highs: list = field(default_factory=list)
    lows: list = field(default_factory=list)
    closes: list = field(default_factory=list)

    sh1: float = None
    sh2: float = None
    sl1: float = None
    sl2: float = None

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

        if cand_h == max(window_h) and window_h.count(cand_h) == 1:
            if no_filter or self.sl1 is None or (cand_h - self.sl1) >= min_leg:
                self.sh2, self.sh1 = self.sh1, cand_h
        if cand_l == min(window_l) and window_l.count(cand_l) == 1:
            if no_filter or self.sh1 is None or (self.sh1 - cand_l) >= min_leg:
                self.sl2, self.sl1 = self.sl1, cand_l

    def _structure_dir(self):
        if None in (self.sh1, self.sh2, self.sl1, self.sl2):
            return DIR_NONE
        if self.sh1 > self.sh2 and self.sl1 > self.sl2:
            return DIR_UP
        if self.sh1 < self.sh2 and self.sl1 < self.sl2:
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

        return {
            "state": self.confirmed_state,
            "raw": raw,
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
