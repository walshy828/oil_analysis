"""
Check the Market Intel data feeds against the live sources.

Usage (from backend/, with EIA_API_KEY set in the environment or .env):
    python verify_market_feeds.py

Prints, per series, whether data came back and the latest observation. Nothing is written to
your database: results go to a throwaway in-memory SQLite. Use it after setup, and whenever a
feed shows "no_data" on the Market Intel page (EIA occasionally renames series IDs).
"""
import asyncio
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
import app.models  # noqa: F401  (register tables)
from app.scrapers import get_scraper

FEEDS = ["eia_market_data", "cftc_cot", "weather_forecast", "futures_curve"]


async def main():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    for feed in FEEDS:
        print(f"\n=== {feed} ===")
        try:
            rows = await get_scraper(feed, "").scrape(db)
        except Exception as exc:  # pragma: no cover - diagnostic script
            print(f"FAILED: {exc!r}")
            continue
        if not rows:
            print("No output (missing API key?)")
        for r in rows:
            status = r.get("status", "ok")
            print(f"  [{status:>12}] {json.dumps(r)}")


if __name__ == "__main__":
    asyncio.run(main())
