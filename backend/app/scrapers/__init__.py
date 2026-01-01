from app.scrapers.base import BaseScraper
from app.scrapers.newengland_oil import NewEnglandOilScraper
from app.scrapers.market_commodities import MarketCommoditiesScraper
from app.scrapers.eia_spot import EiaSpotPriceScraper
from app.scrapers.weather import WeatherScraper

# Registry of available scrapers
SCRAPER_REGISTRY = {
    "newengland_oil": NewEnglandOilScraper,
    "market_commodities": MarketCommoditiesScraper,
    "eia_spot_prices": EiaSpotPriceScraper,
    "weather": WeatherScraper,
}


def get_scraper(scraper_type: str, url: str) -> BaseScraper:
    """Factory function to get the appropriate scraper."""
    if scraper_type not in SCRAPER_REGISTRY:
        raise ValueError(f"Unknown scraper type: {scraper_type}")
    
    return SCRAPER_REGISTRY[scraper_type](url)


__all__ = ["BaseScraper", "NewEnglandOilScraper", "get_scraper", "SCRAPER_REGISTRY"]
