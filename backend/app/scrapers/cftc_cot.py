import logging
from datetime import date, datetime
from typing import List, Dict, Any

import httpx
from sqlalchemy.orm import Session

from app.scrapers.base import BaseScraper
from app.services.market_indicators import upsert_indicator_rows

logger = logging.getLogger(__name__)

# CFTC Public Reporting Environment (Socrata): Disaggregated Futures Only
COT_URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"

# series prefix -> market name prefix as published by CFTC
MARKETS = {
    "cot_ulsd": "NY HARBOR ULSD",
    "cot_wti": "WTI-PHYSICAL",
}


class CftcCotScraper(BaseScraper):
    """Managed-money positioning in NY Harbor ULSD and WTI from the weekly CFTC COT report."""

    @classmethod
    def get_scraper_type(cls) -> str:
        return "cftc_cot"

    @classmethod
    def get_description(cls) -> str:
        return "CFTC Commitments of Traders: managed-money net position in ULSD and WTI futures"

    async def scrape(self, db: Session, snapshot_id: str = None, scraped_at: datetime = None) -> List[Dict[str, Any]]:
        summary: List[Dict[str, Any]] = []
        async with httpx.AsyncClient() as client:
            for prefix, market in MARKETS.items():
                try:
                    params = {
                        "$where": f"market_and_exchange_names like '{market}%'",
                        "$order": "report_date_as_yyyy_mm_dd DESC",
                        "$limit": "200",  # ~4 years of weekly reports
                    }
                    resp = await client.get(COT_URL, params=params, timeout=30.0)
                    if resp.status_code != 200:
                        raise RuntimeError(f"HTTP {resp.status_code}")
                    data = resp.json()

                    # Keyed by date so a sibling listing can never produce duplicate rows
                    net_map, pct_map = {}, {}
                    for item in data:
                        try:
                            d = date.fromisoformat(item["report_date_as_yyyy_mm_dd"][:10])
                            long_ = float(item["m_money_positions_long_all"])
                            short = float(item["m_money_positions_short_all"])
                            oi = float(item["open_interest_all"])
                        except (KeyError, ValueError, TypeError):
                            continue
                        net_map[d] = long_ - short
                        if oi > 0:
                            pct_map[d] = (long_ - short) / oi * 100.0

                    net_rows, pct_rows = list(net_map.items()), list(pct_map.items())
                    if not net_rows:
                        summary.append({"series": prefix, "status": "no_data"})
                        continue

                    c1 = upsert_indicator_rows(db, f"{prefix}_mm_net", net_rows, unit="contracts",
                                               source="CFTC", snapshot_id=snapshot_id, scraped_at=scraped_at)
                    c2 = upsert_indicator_rows(db, f"{prefix}_mm_net_pct", pct_rows, unit="pct_oi",
                                               source="CFTC", snapshot_id=snapshot_id, scraped_at=scraped_at)
                    latest = max(net_rows, key=lambda r: r[0])
                    summary.append({
                        "series": prefix, "rows_changed": c1 + c2,
                        "latest_date": latest[0].isoformat(), "latest_net": latest[1],
                    })
                except Exception as e:
                    logger.warning("CFTC COT fetch failed for %s: %s", prefix, e)
                    summary.append({"series": prefix, "status": "error", "error": str(e)})
            db.commit()
        return summary
