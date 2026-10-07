"""
Market Intel signal model.

Each signal reads one aspect of the heating-oil market (futures momentum, distillate crack,
curve shape, inventories, exports, positioning, weather, ...) and scores it from -2 (strongly
bearish for prices) to +2 (strongly bullish) for each of three horizons. Scores are combined
with the per-horizon weights in WEIGHTS into an outlook, a confidence level and the main
drivers.

Everything is evaluated "as of" a date, so the same code powers the live outlook and the
backtest. This is a transparent decision aid, not a statistical forecast.
"""
from bisect import bisect_right
from collections import defaultdict
from datetime import date, timedelta
from math import exp, log, sqrt
from statistics import median, pstdev
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Company, MarketEvent, MarketIndicator, OilPrice

HORIZONS = ("days", "weeks", "months")
HORIZON_LABELS = {"days": "Next 1-7 days", "weeks": "Next 2-4 weeks", "months": "Next 2-3 months"}
HORIZON_CALENDAR_DAYS = {"days": 7, "weeks": 28, "months": 84}
HORIZON_TRADING_DAYS = {"days": 5, "weeks": 20, "months": 60}

GALLONS_PER_BBL = 42.0
GASOIL_BBL_PER_TONNE = 7.45
GASOIL_GAL_PER_TONNE = GASOIL_BBL_PER_TONNE * GALLONS_PER_BBL

# Weight of each signal per horizon. A signal with no entry (or 0) for a horizon is ignored there.
# These are judgement calls, not fitted values; the backtest endpoint reports how each performs.
WEIGHTS: Dict[str, Dict[str, float]] = {
    "futures_momentum":   {"days": 3.0, "weeks": 1.5, "months": 0.5},
    "weather_hdd":        {"days": 2.5, "weeks": 1.5},
    "positioning":        {"days": 2.0, "weeks": 1.0},
    "retail_passthrough": {"days": 1.5, "weeks": 1.5},
    "distillate_crack":   {"days": 1.0, "weeks": 2.0, "months": 2.0},
    "curve_structure":    {"days": 1.0, "weeks": 1.5, "months": 3.0},
    "us_stocks":          {"days": 0.5, "weeks": 2.5, "months": 2.0},
    "northeast_stocks":   {"days": 0.5, "weeks": 2.0, "months": 1.0},
    "exports":            {"days": 0.5, "weeks": 1.5, "months": 1.0},
    "transatlantic_arb":  {"days": 1.0, "weeks": 1.5, "months": 0.5},
    "refinery_runs":      {"days": 0.5, "weeks": 1.0, "months": 0.5},
    "demand":             {"weeks": 0.75, "months": 0.5},
    "enso":               {"weeks": 0.25, "months": 1.0},
    "substitutes":        {"days": 0.25, "weeks": 0.5, "months": 0.5},
    "events":             {"days": 1.5, "weeks": 2.0, "months": 2.5},
}

# (stale-after days) per series; a signal whose newest input is older is reported as stale.
STALE_AFTER = {
    "ulsd": 6, "brent": 6, "retail": 14, "ho_crack": 6, "arb": 6, "gasoil": 6,
    "us_dist_stocks": 14, "padd1_dist_stocks": 14, "padd1a_dist_stocks": 14,
    "dist_exports": 14, "dist_demand": 14, "refinery_util": 14,
    "cot_ulsd_mm_net_pct": 14, "hdd_dev_7d_pct": 4, "hdd_dev_15d_pct": 4,
    "enso_oni": 120, "henry_hub": 10, "propane_mb": 10,
}

MIN_HISTORY = 30


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def percentile_rank(pool: List[float], x: float) -> float:
    if not pool:
        return 50.0
    below = sum(1 for v in pool if v < x)
    equal = sum(1 for v in pool if v == x)
    return (below + 0.5 * equal) / len(pool) * 100.0


class SignalContext:
    """All series needed by the signals, loaded once and queryable as of any date."""

    def __init__(self, db: Session, lookback_days: int = 1900):
        self.db = db
        self.today = date.today()
        start = self.today - timedelta(days=lookback_days)
        self.s: Dict[str, Tuple[List[date], List[float]]] = {}
        self.labels: Dict[str, str] = {}

        # --- stored indicators
        raw: Dict[str, Dict[date, float]] = defaultdict(dict)
        for r in db.query(MarketIndicator).filter(MarketIndicator.obs_date >= start).all():
            raw[r.series_key][r.obs_date] = r.value
            if r.label:
                self.labels[r.series_key] = r.label
        for k, m in raw.items():
            self._put(k, m)

        # --- price series (OilPrice) : market futures first, EIA spot to fill gaps
        self._put("ulsd", self._prices(["Market Index: NY Harbor ULSD"], ["EIA Index: NY Harbor ULSD Spot"], start))
        self._put("brent", self._prices(["Market Index: Brent Crude"], ["EIA Index: Brent Crude Spot"], start))
        self._put("retail", self._retail(start))

        # --- derived series
        ulsd = self.s.get("ulsd")
        brent = self.s.get("brent")
        if ulsd and brent:
            self._put("ho_crack", {d: GALLONS_PER_BBL * v - b
                                   for d, v in zip(*ulsd)
                                   for b in [self.value_at("brent", d, 4)] if b is not None})
        if "gasoil_front_usd_t" in self.s:
            g = dict(zip(*self.s["gasoil_front_usd_t"]))
            self._put("gasoil", {d: v / GASOIL_GAL_PER_TONNE for d, v in g.items()})
            if brent:
                self._put("gasoil_crack", {d: v / GASOIL_BBL_PER_TONNE - b for d, v in g.items()
                                           for b in [self.value_at("brent", d, 4)] if b is not None})
            if ulsd:
                self._put("arb", {d: v / GASOIL_GAL_PER_TONNE - u for d, v in g.items()
                                  for u in [self.value_at("ulsd", d, 4)] if u is not None})
        retail = self.s.get("retail") or self.s.get("ma_retail_ho")
        if retail and ulsd:
            self._put("retail_margin", {d: v - u for d, v in zip(*retail)
                                        for u in [self.value_at("ulsd", d, 6)] if u is not None})

        self.events = db.query(MarketEvent).all()

    # ---- loading helpers
    def _put(self, key: str, m: Dict[date, float]) -> None:
        if not m:
            return
        items = sorted(m.items())
        self.s[key] = ([d for d, _ in items], [v for _, v in items])

    def _prices(self, primary: List[str], fallback: List[str], start: date) -> Dict[date, float]:
        out: Dict[date, float] = {}
        for names in (fallback, primary):  # primary written last so it wins
            rows = self.db.query(OilPrice.date_reported, func.avg(OilPrice.price_per_gallon)).join(Company).filter(
                Company.name.in_(names), OilPrice.date_reported >= start
            ).group_by(OilPrice.date_reported).all()
            for d, v in rows:
                out[d] = float(v)
        return out

    def _retail(self, start: date) -> Dict[date, float]:
        rows = self.db.query(OilPrice.date_reported, func.avg(OilPrice.price_per_gallon)).join(Company).filter(
            Company.is_market_index == False, OilPrice.date_reported >= start  # noqa: E712
        ).group_by(OilPrice.date_reported).all()
        return {d: float(v) for d, v in rows}

    # ---- queries
    def has(self, key: str) -> bool:
        return key in self.s

    def last(self, key: str, as_of: date, max_age: Optional[int] = None) -> Optional[Tuple[date, float]]:
        if key not in self.s:
            return None
        dates, vals = self.s[key]
        i = bisect_right(dates, as_of)
        if i == 0:
            return None
        d, v = dates[i - 1], vals[i - 1]
        if max_age is not None and (as_of - d).days > max_age:
            return None
        return d, v

    def value_at(self, key: str, as_of: date, tolerance: int = 0) -> Optional[float]:
        r = self.last(key, as_of, tolerance)
        return r[1] if r else None

    def back(self, key: str, as_of: date, days: int, tolerance: int = 6) -> Optional[float]:
        """Value `days` before as_of (latest observation at or before that date)."""
        return self.value_at(key, as_of - timedelta(days=days), tolerance)

    def window(self, key: str, as_of: date, days: int) -> List[float]:
        if key not in self.s:
            return []
        dates, vals = self.s[key]
        hi = bisect_right(dates, as_of)
        lo = bisect_right(dates, as_of - timedelta(days=days))
        return vals[lo:hi]

    def pct_change(self, key: str, as_of: date, days: int) -> Optional[float]:
        now, then = self.value_at(key, as_of, STALE_AFTER.get(key, 10)), self.back(key, as_of, days)
        if now is None or not then:
            return None
        return now / then - 1.0

    def seasonal_pool(self, key: str, as_of: date, years: int = 5, window: int = 15) -> List[float]:
        """Values from the same time of year (+/- window days) in the previous `years` years."""
        if key not in self.s:
            return []
        dates, vals = self.s[key]
        pool: List[float] = []
        for y in range(1, years + 1):
            centre = as_of - timedelta(days=round(365.25 * y))
            lo = bisect_right(dates, centre - timedelta(days=window + 1))
            hi = bisect_right(dates, centre + timedelta(days=window))
            pool.extend(vals[lo:hi])
        return pool

    def curve_at(self, as_of: date) -> List[Tuple[int, float]]:
        """ULSD futures strip as of a date: [(YYYYMM, price)] for contracts not yet expired."""
        cur_ym = as_of.year * 100 + as_of.month
        strip = []
        for key in self.s:
            if not key.startswith("ho_fut:"):
                continue
            ym = int(key.split(":")[1])
            if ym <= cur_ym:  # HO expires the last business day of the month before delivery
                continue
            v = self.value_at(key, as_of, 5)
            if v is not None:
                strip.append((ym, v))
        strip.sort()
        return strip

    def active_events(self, as_of: date, live: bool) -> List[MarketEvent]:
        out = []
        for e in self.events:
            if live and not e.active:
                continue
            if e.start_date and e.start_date > as_of:
                continue
            if e.expires_on and e.expires_on < as_of:
                continue
            out.append(e)
        return out


# ----------------------------------------------------------------------------- signal helpers

def _signal(key: str, label: str, group: str, scores: Optional[Dict[str, float]] = None,
            display: str = "", detail: str = "", percentile: Optional[float] = None,
            as_of: Optional[date] = None, reason: Optional[str] = None) -> Dict[str, Any]:
    available = scores is not None
    return {
        "key": key, "label": label, "group": group, "available": available,
        "scores": {h: round(scores[h], 2) for h in HORIZONS if h in scores} if scores else {},
        "display": display, "detail": detail,
        "percentile": None if percentile is None else round(percentile, 0),
        "as_of": as_of.isoformat() if as_of else None,
        "reason": None if available else (reason or "No data yet"),
        "weights": WEIGHTS.get(key, {}),
    }


def _stale(ctx: SignalContext, key: str, as_of: date) -> Optional[str]:
    r = ctx.last(key, as_of)
    if r is None:
        return "No data yet"
    if (as_of - r[0]).days > STALE_AFTER.get(key, 10):
        return f"Stale (last update {r[0].isoformat()})"
    return None


def _mb(kbbl: float) -> str:
    return f"{kbbl / 1000:.1f}M bbl"


def sig_futures_momentum(ctx: SignalContext, as_of: date):
    lab, grp = "ULSD futures momentum", "Price"
    why = _stale(ctx, "ulsd", as_of)
    if why:
        return _signal("futures_momentum", lab, grp, reason=why)
    c7, c30 = ctx.pct_change("ulsd", as_of, 7), ctx.pct_change("ulsd", as_of, 30)
    if c7 is None:
        return _signal("futures_momentum", lab, grp, reason="Need 7 days of ULSD history")
    c30v = c7 if c30 is None else c30
    scores = {
        "days": clamp(c7 / 0.03, -2, 2),
        "weeks": clamp(c30v / 0.08, -2, 2),
        "months": clamp(c30v / 0.20, -1, 1) * 0.5,
    }
    last = ctx.last("ulsd", as_of)
    detail = f"7d {c7 * 100:+.1f}%" + (f", 30d {c30 * 100:+.1f}%" if c30 is not None else "")
    return _signal("futures_momentum", lab, grp, scores, f"${last[1]:.3f}/gal", detail, as_of=last[0])


def sig_distillate_crack(ctx: SignalContext, as_of: date):
    lab, grp = "Distillate crack (HO - Brent)", "Margins"
    why = _stale(ctx, "ho_crack", as_of)
    if why:
        return _signal("distillate_crack", lab, grp, reason=why)
    d, now = ctx.last("ho_crack", as_of)
    hist = ctx.window("ho_crack", as_of, 365)
    if len(hist) >= MIN_HISTORY:
        pct = percentile_rank(hist, now)
    else:  # absolute fallback: a "normal" HO crack is roughly $25-35/bbl
        pct = 90.0 if now > 50 else 70.0 if now > 35 else 20.0 if now < 20 else 50.0
    prev = ctx.back("ho_crack", as_of, 5)
    chg5 = (now - prev) if prev is not None else 0.0
    if pct >= 95:
        months = -0.5   # extreme margins invite a supply response and demand destruction
    elif pct >= 70:
        months = 0.5
    else:
        months = 0.0
    weeks = 1.5 if pct >= 80 else 0.75 if pct >= 60 else -1.0 if pct <= 20 else -0.5 if pct <= 40 else 0.0
    scores = {"days": clamp(chg5 / 8.0, -2, 2), "weeks": weeks, "months": months}
    return _signal("distillate_crack", lab, grp, scores, f"${now:.1f}/bbl",
                   f"{chg5:+.1f} over 5d; {'percentile vs 1y' if len(hist) >= MIN_HISTORY else 'absolute levels (short history)'}",
                   pct, d)


def sig_curve(ctx: SignalContext, as_of: date):
    lab, grp = "ULSD curve shape", "Curve"
    strip = ctx.curve_at(as_of)
    if len(strip) < 6:
        return _signal("curve_structure", lab, grp, reason="Need the futures curve (run the ULSD Forward Curve scraper)")
    m1, m2, m6 = strip[0][1], strip[1][1], strip[5][1]
    back_pct = (m1 - m6) / m1
    if back_pct >= 0.08:
        scores = {"days": 1.0, "weeks": 0.5, "months": -1.5}
    elif back_pct >= 0.03:
        scores = {"days": 0.5, "weeks": 0.25, "months": -0.75}
    elif back_pct <= -0.02:
        scores = {"days": -0.5, "weeks": -0.25, "months": 0.5}
    else:
        scores = {"days": 0.0, "weeks": 0.0, "months": 0.0}
    shape = "backwardation" if back_pct > 0.005 else "contango" if back_pct < -0.005 else "flat"
    return _signal("curve_structure", lab, grp, scores, f"{back_pct * 100:+.1f}% M1-M6 ({shape})",
                   f"M1 ${m1:.3f}, M2 ${m2:.3f}, M6 ${m6:.3f}. Backwardation means the market expects prices to fade; "
                   f"it also signals tight nearby supply.", as_of=as_of)


def _stocks_signal(ctx: SignalContext, as_of: date, key: str, sig_key: str, label: str, fallback: Optional[str] = None):
    use = key if ctx.has(key) else (fallback if fallback and ctx.has(fallback) else key)
    why = _stale(ctx, use, as_of)
    if why:
        return _signal(sig_key, label, "Inventories", reason=why)
    d, now = ctx.last(use, as_of)
    pool = ctx.seasonal_pool(use, as_of)
    if len(pool) < 8:
        return _signal(sig_key, label, "Inventories", reason="Need ~5 years of weekly history")
    pct = percentile_rank(pool, now)
    avg = sum(pool) / len(pool)
    lin = clamp((50 - pct) / 35.0, -1, 1)
    prev4 = ctx.back(use, as_of, 28, 8)
    trend = 0.0
    chg4 = None
    if prev4:
        chg4 = now / prev4 - 1.0
        trend = clamp(-chg4 / 0.05, -1, 1) * 0.5
    scores = {"days": 0.5 * lin + trend * 0.5, "weeks": 2.0 * lin + trend, "months": 1.5 * lin}
    detail = f"{(now / avg - 1) * 100:+.0f}% vs 5-yr seasonal avg"
    if chg4 is not None:
        detail += f"; {chg4 * 100:+.1f}% over 4 weeks"
    return _signal(sig_key, label, "Inventories", scores, _mb(now), detail, pct, d)


def sig_us_stocks(ctx, as_of):
    return _stocks_signal(ctx, as_of, "us_dist_stocks", "us_stocks", "US distillate stocks")


def sig_ne_stocks(ctx, as_of):
    return _stocks_signal(ctx, as_of, "padd1a_dist_stocks", "northeast_stocks",
                          "New England distillate stocks", fallback="padd1_dist_stocks")


def sig_exports(ctx: SignalContext, as_of: date):
    lab, grp = "Distillate exports", "Supply chain"
    why = _stale(ctx, "dist_exports", as_of)
    if why:
        return _signal("exports", lab, grp, reason=why)
    recent = ctx.window("dist_exports", as_of, 28)
    pool = ctx.window("dist_exports", as_of, 1095)
    if len(pool) < 20 or not recent:
        return _signal("exports", lab, grp, reason="Need ~3 years of weekly history")
    avg4 = sum(recent) / len(recent)
    pct = percentile_rank(pool, avg4)
    x = clamp((pct - 50) / 35.0, -1, 1)
    d = ctx.last("dist_exports", as_of)[0]
    return _signal("exports", lab, grp, {"days": 0.5 * x, "weeks": 1.5 * x, "months": 1.0 * x},
                   f"{avg4 / 1000:.2f}M b/d (4wk)", "High exports pull barrels away from the US East Coast", pct, d)


def sig_refinery_runs(ctx: SignalContext, as_of: date):
    lab, grp = "Refinery utilization", "Supply chain"
    why = _stale(ctx, "refinery_util", as_of)
    if why:
        return _signal("refinery_runs", lab, grp, reason=why)
    d, util = ctx.last("refinery_util", as_of)
    x = clamp((90 - util) / 5.0, -1, 1)
    if x < 0:
        x *= 0.5  # running flat out is only mildly bearish
    return _signal("refinery_runs", lab, grp, {"days": 0.5 * x, "weeks": 1.0 * x, "months": 0.5 * x},
                   f"{util:.1f}%", "Low runs (outages, maintenance) tighten distillate supply", as_of=d)


def sig_demand(ctx: SignalContext, as_of: date):
    lab, grp = "Distillate demand", "Supply chain"
    why = _stale(ctx, "dist_demand", as_of)
    if why:
        return _signal("demand", lab, grp, reason=why)
    recent = ctx.window("dist_demand", as_of, 28)
    pool = ctx.seasonal_pool("dist_demand", as_of)
    if len(pool) < 8 or not recent:
        return _signal("demand", lab, grp, reason="Need ~5 years of weekly history")
    avg4 = sum(recent) / len(recent)
    pct = percentile_rank(pool, avg4)
    x = clamp((pct - 50) / 35.0, -1, 1)
    d = ctx.last("dist_demand", as_of)[0]
    return _signal("demand", lab, grp, {"weeks": 1.0 * x, "months": 0.5 * x},
                   f"{avg4 / 1000:.2f}M b/d (4wk)", "Implied product supplied vs same season", pct, d)


def sig_arb(ctx: SignalContext, as_of: date):
    lab, grp = "Transatlantic arbitrage", "Supply chain"
    why = _stale(ctx, "arb", as_of)
    if why:
        return _signal("transatlantic_arb", lab, grp, reason=why)
    d, arb = ctx.last("arb", as_of)
    s = 1.5 if arb > 0.12 else 0.75 if arb > 0.04 else -1.0 if arb < -0.08 else -0.5 if arb < -0.02 else 0.0
    gc = ctx.value_at("gasoil_crack", as_of, 6)
    detail = "ICE gasoil minus NYH ULSD. A premium pulls US barrels to Europe."
    if gc is not None:
        detail += f" ICE gasoil crack ${gc:.1f}/bbl."
    return _signal("transatlantic_arb", lab, grp, {"days": 0.5 * s, "weeks": s, "months": 0.5 * s},
                   f"{arb * 100:+.1f}c/gal", detail, as_of=d)


def sig_positioning(ctx: SignalContext, as_of: date):
    lab, grp = "Speculative positioning", "Positioning"
    key = "cot_ulsd_mm_net_pct"
    why = _stale(ctx, key, as_of)
    if why:
        return _signal("positioning", lab, grp, reason=why)
    d, now = ctx.last(key, as_of)
    pool = ctx.window(key, as_of, 1460)
    if len(pool) < 40:
        return _signal("positioning", lab, grp, reason="Need ~1 year of COT history")
    pct = percentile_rank(pool, now)
    prev = ctx.back(key, as_of, 28, 8)
    mom = clamp(((now - prev) if prev is not None else 0.0) / 6.0, -1, 1) * 0.5
    if pct >= 85:      # crowded long: vulnerable to liquidation
        scores = {"days": -1.0, "weeks": -0.5, "months": 0.0}
    elif pct <= 15:    # washed out: short-covering risk
        scores = {"days": 1.0, "weeks": 0.5, "months": 0.0}
    else:
        scores = {"days": mom, "weeks": mom, "months": 0.0}
    return _signal("positioning", lab, grp, scores, f"{now:+.1f}% of OI (managed money net)",
                   "Crowded longs raise the risk of sharp liquidation drops; washed-out shorts raise squeeze risk",
                   pct, d)


def sig_weather(ctx: SignalContext, as_of: date):
    lab, grp = "Weather / HDD forecast", "Demand"
    why = _stale(ctx, "hdd_dev_7d_pct", as_of)
    if why:
        return _signal("weather_hdd", lab, grp, reason=why)
    d, dev7 = ctx.last("hdd_dev_7d_pct", as_of)
    norm7 = ctx.value_at("hdd_norm_7d", as_of, 4)
    if norm7 is not None and norm7 < 40:
        return _signal("weather_hdd", lab, grp, reason="Off-season (little heating demand)")
    dev15 = ctx.value_at("hdd_dev_15d_pct", as_of, 4)
    d15 = dev7 if dev15 is None else dev15
    scores = {"days": clamp(dev7 / 12.0, -2, 2), "weeks": clamp(d15 / 15.0, -1.5, 1.5)}
    return _signal("weather_hdd", lab, grp, scores, f"{dev7:+.0f}% HDD vs normal (7d)",
                   f"15-day outlook {d15:+.0f}% vs 5-year normal; colder = more heating demand", as_of=d)


def sig_enso(ctx: SignalContext, as_of: date):
    lab, grp = "Winter outlook (ENSO)", "Demand"
    why = _stale(ctx, "enso_oni", as_of)
    if why:
        return _signal("enso", lab, grp, reason=why)
    d, oni = ctx.last("enso_oni", as_of)
    m = -1.0 if oni >= 1.5 else -0.5 if oni >= 0.5 else 1.0 if oni <= -1.0 else 0.5 if oni <= -0.5 else 0.0
    phase = "El Nino" if oni >= 0.5 else "La Nina" if oni <= -0.5 else "neutral"
    return _signal("enso", lab, grp, {"weeks": 0.5 * m, "months": m}, f"ONI {oni:+.1f} ({phase})",
                   "El Nino winters tend to be milder in the Northeast; La Nina colder. The effect is modest.", as_of=d)


def sig_retail(ctx: SignalContext, as_of: date):
    lab, grp = "Retail pass-through", "Price"
    key = "retail_margin"
    why = _stale(ctx, key, as_of) if ctx.has(key) else "No retail or wholesale overlap yet"
    if why:
        return _signal("retail_passthrough", lab, grp, reason=why)
    d, now = ctx.last(key, as_of)
    pool = ctx.window(key, as_of, 365)
    if len(pool) < MIN_HISTORY:
        return _signal("retail_passthrough", lab, grp, reason="Need ~30 days of retail + futures overlap")
    norm = median(pool)
    x = clamp((norm - now) / 0.25, -1, 1)
    return _signal("retail_passthrough", lab, grp, {"days": 1.5 * x, "weeks": 1.5 * x},
                   f"${now:.2f} margin vs ${norm:.2f} typical",
                   "Retail margin over ULSD. Below typical = retail hasn't caught up with wholesale; above = room to fall.",
                   percentile_rank(pool, now), d)


def sig_substitutes(ctx: SignalContext, as_of: date):
    lab, grp = "Substitute fuels", "Demand"
    changes = [c for c in (ctx.pct_change("henry_hub", as_of, 30), ctx.pct_change("propane_mb", as_of, 30)) if c is not None]
    if not changes:
        return _signal("substitutes", lab, grp, reason="No natural gas / propane data yet")
    avg = sum(changes) / len(changes)
    x = clamp(avg / 0.20, -1, 1)
    hh = ctx.last("henry_hub", as_of)
    return _signal("substitutes", lab, grp, {"days": 0.25 * x, "weeks": 0.5 * x, "months": 0.5 * x},
                   f"{avg * 100:+.0f}% (30d gas/propane)",
                   "Rising gas/propane prices make heating oil relatively cheaper and reduce fuel switching"
                   + (f". Henry Hub ${hh[1]:.2f}" if hh else ""), as_of=hh[0] if hh else as_of)


def sig_events(ctx: SignalContext, as_of: date, live: bool = True):
    lab, grp = "Geopolitical events", "Events"
    events = ctx.active_events(as_of, live)
    if not events:
        return _signal("events", lab, grp, reason="No active events logged. Add supply disruptions or diplomacy news.")
    scores = {}
    for h in HORIZONS:
        total = sum(e.direction * e.magnitude * 0.7 for e in events if e.horizon in (h, "all"))
        scores[h] = clamp(total, -2, 2)
    names = "; ".join(f"{'+' if e.direction > 0 else '-' if e.direction < 0 else '='}{e.title}" for e in events[:4])
    return _signal("events", lab, grp, scores, f"{len(events)} active", names, as_of=as_of)


SIGNAL_FUNCS = [
    sig_futures_momentum, sig_distillate_crack, sig_curve, sig_us_stocks, sig_ne_stocks, sig_exports,
    sig_refinery_runs, sig_demand, sig_arb, sig_positioning, sig_weather, sig_enso, sig_retail,
    sig_substitutes, sig_events,
]


def compute_signals(ctx: SignalContext, as_of: date, live: bool = True) -> List[Dict[str, Any]]:
    out = []
    for fn in SIGNAL_FUNCS:
        out.append(fn(ctx, as_of, live) if fn is sig_events else fn(ctx, as_of))
    return out


# ----------------------------------------------------------------------------- combination

def label_for(avg: float) -> str:
    if avg >= 1.0:
        return "Rise Likely"
    if avg >= 0.35:
        return "Slight Upward Pressure"
    if avg <= -1.0:
        return "Fall Likely"
    if avg <= -0.35:
        return "Slight Downward Pressure"
    return "Stable"


def combine(signals: List[Dict[str, Any]], horizon: str) -> Dict[str, Any]:
    used, total_w = [], 0.0
    for s in signals:
        w = WEIGHTS.get(s["key"], {}).get(horizon, 0.0)
        total_w += w
        sc = s["scores"].get(horizon)
        if s["available"] and sc is not None and w > 0:
            used.append((s, w, sc))
    den = sum(w for _, w, _ in used)
    if not used or den == 0:
        return {"horizon": horizon, "horizon_label": HORIZON_LABELS[horizon], "score": None,
                "outlook": "Insufficient data", "confidence": "Low", "coverage": 0.0,
                "drivers": [], "headwinds": []}
    avg = sum(w * sc for _, w, sc in used) / den
    coverage = den / total_w if total_w else 0.0
    mad = sum(w * abs(sc - avg) for _, w, sc in used) / den
    agreement = clamp(1.0 - mad / 2.0, 0.0, 1.0)
    conf_score = 0.5 * coverage + 0.5 * agreement
    confidence = "High" if conf_score >= 0.7 else "Moderate" if conf_score >= 0.5 else "Low"

    contrib = sorted(((w * sc, s) for s, w, sc in used), key=lambda t: -abs(t[0]))
    sign = 1 if avg >= 0 else -1
    drivers = [{"key": s["key"], "label": s["label"], "score": s["scores"][horizon], "display": s["display"]}
               for c, s in contrib if c * sign > 0][:3]
    headwinds = [{"key": s["key"], "label": s["label"], "score": s["scores"][horizon], "display": s["display"]}
                 for c, s in contrib if c * sign < 0][:2]
    return {
        "horizon": horizon, "horizon_label": HORIZON_LABELS[horizon],
        "score": round(avg, 2), "outlook": label_for(avg), "confidence": confidence,
        "coverage": round(coverage, 2), "agreement": round(agreement, 2),
        "signals_used": len(used), "drivers": drivers, "headwinds": headwinds,
    }


def volatility_range(ctx: SignalContext, as_of: date) -> Dict[str, Any]:
    """1-sigma ULSD price range per horizon from recent realized volatility (not a forecast)."""
    r = ctx.last("ulsd", as_of, STALE_AFTER["ulsd"])
    vals = ctx.window("ulsd", as_of, 45)
    if not r or len(vals) < 10:
        return {}
    rets = [log(b / a) for a, b in zip(vals, vals[1:]) if a > 0 and b > 0]
    if len(rets) < 8:
        return {}
    sigma = pstdev(rets[-30:])
    out = {"price": round(r[1], 3), "daily_sigma_pct": round(sigma * 100, 2), "ranges": {}}
    for h in HORIZONS:
        span = sigma * sqrt(HORIZON_TRADING_DAYS[h])
        out["ranges"][h] = {"low": round(r[1] * exp(-span), 3), "high": round(r[1] * exp(span), 3)}
    return out


def narrative(result: Dict[str, Any]) -> str:
    if result["score"] is None:
        return "Not enough market data yet. Set up the market data feeds to enable this horizon."
    txt = f"{result['outlook']} ({result['confidence'].lower()} confidence)."
    if result["drivers"]:
        txt += " Driven by " + ", ".join(d["label"].lower() for d in result["drivers"]) + "."
    if result["headwinds"]:
        txt += " Working against: " + ", ".join(h["label"].lower() for h in result["headwinds"]) + "."
    return txt


def compute_outlook(db: Session, as_of: Optional[date] = None, ctx: Optional[SignalContext] = None) -> Dict[str, Any]:
    as_of = as_of or date.today()
    ctx = ctx or SignalContext(db)
    signals = compute_signals(ctx, as_of, live=True)
    horizons = {}
    for h in HORIZONS:
        res = combine(signals, h)
        res["summary"] = narrative(res)
        horizons[h] = res
    available = sum(1 for s in signals if s["available"])
    return {
        "as_of": as_of.isoformat(),
        "horizons": horizons,
        "signals": signals,
        "volatility": volatility_range(ctx, as_of),
        "unavailable": [{"key": s["key"], "label": s["label"], "reason": s["reason"]}
                        for s in signals if not s["available"]],
        "signals_available": available,
        "signals_total": len(signals),
    }


# ----------------------------------------------------------------------------- weekly changes

def metric_snapshot(ctx: SignalContext, as_of: date) -> Dict[str, Optional[float]]:
    strip = ctx.curve_at(as_of)
    return {
        "ulsd": ctx.value_at("ulsd", as_of, 6),
        "brent": ctx.value_at("brent", as_of, 6),
        "ho_crack": ctx.value_at("ho_crack", as_of, 6),
        "backwardation": ((strip[0][1] - strip[5][1]) / strip[0][1] * 100) if len(strip) >= 6 else None,
        "us_stocks": ctx.value_at("us_dist_stocks", as_of, 14),
        "ne_stocks": ctx.value_at("padd1a_dist_stocks", as_of, 14),
        "exports": ctx.value_at("dist_exports", as_of, 14),
        "mm_net": ctx.value_at("cot_ulsd_mm_net_pct", as_of, 14),
        "retail": ctx.value_at("retail", as_of, 10),
    }


WEEKLY_META = [
    ("ulsd", "ULSD futures", "$/gal", 3, True),
    ("brent", "Brent", "$/bbl", 2, True),
    ("ho_crack", "Distillate crack", "$/bbl", 1, True),
    ("backwardation", "Curve backwardation (M1-M6)", "%", 1, True),
    ("us_stocks", "US distillate stocks", "kbbl", 0, False),
    ("ne_stocks", "New England stocks", "kbbl", 0, False),
    ("exports", "Distillate exports", "kb/d", 0, True),
    ("mm_net", "Managed-money net (ULSD)", "% OI", 1, True),
    ("retail", "Local retail average", "$/gal", 3, True),
]


def weekly_changes(ctx: SignalContext) -> List[Dict[str, Any]]:
    now = metric_snapshot(ctx, ctx.today)
    then = metric_snapshot(ctx, ctx.today - timedelta(days=7))
    out = []
    for key, label, unit, dp, up_is_bullish in WEEKLY_META:
        a, b = now.get(key), then.get(key)
        if a is None:
            continue
        delta = None if b is None else a - b
        # For stocks, a draw (negative delta) is bullish for prices.
        bullish = None if delta is None or delta == 0 else (delta > 0) == up_is_bullish
        out.append({"key": key, "label": label, "unit": unit, "decimals": dp,
                    "now": round(a, 4), "prev": None if b is None else round(b, 4),
                    "delta": None if delta is None else round(delta, 4), "bullish": bullish})
    return out


# ----------------------------------------------------------------------------- backtest

def _pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 5:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = sqrt(sum((x - mx) ** 2 for x in xs))
    sy = sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def backtest(db: Session, days: int = 365, step: int = 7) -> Dict[str, Any]:
    """
    Walk back through history, recompute the signals as they would have looked on each date and
    compare with the realized ULSD move over each horizon. Only signals whose inputs existed on
    that date contribute, so results improve as feeds accumulate history.
    """
    ctx = SignalContext(db)
    if not ctx.has("ulsd"):
        return {"error": "No ULSD price history available", "horizons": {}}
    last_px = ctx.last("ulsd", ctx.today)
    results: Dict[str, Any] = {}
    per_signal: Dict[str, Dict[str, Dict[str, List[float]]]] = defaultdict(lambda: defaultdict(lambda: {"x": [], "y": []}))
    start = ctx.today - timedelta(days=days)

    for h in HORIZONS:
        horizon_days = HORIZON_CALENDAR_DAYS[h]
        rows = []
        d = start
        while d <= ctx.today - timedelta(days=horizon_days):
            p0 = ctx.value_at("ulsd", d, 4)
            p1 = ctx.value_at("ulsd", d + timedelta(days=horizon_days), 4)
            if p0 and p1:
                signals = compute_signals(ctx, d, live=False)
                res = combine(signals, h)
                if res["score"] is not None:
                    realized = p1 / p0 - 1.0
                    rows.append((d, res["score"], realized, res["confidence"]))
                    for s in signals:
                        sc = s["scores"].get(h)
                        if s["available"] and sc is not None and WEIGHTS.get(s["key"], {}).get(h, 0) > 0:
                            per_signal[h][s["key"]]["x"].append(sc)
                            per_signal[h][s["key"]]["y"].append(realized)
            d += timedelta(days=step)

        directional = [(sc, r) for _, sc, r, _ in rows if abs(sc) >= 0.35]
        hits = sum(1 for sc, r in directional if (sc > 0) == (r > 0))
        up = [r for _, sc, r, _ in rows if sc >= 0.35]
        down = [r for _, sc, r, _ in rows if sc <= -0.35]
        flat = [r for _, sc, r, _ in rows if -0.35 < sc < 0.35]
        avg = lambda v: round(sum(v) / len(v) * 100, 2) if v else None  # noqa: E731
        results[h] = {
            "horizon_label": HORIZON_LABELS[h],
            "samples": len(rows),
            "directional_calls": len(directional),
            "hit_rate": round(hits / len(directional) * 100, 1) if directional else None,
            "correlation": None if _pearson([r[1] for r in rows], [r[2] for r in rows]) is None
            else round(_pearson([r[1] for r in rows], [r[2] for r in rows]), 2),
            "avg_move_when_bullish_pct": avg(up), "avg_move_when_bearish_pct": avg(down),
            "avg_move_when_stable_pct": avg(flat),
            "signals": sorted([
                {"key": k, "samples": len(v["x"]),
                 "correlation": None if _pearson(v["x"], v["y"]) is None else round(_pearson(v["x"], v["y"]), 2),
                 "hit_rate": round(sum(1 for x, y in zip(v["x"], v["y"]) if abs(x) >= 0.25 and (x > 0) == (y > 0)) /
                                   max(1, sum(1 for x in v["x"] if abs(x) >= 0.25)) * 100, 1)}
                for k, v in per_signal[h].items()
            ], key=lambda r: -(r["correlation"] or -9)),
        }
    return {
        "window_days": days, "step_days": step,
        "latest_price_date": last_px[0].isoformat() if last_px else None,
        "caveat": "Small samples and a regime-driven market make these figures indicative only. "
                  "Weather, positioning and events only count where their history exists.",
        "horizons": results,
    }
