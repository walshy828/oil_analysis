import httpx
from typing import List, Dict, Any
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.scrapers.base import BaseScraper
from app.models import Company, OilPrice
from app.config import settings

class EiaSpotPriceScraper(BaseScraper):
    """Scraper for EIA Spot Prices (WTI, Brent, NY Harbor ULSD) using EIA API v2."""
    
    API_URL = "https://api.eia.gov/v2/petroleum/pri/spt/data/"
    
    # Series IDs and human-readable names
    SERIES = {
        "RWTC": "EIA Index: WTI Crude Spot",
        "RBRTE": "EIA Index: Brent Crude Spot",
        "EER_EPD2DXL0_PF4_RGC_DPG": "EIA Index: NY Harbor ULSD Spot",
        "EER_EPMRR_PF4_RGC_DPG": "EIA Index: NY Harbor Gasoline Spot"
    }
    
    @classmethod
    def get_scraper_type(cls) -> str:
        return "eia_spot_prices"
    
    @classmethod
    def get_description(cls) -> str:
        return "Fetches daily spot prices (WTI, Brent, ULSD) from EIA.gov API"
    
    async def scrape(self, db: Session, snapshot_id: str = None, scraped_at: datetime = None) -> List[Dict[str, Any]]:
        if not settings.eia_api_key:
            print("EIA_API_KEY not configured. Skipping EIA scraper.")
            return []
            
        records = []
        scrape_ts = scraped_at or datetime.utcnow()
        
        async with httpx.AsyncClient() as client:
            for series_id, internal_name in self.SERIES.items():
                try:
                    params = {
                        "api_key": settings.eia_api_key,
                        "frequency": "daily",
                        "data[0]": "value",
                        "facets[series][]": series_id,
                        "sort[0][column]": "period",
                        "sort[0][direction]": "desc",
                        "length": 1
                    }
                    
                    response = await client.get(self.API_URL, params=params, timeout=10.0)
                    
                    if response.status_code != 200:
                        print(f"Failed to fetch EIA series {series_id}: {response.status_code}")
                        continue
                        
                    data = response.json()
                    results = data.get("response", {}).get("data", [])
                    
                    if not results:
                        continue
                        
                    item = results[0]
                    price_val = item.get("value")
                    price_date = date.fromisoformat(item.get("period"))
                    
                    if price_val is None:
                        continue
                        
                    price = Decimal(str(round(float(price_val), 4)))
                    
                    # Find/Create company
                    company = self._find_or_create_index_company(db, internal_name)
                    
                    # Check for existing record
                    existing = db.query(OilPrice).filter(
                        OilPrice.company_id == company.id,
                        OilPrice.date_reported == price_date
                    ).first()
                    
                    if not existing:
                        oil_price = OilPrice(
                            company_id=company.id,
                            price_per_gallon=price,
                            town="EIA Spot / Global",
                            date_reported=price_date,
                            scraped_at=scrape_ts,
                            snapshot_id=snapshot_id
                        )
                        db.add(oil_price)
                        
                        records.append({
                            'company': company.name,
                            'price': float(price),
                            'date': price_date.isoformat()
                        })
                    
                except Exception as e:
                    print(f"Error fetching EIA series {series_id}: {e}")
                    
            db.commit()
                
        return records

    def _find_or_create_index_company(self, db: Session, name: str) -> Company:
        company = db.query(Company).filter(Company.name == name).first()
        if not company:
            company = Company(
                name=name,
                is_market_index=True,
                website="https://www.eia.gov",
                phone="N/A"
            )
            db.add(company)
            db.commit()
            db.refresh(company)
        return company
