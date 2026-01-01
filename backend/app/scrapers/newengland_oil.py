import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from datetime import date, datetime
from decimal import Decimal
import re
from sqlalchemy.orm import Session

from app.scrapers.base import BaseScraper
from app.models import Company, CompanyAlias, OilPrice


from app.services.company_service import find_or_create_company, normalize_company_name


class NewEnglandOilScraper(BaseScraper):
    """Scraper for newenglandoil.com prices."""
    
    @classmethod
    def get_scraper_type(cls) -> str:
        return "newengland_oil"
    
    @classmethod
    def get_description(cls) -> str:
        return "Scrapes heating oil prices from New England Oil website"
    
    async def scrape(self, db: Session) -> List[Dict[str, Any]]:
        """Scrape oil prices from New England Oil website."""
        records = []
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.url, timeout=30.0)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find the price table - the website has a table with oil prices
            # Looking for rows with company names and prices
            
            # The table structure varies, let's try to find price entries
            # Looking for links to company pages and associated prices
            
            # Find all table rows or div sections with price data
            price_entries = []
            
            # Method: Parse rows with data-label attributes
            # The website uses data-label attributes on cells which makes extraction robust
            all_rows = soup.find_all('tr')
            processed_companies = set()
            
            for row in all_rows:
                # 1. Company Name & Website
                # Look for cell with data-label="Company" (case insensitive)
                company_cell = row.find('td', attrs={'data-label': re.compile(r'Company', re.I)})
                if not company_cell:
                    continue
                
                name_link = company_cell.find('a')
                if name_link:
                    raw_company_name = name_link.get_text(strip=True)
                    href = name_link.get('href', '')
                    # Extract website from click.asp?x=URL
                    website = None
                    if 'x=' in href:
                         match = re.search(r'x=([^&]+)', href)
                         if match: website = match.group(1)
                else:
                    raw_company_name = company_cell.get_text(strip=True)
                    website = None
                
                if not raw_company_name or raw_company_name in processed_companies:
                    continue
                
                processed_companies.add(raw_company_name)

                # 2. Town
                town = None
                town_cell = row.find('td', attrs={'data-label': re.compile(r'Town', re.I)})
                if town_cell:
                    town = town_cell.get_text(strip=True)

                # 3. Phone
                phone = None
                phone_cell = row.find('td', attrs={'data-label': re.compile(r'Phone', re.I)})
                if phone_cell:
                    phone = phone_cell.get_text(strip=True)
                
                # 4. Price
                price = None
                # Try to find price cell
                price_cell = row.find('td', attrs={'data-label': re.compile(r'Price', re.I)})
                if price_cell:
                     pt = price_cell.get_text()
                     match = re.search(r'\$?(\d+\.\d{2,4})', pt)
                     if match: price = Decimal(match.group(1))
                
                if not price:
                    # Fallback to row search if explicit label missing or empty
                    row_text = row.get_text(separator=' ')
                    match = re.search(r'\$?(\d+\.\d{2,4})', row_text)
                    if match: price = Decimal(match.group(1))
                
                if not price: continue

                # 5. Date
                date_reported = date.today()
                date_cell = row.find('td', attrs={'data-label': re.compile(r'Date', re.I)})
                if date_cell:
                    date_text = date_cell.get_text(strip=True)
                    if date_text:
                        try:
                            # Try parsing MM/DD/YY
                            parsed_dt = datetime.strptime(date_text, "%m/%d/%y")
                            date_reported = parsed_dt.date()
                        except ValueError:
                            try:
                                # Try MM/DD/YYYY
                                parsed_dt = datetime.strptime(date_text, "%m/%d/%Y")
                                date_reported = parsed_dt.date()
                            except ValueError:
                                # Keep today if parse fails
                                pass

                # Save Data
                company = find_or_create_company(db, raw_company_name, website, phone)
                
                oil_price = OilPrice(
                    company_id=company.id,
                    price_per_gallon=price,
                    town=town,
                    date_reported=date_reported
                )
                db.add(oil_price)
                
                records.append({
                    'company': company.name,
                    'price': float(price),
                    'date': date_reported.isoformat()
                })
            
            # If we didn't find prices with method 2, try parsing the page differently
            if not records:
                # Look for any price patterns in the entire page
                all_text = soup.get_text()
                
                # Find company names (usually all caps) followed by prices
                pattern = r'([A-Z][A-Z\s&\'.,-]+)\s+[\$]?(\d+\.\d{2,4})'
                matches = re.findall(pattern, all_text)
                
                for raw_company_name, price in matches:
                    raw_company_name = raw_company_name.strip()
                    if len(raw_company_name) > 3:  # Filter out short matches
                        price = Decimal(price)
                        
                        company = find_or_create_company(db, raw_company_name)
                        
                        oil_price = OilPrice(
                            company_id=company.id,
                            price_per_gallon=price,
                            date_reported=date.today()
                        )
                        db.add(oil_price)
                        
                        records.append({
                            'company': company.name,
                            'price': float(price),
                            'date': date.today().isoformat()
                        })
            
            db.commit()
        
        return records
