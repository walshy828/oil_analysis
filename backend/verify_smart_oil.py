import asyncio
import os
import sys
from datetime import datetime

# Adjust path to allow imports from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.scrapers.smart_oil_gauge import SmartOilGaugeScraper

async def main():
    print("Initializing DB session...")
    db = SessionLocal()
    try:
        print("Initializing Scraper...")
        scraper = SmartOilGaugeScraper()
        
        print("Running scrape()...")
        # We need a snapshot_id for the scrape method signature, though it might optional in some implementations
        # The signature in smart_oil_gauge.py is: async def scrape(self, db: Session, snapshot_id: str = None, scraped_at: datetime = None)
        
        records = await scraper.scrape(db, snapshot_id="manual_verify", scraped_at=datetime.utcnow())
        
        print(f"\nScrape completed. Records found: {len(records)}")
        for r in records:
            print(f" - {r}")
            
    except Exception as e:
        print(f"\nERROR running scraper: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    # Check for credentials
    if not os.getenv("SMART_OIL_USERNAME") or not os.getenv("SMART_OIL_PASSWORD"):
        print("WARNING: SMART_OIL_USERNAME or SMART_OIL_PASSWORD not found in environment.")
        print("Attempting to run anyway (scraper will likely fail authentication)...")
    
    asyncio.run(main())
