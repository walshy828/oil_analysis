from app.scrapers.base import BaseScraper
from app.scrapers.newengland_oil import NewEnglandOilScraper
from app.scrapers.market_commodities import MarketCommoditiesScraper
from app.scrapers.eia_spot import EiaSpotPriceScraper
from app.scrapers.weather import WeatherScraper
from app.scrapers.smart_oil_gauge import SmartOilGaugeScraper
from app.scrapers.eia_market_data import EiaMarketDataScraper
from app.scrapers.cftc_cot import CftcCotScraper
from app.scrapers.futures_curve import FuturesCurveScraper
from app.scrapers.weather_forecast import WeatherForecastScraper

# Registry of available scrapers
SCRAPER_REGISTRY = {
    "newengland_oil": NewEnglandOilScraper,
    "market_commodities": MarketCommoditiesScraper,
    "eia_spot_prices": EiaSpotPriceScraper,
    "weather": WeatherScraper,
    "smart_oil_gauge": SmartOilGaugeScraper,
    "eia_market_data": EiaMarketDataScraper,
    "cftc_cot": CftcCotScraper,
    "futures_curve": FuturesCurveScraper,
    "weather_forecast": WeatherForecastScraper,
}


def get_scraper(scraper_type: str, url: str) -> BaseScraper:
    """Factory function to get the appropriate scraper."""
    if scraper_type not in SCRAPER_REGISTRY:
        raise ValueError(f"Unknown scraper type: {scraper_type}")
    
    return SCRAPER_REGISTRY[scraper_type](url)


__all__ = ["BaseScraper", "NewEnglandOilScraper", "get_scraper", "SCRAPER_REGISTRY"]
