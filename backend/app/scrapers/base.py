from abc import ABC, abstractmethod
from typing import List, Dict, Any
from sqlalchemy.orm import Session


class BaseScraper(ABC):
    """Base class for all scrapers. Extend this to add new scraper types."""
    
    def __init__(self, url: str):
        self.url = url
    
    @abstractmethod
    async def scrape(self, db: Session) -> List[Dict[str, Any]]:
        """
        Scrape data from the configured URL.
        
        Args:
            db: Database session for storing scraped data
            
        Returns:
            List of dictionaries containing scraped records
        """
        pass
    
    @classmethod
    @abstractmethod
    def get_scraper_type(cls) -> str:
        """Return the unique identifier for this scraper type."""
        pass
    
    @classmethod
    def get_description(cls) -> str:
        """Return a human-readable description of this scraper."""
        return "No description available"
