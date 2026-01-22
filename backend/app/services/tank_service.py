from typing import List, Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import TankReading, Location
import csv
import io
from fastapi import HTTPException

class TankService:
    def __init__(self, db: Session):
        self.db = db

    def detect_anomalies(self, readings: List[dict], tank_capacity: float = 275.0) -> List[dict]:
        """
        Process raw readings and flag anomalies:
        1. Small increases (sensor noise) - flag as anomaly
        2. Large increases (fill events) - flag as fill
        3. Post-fill instability (readings near max fluctuating) - flag as unstable
        """
        if not readings:
            return []
        
        # Sort by timestamp
        readings = sorted(readings, key=lambda x: x['timestamp'])
        
        processed = []
        fill_threshold = 30.0  # Jump of 30+ gallons indicates fill
        noise_threshold = 2.0  # Small increase up to 2 gallons is noise
        max_capacity_threshold = tank_capacity * 0.85  # 85% of capacity = "near full"
        stability_window = 48  # Hours to check for post-fill stability
        
        last_stable_value = None
        fill_event_time = None
        
        for i, reading in enumerate(readings):
            gallons = reading['gallons']
            ts = reading['timestamp']
            
            flags = {
                'is_anomaly': False,
                'is_fill_event': False,
                'is_post_fill_unstable': False
            }
            
            if i > 0:
                prev_gallons = readings[i - 1]['gallons']
                delta = gallons - prev_gallons
                
                # Check for fill event
                if delta > fill_threshold:
                    flags['is_fill_event'] = True
                    fill_event_time = ts
                    last_stable_value = None  # Reset stability tracking
                
                # Check for noise (small unexpected increase)
                elif delta > 0 and delta <= noise_threshold:
                    flags['is_anomaly'] = True
                
                # Check for post-fill instability
                if fill_event_time:
                    hours_since_fill = (ts - fill_event_time).total_seconds() / 3600
                    
                    # Within stability window and near max capacity
                    if hours_since_fill < stability_window and gallons > max_capacity_threshold:
                        # Check if readings are fluctuating (variance)
                        if abs(delta) > 1.0:  # Fluctuation > 1 gallon
                            flags['is_post_fill_unstable'] = True
                    elif hours_since_fill >= stability_window:
                        # Reset fill event tracking after stability window
                        fill_event_time = None
            
            processed.append({
                **reading,
                **flags
            })
        
        return processed

    def process_readings_csv(self, file_content: str, location_id: int) -> dict:
        """
        Process CSV content containing tank readings.
        """
        # Verify location exists
        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")
        
        tank_capacity = location.tank_capacity or 275.0
        
        reader = csv.DictReader(io.StringIO(file_content))
        
        # Define allowed aliases
        TIME_ALIASES = ['t', 'Time', 'timestamp', 'Read Date']
        GALLON_ALIASES = ['g', 'Gallons', 'volume', 'Tank Volume']
        
        raw_readings = []
        for row in reader:
            try:
                # Helper to find the first matching key that exists in this row
                ts_key = next((k for k in TIME_ALIASES if k in row), None)
                val_key = next((k for k in GALLON_ALIASES if k in row), None)

                if not ts_key or not val_key:
                    continue

                # Handle quoted timestamps
                ts_str = row[ts_key].strip('"')
                gallons_str = row[val_key]
                
                # Try multiple date formats
                ts = None
                date_formats = [
                    '%Y-%m-%d %H:%M:%S',
                    '%m/%d/%Y %H:%M:%S',
                    '%m/%d/%Y %H:%M',
                    '%Y-%m-%d %H:%M'
                ]
                
                for fmt in date_formats:
                    try:
                        ts = datetime.strptime(ts_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if not ts:
                    continue

                gallons = float(gallons_str)
                
                raw_readings.append({
                    'timestamp': ts,
                    'gallons': gallons
                })
            except (ValueError, KeyError):
                continue  # Skip invalid rows
        
        if not raw_readings:
            return {
                "message": "No valid readings found",
                "new_readings": 0,
                "skipped_duplicates": 0,
                "total_processed": 0
            }
        
        # Process and flag anomalies
        processed = self.detect_anomalies(raw_readings, tank_capacity)
        
        # Get existing timestamps for deduplication
        existing_timestamps = set(
            r.timestamp for r in self.db.query(TankReading.timestamp).filter(
                TankReading.location_id == location_id
            ).all()
        )
        
        # Insert new readings
        new_count = 0
        skipped_count = 0
        
        for reading in processed:
            if reading['timestamp'] in existing_timestamps:
                skipped_count += 1
                continue
            
            tank_reading = TankReading(
                location_id=location_id,
                timestamp=reading['timestamp'],
                gallons=reading['gallons'],
                is_anomaly=reading['is_anomaly'],
                is_fill_event=reading['is_fill_event'],
                is_post_fill_unstable=reading['is_post_fill_unstable']
            )
            self.db.add(tank_reading)
            new_count += 1
        
        self.db.commit()
        
        return {
            "message": "Upload complete",
            "new_readings": new_count,
            "skipped_duplicates": skipped_count,
            "total_processed": len(processed)
        }

    def add_reading(self, location_id: int, gallons: float, timestamp: datetime) -> TankReading:
        """
        Add a single reading with anomaly detection.
        """
        # Check if reading already exists
        existing = self.db.query(TankReading).filter(
            TankReading.location_id == location_id,
            TankReading.timestamp == timestamp
        ).first()
        
        if existing:
            return existing

        # Get recent readings for context (last 48 hours for stability check)
        start_check = timestamp - timedelta(hours=48)
        recent_readings = self.db.query(TankReading).filter(
            TankReading.location_id == location_id,
            TankReading.timestamp >= start_check
        ).all()
        
        # Convert to dict format expected by detect_anomalies
        history = [
            {'timestamp': r.timestamp, 'gallons': r.gallons}
            for r in recent_readings
        ]
        history.append({'timestamp': timestamp, 'gallons': gallons})
        
        # Get tank capacity
        location = self.db.query(Location).filter(Location.id == location_id).first()
        tank_capacity = location.tank_capacity or 275.0
        
        # Run detection
        processed = self.detect_anomalies(history, tank_capacity)
        
        # Find our new reading in processed list
        result = next(r for r in processed if r['timestamp'] == timestamp)
        
        # Create and save
        new_reading = TankReading(
            location_id=location_id,
            timestamp=timestamp,
            gallons=gallons,
            is_anomaly=result['is_anomaly'],
            is_fill_event=result['is_fill_event'],
            is_post_fill_unstable=result['is_post_fill_unstable']
        )
        
        self.db.add(new_reading)
        self.db.commit()
        self.db.refresh(new_reading)
        
        return new_reading
