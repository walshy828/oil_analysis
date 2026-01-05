import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import re
from sqlalchemy.orm import Session

from app.scrapers.base import BaseScraper
from app.models import Company, OilPrice

# Map internal IDs to Yahoo Finance Symbols
MARKET_COMMODITIES = {
    "ulsd": {
        "symbol": "HO=F",
        "name": "Market Index: NY Harbor ULSD",
        "url": "https://finance.yahoo.com/quote/HO=F"
    },
    "brent": {
        "symbol": "BZ=F",
        "name": "Market Index: Brent Crude",
        "url": "https://finance.yahoo.com/quote/BZ=F"
    }
}

class MarketCommoditiesScraper(BaseScraper):
    """Scraper for market commodities (ULSD, Brent) via Yahoo Finance."""
    
    @classmethod
    def get_scraper_type(cls) -> str:
        return "market_commodities"
    
    @classmethod
    def get_description(cls) -> str:
        return "Scrapes NY Harbor ULSD and Brent Crude prices from Yahoo Finance"
    
    async def scrape(self, db: Session, snapshot_id: str = None, scraped_at: datetime = None) -> List[Dict[str, Any]]:
        """Scrape market prices."""
        records = []
        scrape_ts = scraped_at or datetime.utcnow()
        
        # Determine strict targets from the configured URL or default to all
        # If the user provides a specific Yahoo URL, we might infer, but 
        # for this scraper type, we'll generally iterate both commodities
        # irrespective of the input URL (or treat the input URL as a dummy/base).
        
        # However, to be polite to the architecture, if the URL is specific, we could use it.
        # But for 'Market Commodities', it's better to just scrape the known set.
        
        async with httpx.AsyncClient() as client:
            # We mimic a browser to avoid simple blocking
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            for key, info in MARKET_COMMODITIES.items():
                try:
                    target_url = info["url"]
                    response = await client.get(target_url, headers=headers, follow_redirects=True)
                    
                    if response.status_code != 200:
                        print(f"Failed to fetch {target_url}: {response.status_code}")
                        continue
                        
                    soup = BeautifulSoup(response.text, 'lxml')
                    
                    # Yahoo Finance usually puts the price in a specific container
                    # <fin-streamer ... data-field="regularMarketPrice" ...>2.1345</fin-streamer>
                    # Or simpler: look for the main price container class
                    
                    price = None
                    
                    # Method 1: fin-streamer tag (standard for live yahoo pages)
                    streamer = soup.find('fin-streamer', attrs={'data-field': 'regularMarketPrice', 'data-symbol': info['symbol']})
                    if streamer:
                        price_text = streamer.get_text(strip=True).replace(',', '')
                        if price_text:
                            price = Decimal(price_text)
                    
                    # Method 2: fallback regex on title or huge text
                    if not price:
                        # Sometimes simpler pages use data-testid="qsp-price"
                        price_container = soup.find(attrs={'data-testid': 'qsp-price'})
                        if price_container:
                            price_text = price_container.get_text(strip=True).replace(',', '')
                            price = Decimal(price_text)
                            
                    if not price:
                        continue
                        
                    # Find or create the "Company" for this index
                    company = self._find_or_create_index_company(db, info["name"])
                    
                    # Save Price
                    oil_price = OilPrice(
                        company_id=company.id,
                        price_per_gallon=price,
                        town="NYMEX / Global",
                        date_reported=date.today(),
                        scraped_at=scrape_ts,
                        snapshot_id=snapshot_id
                    )
                    db.add(oil_price)
                    
                    records.append({
                        'company': company.name,
                        'price': float(price),
                        'date': date.today().isoformat()
                    })
                    
                except Exception as e:
                    print(f"Error scraping {info['name']}: {e}")
                    continue
            
            db.commit()
        
        return records

    def _find_or_create_index_company(self, db: Session, name: str) -> Company:
        company = db.query(Company).filter(Company.name == name).first()
        if not company:
            company = Company(
                name=name,
                is_market_index=True,
                website="https://finance.yahoo.com",
                phone="N/A"
            )
            db.add(company)
            db.commit()
            db.refresh(company)
        return company
