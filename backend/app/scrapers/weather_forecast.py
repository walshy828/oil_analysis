import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.models import Location
from app.scrapers.base import BaseScraper
from app.services.market_indicators import upsert_indicator_rows

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"

# Central Massachusetts (Worcester) when no location has coordinates
DEFAULT_COORDS = (42.2626, -71.8023)
HDD_BASE_F = 65.0
NORMAL_YEARS = 5

# 3-month ONI season -> centre month
SEASON_CENTRE = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
                 "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}


def _hdd(hi: Optional[float], lo: Optional[float]) -> Optional[float]:
    if hi is None or lo is None:
        return None
    return max(0.0, HDD_BASE_F - (hi + lo) / 2.0)


class WeatherForecastScraper(BaseScraper):
    """
    15-day heating-degree-day forecast vs a 5-year normal for the home location, plus the
    latest ONI (ENSO) value. Open-Meteo is used for the forecast (16 days, no API key);
    ONI comes from NOAA CPC.
    """

    @classmethod
    def get_scraper_type(cls) -> str:
        return "weather_forecast"

    @classmethod
    def get_description(cls) -> str:
        return "15-day HDD forecast vs 5-year normal and NOAA ENSO (ONI) index"

    def _coords(self, db: Session) -> Tuple[float, float]:
        loc = db.query(Location).filter(
            Location.latitude.isnot(None), Location.longitude.isnot(None)
        ).first()
        return (loc.latitude, loc.longitude) if loc else DEFAULT_COORDS

    async def _daily(self, client: httpx.AsyncClient, url: str, lat: float, lon: float,
                     start: Optional[date] = None, end: Optional[date] = None) -> List[Tuple[date, Optional[float]]]:
        params = {
            "latitude": lat, "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min",
            "temperature_unit": "fahrenheit", "timezone": "America/New_York",
        }
        if start and end:
            params["start_date"], params["end_date"] = start.isoformat(), end.isoformat()
        else:
            params["forecast_days"] = 16
        resp = await client.get(url, params=params, timeout=30.0)
        resp.raise_for_status()
        daily = resp.json().get("daily", {})
        dates = daily.get("time", [])
        his, los = daily.get("temperature_2m_max", []), daily.get("temperature_2m_min", [])
        return [(date.fromisoformat(d), _hdd(his[i], los[i])) for i, d in enumerate(dates)]

    async def _scrape_hdd(self, client, db, snapshot_id, scraped_at) -> Dict[str, Any]:
        lat, lon = self._coords(db)
        today = date.today()
        fcst = await self._daily(client, FORECAST_URL, lat, lon)
        fcst = [(d, h) for d, h in fcst if d >= today and h is not None][:15]
        if len(fcst) < 7:
            return {"series": "hdd_forecast", "status": "no_data"}

        # Normal: same calendar window averaged over previous years
        normals: Dict[int, List[float]] = {}
        for yr_back in range(1, NORMAL_YEARS + 1):
            try:
                s = today.replace(year=today.year - yr_back)
            except ValueError:  # Feb 29
                s = (today - timedelta(days=1)).replace(year=today.year - yr_back)
            hist = await self._daily(client, ARCHIVE_URL, lat, lon, s, s + timedelta(days=len(fcst) - 1))
            for i, (_, h) in enumerate(hist):
                if h is not None:
                    normals.setdefault(i, []).append(h)

        def window(n: int) -> Tuple[float, float]:
            f = sum(h for _, h in fcst[:n])
            nrm = sum(sum(normals[i]) / len(normals[i]) for i in range(min(n, len(fcst))) if normals.get(i))
            return f, nrm

        out: Dict[str, Any] = {"series": "hdd_forecast"}
        for n in (7, 15):
            if len(fcst) < n:
                continue
            f, nrm = window(n)
            upsert_indicator_rows(db, f"hdd_fcst_{n}d", [(today, f)], unit="hdd", source="Open-Meteo",
                                  snapshot_id=snapshot_id, scraped_at=scraped_at)
            upsert_indicator_rows(db, f"hdd_norm_{n}d", [(today, nrm)], unit="hdd", source="Open-Meteo",
                                  snapshot_id=snapshot_id, scraped_at=scraped_at)
            if nrm > 0:
                dev = (f - nrm) / nrm * 100.0
                upsert_indicator_rows(db, f"hdd_dev_{n}d_pct", [(today, dev)], unit="pct", source="Open-Meteo",
                                      snapshot_id=snapshot_id, scraped_at=scraped_at)
                out[f"dev_{n}d_pct"] = round(dev, 1)
        return out

    async def _scrape_oni(self, client, db, snapshot_id, scraped_at) -> Dict[str, Any]:
        resp = await client.get(ONI_URL, timeout=20.0)
        resp.raise_for_status()
        rows = []
        for line in resp.text.splitlines():
            parts = line.split()
            if len(parts) < 4 or parts[0] not in SEASON_CENTRE:
                continue
            try:
                rows.append((date(int(parts[1]), SEASON_CENTRE[parts[0]], 1), float(parts[3])))
            except ValueError:
                continue
        rows = rows[-48:]
        if not rows:
            return {"series": "enso_oni", "status": "no_data"}
        upsert_indicator_rows(db, "enso_oni", rows, unit="degC", source="NOAA CPC",
                              snapshot_id=snapshot_id, scraped_at=scraped_at)
        return {"series": "enso_oni", "latest_date": rows[-1][0].isoformat(), "latest": rows[-1][1]}

    async def scrape(self, db: Session, snapshot_id: str = None, scraped_at: datetime = None) -> List[Dict[str, Any]]:
        summary = []
        async with httpx.AsyncClient() as client:
            for fn in (self._scrape_hdd, self._scrape_oni):
                try:
                    summary.append(await fn(client, db, snapshot_id, scraped_at))
                except Exception as e:
                    logger.warning("%s failed: %s", fn.__name__, e)
                    summary.append({"series": fn.__name__, "status": "error", "error": str(e)})
            db.commit()
        return summary
