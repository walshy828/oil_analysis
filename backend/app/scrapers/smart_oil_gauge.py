import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import os
import re

from app.scrapers.base import BaseScraper
from app.services.tank_service import TankService
from app.models import Location, ScrapeConfig

class SmartOilGaugeScraper(BaseScraper):
    """Scraper for Smart Oil Gauge dashboard and export."""
    
    @classmethod
    def get_scraper_type(cls) -> str:
        return "smart_oil_gauge"
    
    @classmethod
    def get_description(cls) -> str:
        return "Scrapes current level and history from Smart Oil Gauge"
    
    async def scrape(self, db: Session, snapshot_id: str = None, scraped_at: datetime = None) -> List[Dict[str, Any]]:
        """
        Scrape data from Smart Oil Gauge.
        1. Login
        2. Get current level from dashboard
        3. Export history CSV and process it
        """
        username = os.getenv("SMART_OIL_USERNAME")
        password = os.getenv("SMART_OIL_PASSWORD")
        
        if not username or not password:
            raise ValueError("SMART_OIL_USERNAME and SMART_OIL_PASSWORD env vars must be set")
            
        login_url = "https://app.smartoilgauge.com/app.php"
        export_url = "https://app.smartoilgauge.com/export_data.php"
        
        # We need a location to save data to. 
        # For now, we'll use the first location in the DB.
        location = db.query(Location).first()
        if not location:
            raise ValueError("No location found in database to save readings to")
            
        records = []
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://app.smartoilgauge.com/app.php",
            "Origin": "https://app.smartoilgauge.com"
        }
        
        async with httpx.AsyncClient(headers=headers) as client:
            # 1. Login
            # GET login page first to get cookies and parse form
            initial_url = "https://app.smartoilgauge.com/login.php"
            print(f"Fetching login page: {initial_url}...")
            response = await client.get(initial_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            form = soup.find('form')
            
            if not form:
                print("Error: Could not find login form on page")
                # Fallback to simple POST if no form found
                post_url = initial_url
                data = {}
            else:
                # Get action URL
                action = form.get('action')
                if action:
                    if action.startswith('http'):
                        post_url = action
                    else:
                        # Handle relative URL
                        from urllib.parse import urljoin
                        post_url = urljoin(initial_url, action)
                else:
                    post_url = initial_url
                
                print(f"Login form action: {post_url}")
                
                # Get all inputs
                data = {}
                for inp in form.find_all('input'):
                     name = inp.get('name')
                     if name:
                         data[name] = inp.get('value', '')
                
                print(f"Form fields found: {list(data.keys())}")
            
            # Update with credentials
            data['username'] = username
            data['user_pass'] = password
            # Ensure the submit button name is included if it was in the inputs, otherwise add it
            if 'login' not in data:
                 data['login'] = 'Login'

            print(f"Posting login to {post_url}...")
            response = await client.post(post_url, data=data, follow_redirects=True)
            response.raise_for_status()

            print(f"Login result url: {response.url}")
            # 2. Get Tank Data via API
            # based on analysis of app.js
            ajax_url = "https://app.smartoilgauge.com/ajax/main_ajax.php"
            
            # Get list of tanks
            print("Fetching tank list...")
            tanks_payload = {
                "action": "get_tanks_list",
                "tank_id": 0
            }
            tanks_resp = await client.post(ajax_url, data=tanks_payload)
            tanks_resp.raise_for_status()
            tanks_data = tanks_resp.json()
            print(f"Tanks API Response: {tanks_data}")
            
            if "tanks" not in tanks_data or not tanks_data["tanks"]:
                print("No tanks found in account")
                return records

            # Process each tank (or just the first one matching our location??)
            # For now, we only support one tank per location in our DB model roughly.
            # We'll take the first tank.
            tank = tanks_data["tanks"][0]
            tank_id = tank["tank_id"]
            print(f"Found tank: {tank.get('tank_name')} (ID: {tank_id})")
            
            # Get tank details to find registration_id for export
            print(f"Fetching details for tank {tank_id}...")
            details_payload = {
                "action": "get_tank_details",
                "tank_id": tank_id
            }
            details_resp = await client.post(ajax_url, data=details_payload)
            details_resp.raise_for_status()
            tank_details = details_resp.json()
            
            # Get Current Level
            # API returns strings like "200.16" or null
            sensor_gallons = tank_details.get("sensor_gallons")
            if sensor_gallons is not None:
                current_gallons = float(sensor_gallons)
                print(f"Current level: {current_gallons} gallons")
                
                # Save to DB using TankService
                ts = datetime.utcnow()
                service = TankService(db)
                reading = service.add_reading(location.id, current_gallons, ts)
                print(f"Saved reading: {reading.id} ({reading.gallons} gal)")
                
                records.append({
                    "type": "current_level",
                    "gallons": current_gallons,
                    "timestamp": ts.isoformat(),
                    "saved_to_db": True
                })
            
            # 3. Export History
            registration_id = None
            if "sensors" in tank_details and tank_details["sensors"]:
                registration_id = tank_details["sensors"][0].get("registration_id")
            
            if not registration_id:
                print("Could not find registration_id for export")
            else:
                print(f"Exporting data for registration_id: {registration_id}")
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)

                # POST directly to the export endpoint with registration_id in query string.
                # The form's submit button is named "submit" (id="do-export"), value="Export".
                export_post_url = f"{export_url}?registration_id={registration_id}"
                export_form_data = {
                    'registration_id': registration_id,
                    'startdate': start_date.strftime("%Y-%m-%d"),
                    'enddate': end_date.strftime("%Y-%m-%d"),
                    'submit': 'Export',
                }
                print(f"Posting export to {export_post_url}...")
                export_response = await client.post(
                    export_post_url,
                    data=export_form_data,
                    follow_redirects=True
                )

                if export_response.status_code == 200:
                    content_type = export_response.headers.get('content-type', '')
                    is_csv = 'csv' in content_type

                    if is_csv:
                        csv_content = export_response.text
                        print(f"CSV Content Preview: {csv_content[:200]}")

                        service = TankService(db)
                        result = service.process_readings_csv(csv_content, location.id)
                        print(f"Import result: {result}")

                        records.append({
                            "type": "history_export",
                            "new_readings": result.get('new_readings'),
                            "total_processed": result.get('total_processed')
                        })
                    else:
                        print(f"Export returned non-CSV content: {content_type}")
        
        return records
