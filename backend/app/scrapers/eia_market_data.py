import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.scrapers.base import BaseScraper
from app.services.market_indicators import upsert_indicator_rows

logger = logging.getLogger(__name__)

EIA_BASE = "https://api.eia.gov/v2/"

# series_key -> (frequency, unit, [(route, series_id), ...] tried in order, history rows)
# Several candidates are listed where EIA exposes the same series under more than one route.
INDICATORS: Dict[str, Dict[str, Any]] = {
    # Distillate inventories (thousand barrels)
    "us_dist_stocks": {
        "freq": "weekly", "unit": "kbbl", "length": 330,
        "candidates": [("petroleum/stoc/wstk", "WDISTUS1")],
    },
    "padd1_dist_stocks": {
        "freq": "weekly", "unit": "kbbl", "length": 330,
        "candidates": [("petroleum/stoc/wstk", "W_EPD0_SAE_R10_MBBL")],
    },
    "padd1a_dist_stocks": {
        "freq": "weekly", "unit": "kbbl", "length": 330,
        "candidates": [("petroleum/stoc/wstk", "W_EPD0_SAE_R1X_MBBL")],
    },
    # Weekly supply/demand balance
    "refinery_util": {
        "freq": "weekly", "unit": "pct", "length": 330,
        "candidates": [("petroleum/sum/sndw", "WPULEUS3")],
    },
    "dist_production": {
        "freq": "weekly", "unit": "kb/d", "length": 330,
        "candidates": [("petroleum/sum/sndw", "WDIRPUS2")],
    },
    "dist_demand": {
        "freq": "weekly", "unit": "kb/d", "length": 330,
        "candidates": [("petroleum/sum/sndw", "WDIUPUS2"), ("petroleum/cons/wpsup", "WDIUPUS2")],
    },
    "dist_exports": {
        "freq": "weekly", "unit": "kb/d", "length": 330,
        "candidates": [("petroleum/sum/sndw", "WDIEXUS2"), ("petroleum/move/wkly", "W_EPD0_EEX_NUS-Z00_MBBLD")],
    },
    # Retail pass-through: Massachusetts residential heating oil ($/gal)
    "ma_retail_ho": {
        "freq": "weekly", "unit": "usd/gal", "length": 260,
        "candidates": [("petroleum/pri/wfr", "W_EPD2F_PRS_SMA_DPG")],
    },
    # Substitute fuels
    "henry_hub": {
        "freq": "daily", "unit": "usd/mmbtu", "length": 500,
        "candidates": [("natural-gas/pri/fut", "RNGWHHD")],
    },
    "propane_mb": {
        "freq": "daily", "unit": "usd/gal", "length": 500,
        "candidates": [("petroleum/pri/spt", "EER_EPLLPA_PF4_Y44MB_DPG")],
    },
}


class EiaMarketDataScraper(BaseScraper):
    """
    Weekly EIA fundamentals for the Market Intel signal model: distillate stocks
    (US / PADD 1 / New England), refinery utilization, distillate production, demand and
    exports, Massachusetts retail heating oil, Henry Hub gas and Mont Belvieu propane.
    """

    @classmethod
    def get_scraper_type(cls) -> str:
        return "eia_market_data"

    @classmethod
    def get_description(cls) -> str:
        return "EIA distillate inventories, exports, refinery utilization, MA retail heating oil, natural gas and propane"

    async def _fetch(self, client: httpx.AsyncClient, route: str, series_id: str,
                     freq: str, length: int) -> List[Tuple[date, float]]:
        params = {
            "api_key": settings.eia_api_key,
            "frequency": freq,
            "data[0]": "value",
            "facets[series][]": series_id,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": length,
        }
        resp = await client.get(f"{EIA_BASE}{route}/data/", params=params, timeout=30.0)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}")
        out = []
        for item in resp.json().get("response", {}).get("data", []):
            val = item.get("value")
            period = item.get("period")
            if val is None or not period:
                continue
            try:
                out.append((date.fromisoformat(period[:10]), float(val)))
            except (ValueError, TypeError):
                continue
        return out

    async def scrape(self, db: Session, snapshot_id: str = None, scraped_at: datetime = None) -> List[Dict[str, Any]]:
        if not settings.eia_api_key:
            logger.warning("EIA_API_KEY not configured. Skipping EIA market data scraper.")
            return []

        summary: List[Dict[str, Any]] = []
        async with httpx.AsyncClient() as client:
            for key, spec in INDICATORS.items():
                rows: Optional[List[Tuple[date, float]]] = None
                used = None
                last_err = None
                for route, series_id in spec["candidates"]:
                    try:
                        rows = await self._fetch(client, route, series_id, spec["freq"], spec["length"])
                        if rows:
                            used = f"{route}:{series_id}"
                            break
                    except Exception as e:  # try next candidate
                        last_err = str(e)
                if not rows:
                    logger.warning("EIA market data: no data for %s (%s)", key, last_err or "empty")
                    summary.append({"series": key, "status": "no_data", "error": last_err})
                    continue

                changed = upsert_indicator_rows(
                    db, key, rows, unit=spec["unit"], source="EIA",
                    snapshot_id=snapshot_id, scraped_at=scraped_at,
                )
                latest = max(rows, key=lambda r: r[0])
                summary.append({
                    "series": key, "source": used, "rows_changed": changed,
                    "latest_date": latest[0].isoformat(), "latest_value": latest[1],
                })
            db.commit()
        return summary
