import asyncio
import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.models import MarketIndicator
from app.scrapers.base import BaseScraper
from app.services.market_indicators import upsert_indicator_rows

logger = logging.getLogger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
MONTH_CODES = "FGHJKMNQUVXZ"

# ICE low-sulphur gasoil front month, quoted in USD per metric ton
GASOIL_SYMBOLS = ["LGO=F"]
GASOIL_KEY = "gasoil_front_usd_t"


class RateLimited(RuntimeError):
    """Yahoo answered 429; further requests in this run would only deepen the block."""


def ho_series_key(year: int, month: int) -> str:
    return f"ho_fut:{year}{month:02d}"


def ho_symbol(year: int, month: int) -> str:
    return f"HO{MONTH_CODES[month - 1]}{year % 100:02d}.NYM"


def add_months(year: int, month: int, n: int) -> Tuple[int, int]:
    idx = year * 12 + (month - 1) + n
    return idx // 12, idx % 12 + 1


async def fetch_chart(client: httpx.AsyncClient, symbol: str, range_: str) -> List[Tuple[date, float]]:
    """Daily closes for a Yahoo Finance symbol via the chart JSON endpoint."""
    resp = await client.get(
        CHART_URL.format(symbol=symbol),
        params={"range": range_, "interval": "1d"},
        headers=HEADERS, timeout=20.0,
    )
    if resp.status_code == 429:
        raise RateLimited("HTTP 429 (Yahoo is rate limiting or blocking this host)")
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")
    result = (resp.json().get("chart", {}).get("result") or [None])[0]
    if not result:
        return []
    offset = int(result.get("meta", {}).get("gmtoffset", 0) or 0)
    stamps = result.get("timestamp") or []
    closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    out = []
    for ts, close in zip(stamps, closes):
        if close is None:
            continue
        out.append((datetime.utcfromtimestamp(ts + offset).date(), float(close)))
    return out


class FuturesCurveScraper(BaseScraper):
    """
    NY Harbor ULSD (HO) individual contract settlements for the next 12 months, plus ICE gasoil.

    Contracts are stored per delivery month (ho_fut:YYYYMM) rather than per rank (M1, M2...), so
    the curve can be rebuilt for any past date and the first run backfills a year of history.

    Data comes from Yahoo Finance's chart endpoint (free, delayed, best effort: Yahoo blocks some
    hosts with HTTP 429). If that happens the run stops early and reports it; the curve can also
    be loaded by hand via POST /api/market-intel/curve/import, or by replacing `fetch_chart` with
    a licensed feed. Everything downstream only reads the indicator table.
    """

    @classmethod
    def get_scraper_type(cls) -> str:
        return "futures_curve"

    @classmethod
    def get_description(cls) -> str:
        return "NYMEX ULSD forward curve (12 contracts) and ICE gasoil"

    def _has_history(self, db: Session, key: str) -> bool:
        return db.query(MarketIndicator.id).filter(MarketIndicator.series_key == key).first() is not None

    async def scrape(self, db: Session, snapshot_id: str = None, scraped_at: datetime = None) -> List[Dict[str, Any]]:
        today = date.today()
        summary: List[Dict[str, Any]] = []

        # Current-month HO expires the last business day of the prior month, so the live
        # strip is next month .. +12. First run also pulls expired contracts for backfill.
        live = [add_months(today.year, today.month, n) for n in range(1, 13)]
        expired = [add_months(today.year, today.month, n) for n in range(-11, 1)]

        blocked = False
        async with httpx.AsyncClient() as client:
            for (y, m) in expired + live:
                key = ho_series_key(y, m)
                is_live = (y, m) in live
                has_history = self._has_history(db, key)
                if not is_live and has_history:
                    continue  # expired contract already stored
                range_ = "5d" if has_history else "1y"
                try:
                    rows = await fetch_chart(client, ho_symbol(y, m), range_)
                    if not rows:
                        summary.append({"series": key, "status": "no_data"})
                        continue
                    changed = upsert_indicator_rows(
                        db, key, rows, unit="usd/gal", source="NYMEX/Yahoo",
                        label=ho_symbol(y, m), snapshot_id=snapshot_id, scraped_at=scraped_at,
                    )
                    summary.append({"series": key, "rows_changed": changed, "latest": rows[-1][1]})
                except RateLimited as e:
                    logger.warning("Curve fetch rate limited at %s: %s. Stopping this run.", ho_symbol(y, m), e)
                    summary.append({"series": key, "status": "rate_limited", "error": str(e)})
                    blocked = True
                    break
                except Exception as e:
                    logger.warning("Curve fetch failed for %s: %s", ho_symbol(y, m), e)
                    summary.append({"series": key, "status": "error", "error": str(e)})
                await asyncio.sleep(1.0)

            if blocked:
                db.commit()
                return summary

            # ICE gasoil
            rows: Optional[List[Tuple[date, float]]] = None
            for sym in GASOIL_SYMBOLS:
                try:
                    rows = await fetch_chart(client, sym, "5d" if self._has_history(db, GASOIL_KEY) else "1y")
                    if rows:
                        break
                except RateLimited:
                    break
                except Exception as e:
                    logger.warning("Gasoil fetch failed for %s: %s", sym, e)
            if rows:
                changed = upsert_indicator_rows(
                    db, GASOIL_KEY, rows, unit="usd/t", source="ICE/Yahoo",
                    snapshot_id=snapshot_id, scraped_at=scraped_at,
                )
                summary.append({"series": GASOIL_KEY, "rows_changed": changed, "latest": rows[-1][1]})
            else:
                summary.append({"series": GASOIL_KEY, "status": "no_data"})

            db.commit()
        return summary
