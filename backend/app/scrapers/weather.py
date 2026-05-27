from datetime import date, timedelta, datetime
import httpx
from sqlalchemy.orm import Session
from app.models import Location, Temperature
from app.scrapers.base import BaseScraper
import logging

logger = logging.getLogger(__name__)

# Fetch enough history to catch up after missed runs
_LOOKBACK_DAYS = 14


class WeatherScraper(BaseScraper):
    """
    Scrapes historical/recent weather data for ALL configured locations.
    Ignores the 'url' parameter in ScrapeConfig; uses the Open-Meteo archive API.
    """

    @classmethod
    def get_scraper_type(cls) -> str:
        return "weather"

    async def scrape(self, db: Session, snapshot_id: str = None, scraped_at: datetime = None) -> list:
        locations = db.query(Location).filter(
            Location.latitude.isnot(None),
            Location.longitude.isnot(None)
        ).all()

        records = []

        async with httpx.AsyncClient() as client:
            for loc in locations:
                try:
                    end_date = date.today() - timedelta(days=1)
                    start_date = end_date - timedelta(days=_LOOKBACK_DAYS)

                    url = "https://archive-api.open-meteo.com/v1/archive"
                    params = {
                        "latitude": loc.latitude,
                        "longitude": loc.longitude,
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "daily": "temperature_2m_max,temperature_2m_min",
                        "temperature_unit": "fahrenheit",
                        "timezone": "America/New_York"
                    }

                    response = await client.get(url, params=params, timeout=30.0)
                    if response.status_code != 200:
                        logger.error(f"Failed to fetch weather for {loc.name}: {response.text}")
                        continue

                    data = response.json()
                    daily = data.get("daily", {})
                    dates = daily.get("time", [])
                    highs = daily.get("temperature_2m_max", [])
                    lows = daily.get("temperature_2m_min", [])

                    if not dates:
                        continue

                    added = 0
                    updated = 0
                    for i, d in enumerate(dates):
                        try:
                            temp_date = date.fromisoformat(d)
                            high = highs[i] if i < len(highs) and highs[i] is not None else None
                            low = lows[i] if i < len(lows) and lows[i] is not None else None

                            if high is None or low is None:
                                continue

                            existing = db.query(Temperature).filter(
                                Temperature.location_id == loc.id,
                                Temperature.date == temp_date
                            ).first()

                            if existing:
                                existing.low_temp = low
                                existing.high_temp = high
                                updated += 1
                            else:
                                db.add(Temperature(
                                    location_id=loc.id,
                                    date=temp_date,
                                    low_temp=low,
                                    high_temp=high
                                ))
                                added += 1
                        except Exception as parse_err:
                            logger.error(f"Error parsing weather row {d} for {loc.name}: {parse_err}")
                            continue

                    db.commit()
                    logger.info(f"Weather for {loc.name}: {added} added, {updated} updated")
                    records.append({
                        "location": loc.name,
                        "location_id": loc.id,
                        "added": added,
                        "updated": updated,
                    })

                except Exception as e:
                    logger.error(f"Error scraping weather for {loc.name}: {e}")

        return records
