from datetime import date, timedelta
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MarketEvent, MarketIndicator, ScrapeConfig
from app.models.scrape_config import ScheduleType
from app.services import market_signals as ms

router = APIRouter()


# ------------------------------------------------------------------ outlook / signals

@router.get("/signals")
async def get_signals(db: Session = Depends(get_db)):
    """Outlook for the next days / weeks / months with every contributing signal."""
    return ms.compute_outlook(db)


@router.get("/weekly-changes")
async def get_weekly_changes(db: Session = Depends(get_db)):
    """Key market metrics now vs 7 days ago."""
    return ms.weekly_changes(ms.SignalContext(db))


@router.get("/backtest")
async def get_backtest(
    days: int = Query(365, ge=60, le=1800),
    step: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """How the signal model would have scored vs realized ULSD moves over past dates."""
    return ms.backtest(db, days=days, step=step)


# ------------------------------------------------------------------ charts

def _in_range(dates: List[date], date_from: date, date_to: date) -> List[date]:
    return [d for d in dates if date_from <= d <= date_to]


@router.get("/charts/crack")
async def crack_chart(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Distillate cracks in $/bbl: NYMEX HO vs Brent and ICE gasoil vs Brent."""
    date_to = date_to or date.today()
    date_from = date_from or date_to - timedelta(days=180)
    ctx = ms.SignalContext(db)
    series = {k: dict(zip(*ctx.s[k])) for k in ("ho_crack", "gasoil_crack") if k in ctx.s}
    dates = sorted({d for s in series.values() for d in s if date_from <= d <= date_to})
    return {
        "dates": [d.isoformat() for d in dates],
        "ho_crack": [series.get("ho_crack", {}).get(d) for d in dates],
        "gasoil_crack": [series.get("gasoil_crack", {}).get(d) for d in dates],
    }


@router.get("/charts/curve")
async def curve_chart(db: Session = Depends(get_db)):
    """ULSD forward curve today vs 30 and 90 days ago, by delivery month."""
    ctx = ms.SignalContext(db)
    curves = []
    for label, back in (("Today", 0), ("30 days ago", 30), ("90 days ago", 90)):
        as_of = ctx.today - timedelta(days=back)
        strip = ctx.curve_at(as_of)
        if strip:
            curves.append({
                "label": label, "as_of": as_of.isoformat(),
                "points": [{"month": f"{ym // 100}-{ym % 100:02d}", "price": round(p, 4)} for ym, p in strip],
            })
    months = sorted({pt["month"] for c in curves for pt in c["points"]})
    return {"months": months, "curves": curves}


@router.get("/charts/stocks")
async def stocks_chart(
    series: Literal["padd1a", "padd1", "us"] = "padd1a",
    weeks: int = Query(52, ge=8, le=156),
    db: Session = Depends(get_db),
):
    """Weekly distillate stocks with the 5-year seasonal min/avg/max band."""
    key = {"padd1a": "padd1a_dist_stocks", "padd1": "padd1_dist_stocks", "us": "us_dist_stocks"}[series]
    ctx = ms.SignalContext(db)
    if key not in ctx.s:
        return {"series": series, "dates": [], "stocks": [], "band_min": [], "band_avg": [], "band_max": []}
    dates, vals = ctx.s[key]
    cutoff = ctx.today - timedelta(weeks=weeks)
    out = {"series": series, "dates": [], "stocks": [], "band_min": [], "band_avg": [], "band_max": []}
    for d, v in zip(dates, vals):
        if d < cutoff:
            continue
        pool = ctx.seasonal_pool(key, d, years=5, window=7)
        out["dates"].append(d.isoformat())
        out["stocks"].append(v)
        out["band_min"].append(min(pool) if pool else None)
        out["band_avg"].append(sum(pool) / len(pool) if pool else None)
        out["band_max"].append(max(pool) if pool else None)
    return out


# ------------------------------------------------------------------ feeds / setup

FEEDS = [
    {"scraper_type": "eia_market_data", "name": "EIA Market Fundamentals", "url": "https://api.eia.gov/v2/",
     "schedule_type": ScheduleType.DAILY, "schedule_value": "12:30",
     "prefixes": ["us_dist_stocks", "padd1_dist_stocks", "padd1a_dist_stocks", "refinery_util", "dist_production",
                  "dist_demand", "dist_exports", "ma_retail_ho", "henry_hub", "propane_mb"],
     "needs": "EIA_API_KEY"},
    {"scraper_type": "cftc_cot", "name": "CFTC Positioning", "url": "https://publicreporting.cftc.gov/",
     "schedule_type": ScheduleType.DAILY, "schedule_value": "16:30",
     "prefixes": ["cot_ulsd_mm_net_pct", "cot_wti_mm_net_pct"], "needs": None},
    {"scraper_type": "futures_curve", "name": "ULSD Forward Curve", "url": "https://finance.yahoo.com/quote/HO=F",
     "schedule_type": ScheduleType.INTERVAL, "schedule_value": "4",
     "prefixes": ["ho_fut:", "gasoil_front_usd_t"], "needs": None},
    {"scraper_type": "weather_forecast", "name": "HDD Forecast & ENSO", "url": "https://open-meteo.com/",
     "schedule_type": ScheduleType.INTERVAL, "schedule_value": "6",
     "prefixes": ["hdd_fcst_7d", "hdd_dev_7d_pct", "enso_oni"], "needs": None},
]


@router.get("/feeds")
async def feed_status(db: Session = Depends(get_db)):
    """Which market-intel feeds are configured and how fresh their data is."""
    latest = dict(db.query(MarketIndicator.series_key, func.max(MarketIndicator.obs_date))
                  .group_by(MarketIndicator.series_key).all())
    configs = {c.scraper_type: c for c in db.query(ScrapeConfig).all()}
    out = []
    for f in FEEDS:
        cfg = configs.get(f["scraper_type"])
        series = []
        for p in f["prefixes"]:
            dates = [d for k, d in latest.items() if k == p or (p.endswith(":") and k.startswith(p))]
            series.append({"key": p.rstrip(":"), "latest": max(dates).isoformat() if dates else None})
        out.append({
            "scraper_type": f["scraper_type"], "name": f["name"], "needs": f["needs"],
            "config_id": cfg.id if cfg else None, "configured": cfg is not None,
            "enabled": bool(cfg.enabled) if cfg else False,
            "last_run": cfg.last_run.isoformat() if cfg and cfg.last_run else None,
            "series": series,
        })
    return out


@router.post("/setup")
async def setup_feeds(db: Session = Depends(get_db)):
    """Create the scrape configs for the market-intel feeds if they don't exist yet."""
    existing = {c.scraper_type for c in db.query(ScrapeConfig).all()}
    existing_names = {c.name for c in db.query(ScrapeConfig).all()}
    result = []
    for f in FEEDS:
        if f["scraper_type"] in existing:
            cfg = db.query(ScrapeConfig).filter(ScrapeConfig.scraper_type == f["scraper_type"]).first()
            result.append({"scraper_type": f["scraper_type"], "config_id": cfg.id, "created": False})
            continue
        name = f["name"] if f["name"] not in existing_names else f"{f['name']} (market intel)"
        cfg = ScrapeConfig(name=name, scraper_type=f["scraper_type"], url=f["url"], enabled=True,
                           schedule_type=f["schedule_type"], schedule_value=f["schedule_value"])
        db.add(cfg)
        db.flush()
        result.append({"scraper_type": f["scraper_type"], "config_id": cfg.id, "created": True})
    db.commit()
    return result


# ------------------------------------------------------------------ manual curve import

class CurveRow(BaseModel):
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="Delivery month, YYYY-MM")
    price: float = Field(..., gt=0, lt=50, description="USD per gallon")


class CurveImport(BaseModel):
    as_of: Optional[date] = None
    rows: List[CurveRow] = Field(..., min_length=1, max_length=36)
    gasoil_usd_per_tonne: Optional[float] = Field(None, gt=0, lt=10000)


@router.post("/curve/import")
async def import_curve(payload: CurveImport, db: Session = Depends(get_db)):
    """
    Load a ULSD forward curve by hand (e.g. from a supplier's daily market email) when the
    automatic feed is unavailable. Optionally include the ICE gasoil front month in USD/tonne.
    """
    from app.services.market_indicators import upsert_indicator_rows
    as_of = payload.as_of or date.today()
    if as_of > date.today():
        raise HTTPException(status_code=400, detail="as_of cannot be in the future")
    changed = 0
    for r in payload.rows:
        year, month = int(r.month[:4]), int(r.month[5:])
        if not 1 <= month <= 12:
            raise HTTPException(status_code=400, detail=f"Invalid month: {r.month}")
        changed += upsert_indicator_rows(db, f"ho_fut:{year}{month:02d}", [(as_of, r.price)],
                                         unit="usd/gal", source="manual", label=f"manual {r.month}")
    if payload.gasoil_usd_per_tonne:
        changed += upsert_indicator_rows(db, "gasoil_front_usd_t", [(as_of, payload.gasoil_usd_per_tonne)],
                                         unit="usd/t", source="manual")
    db.commit()
    return {"as_of": as_of.isoformat(), "rows_changed": changed}


# ------------------------------------------------------------------ events

class EventIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = Field("other", max_length=64)
    direction: int = Field(1, ge=-1, le=1)
    magnitude: int = Field(1, ge=1, le=3)
    horizon: Literal["days", "weeks", "months", "all"] = "all"
    start_date: Optional[date] = None
    expires_on: Optional[date] = None
    active: bool = True
    notes: Optional[str] = None


def _event_dict(e: MarketEvent) -> Dict:
    return {
        "id": e.id, "title": e.title, "category": e.category, "direction": e.direction,
        "magnitude": e.magnitude, "horizon": e.horizon,
        "start_date": e.start_date.isoformat() if e.start_date else None,
        "expires_on": e.expires_on.isoformat() if e.expires_on else None,
        "active": e.active, "notes": e.notes,
    }


@router.get("/events")
async def list_events(include_inactive: bool = False, db: Session = Depends(get_db)):
    q = db.query(MarketEvent)
    if not include_inactive:
        today = date.today()
        q = q.filter(MarketEvent.active == True,  # noqa: E712
                     (MarketEvent.expires_on.is_(None)) | (MarketEvent.expires_on >= today))
    return [_event_dict(e) for e in q.order_by(MarketEvent.start_date.desc(), MarketEvent.id.desc()).all()]


@router.post("/events")
async def create_event(payload: EventIn, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["start_date"] = data["start_date"] or date.today()
    e = MarketEvent(**data)
    db.add(e)
    db.commit()
    db.refresh(e)
    return _event_dict(e)


@router.put("/events/{event_id}")
async def update_event(event_id: int, payload: EventIn, db: Session = Depends(get_db)):
    e = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    for k, v in payload.model_dump().items():
        if k == "start_date" and v is None:
            continue
        setattr(e, k, v)
    db.commit()
    db.refresh(e)
    return _event_dict(e)


@router.delete("/events/{event_id}")
async def delete_event(event_id: int, db: Session = Depends(get_db)):
    e = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(e)
    db.commit()
    return {"deleted": event_id}
