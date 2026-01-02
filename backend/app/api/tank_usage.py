from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta, date
from typing import Optional, List
from decimal import Decimal
import csv
import io

from app.database import get_db
from app.models import TankReading, Location, OilPrice, Company, DailyUsage
from app.services.usage_normalization import UsageNormalizer

router = APIRouter()


def detect_anomalies(readings: List[dict], tank_capacity: float = 275.0) -> List[dict]:
    """
    Process raw readings and flag anomalies:
    1. Small increases (sensor noise) - flag as anomaly
    2. Large increases (fill events) - flag as fill
    3. Post-fill instability (readings near max fluctuating) - flag as unstable
    
    Args:
        readings: List of dicts with 'timestamp' and 'gallons'
        tank_capacity: Tank capacity in gallons (default 275)
    
    Returns:
        List of processed readings with anomaly flags
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


@router.post("/upload")
async def upload_tank_readings(
    file: UploadFile = File(...),
    location_id: int = Query(..., description="Location ID for the tank"),
    db: Session = Depends(get_db)
):
    """
    Upload Smart Oil Gauge CSV data.
    Expected format: t,g (timestamp, gallons)
    Deduplicates based on location_id + timestamp.
    """
    # Verify location exists
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    tank_capacity = location.tank_capacity or 275.0
    
    # Parse CSV
    content = await file.read()
    text = content.decode('utf-8')
    
    reader = csv.DictReader(io.StringIO(text))
    # Define allowed aliases
    
    TIME_ALIASES = ['t', 'Time', 'timestamp']
    GALLON_ALIASES = ['g', 'Gallons', 'volume']
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
            
            ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
            gallons = float(gallons_str)
            
            raw_readings.append({
                'timestamp': ts,
                'gallons': gallons
            })
        except (ValueError, KeyError) as e:
            continue  # Skip invalid rows
    
    if not raw_readings:
        raise HTTPException(status_code=400, detail="No valid readings found in CSV")
    
    # Process and flag anomalies
    processed = detect_anomalies(raw_readings, tank_capacity)
    
    # Get existing timestamps for deduplication
    existing_timestamps = set(
        r.timestamp for r in db.query(TankReading.timestamp).filter(
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
        db.add(tank_reading)
        new_count += 1
    
    db.commit()
    
    return {
        "message": "Upload complete",
        "new_readings": new_count,
        "skipped_duplicates": skipped_count,
        "total_processed": len(processed)
    }


@router.get("/readings")
async def get_tank_readings(
    location_id: int = Query(...),
    days: int = Query(30, description="Number of days to fetch"),
    include_anomalies: bool = Query(False, description="Include flagged anomaly readings"),
    db: Session = Depends(get_db)
):
    """Get tank readings with optional anomaly filtering."""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(TankReading).filter(
        TankReading.location_id == location_id,
        TankReading.timestamp >= start_date
    )
    
    if not include_anomalies:
        query = query.filter(
            TankReading.is_anomaly == False,
            TankReading.is_post_fill_unstable == False
        )
    
    readings = query.order_by(TankReading.timestamp).all()
    
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "gallons": r.gallons,
            "is_anomaly": r.is_anomaly,
            "is_fill_event": r.is_fill_event,
            "is_post_fill_unstable": r.is_post_fill_unstable
        }
        for r in readings
    ]


@router.get("/usage-summary")
async def get_usage_summary(
    location_id: int = Query(...),
    days: int = Query(30),
    db: Session = Depends(get_db)
):
    """
    Calculate daily usage trends.
    Usage = difference between first and last clean reading of each day.
    Also estimates cost based on latest local oil price.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get clean readings (exclude anomalies and unstable)
    readings = db.query(TankReading).filter(
        TankReading.location_id == location_id,
        TankReading.timestamp >= start_date,
        TankReading.is_anomaly == False,
        TankReading.is_post_fill_unstable == False,
        TankReading.is_fill_event == False
    ).order_by(TankReading.timestamp).all()
    
    if not readings:
        return {
            "daily_usage": [],
            "total_usage": 0,
            "avg_daily_usage": 0,
            "estimated_cost": 0,
            "latest_price": None
        }
    
    # Group by date
    daily_data = {}
    for r in readings:
        day = r.timestamp.date()
        if day not in daily_data:
            daily_data[day] = {'first': r.gallons, 'last': r.gallons, 'first_ts': r.timestamp}
        else:
            daily_data[day]['last'] = r.gallons
    
    # Calculate daily usage (first reading - last reading = consumption)
    daily_usage = []
    for day in sorted(daily_data.keys()):
        data = daily_data[day]
        usage = max(0, data['first'] - data['last'])  # Ensure non-negative
        daily_usage.append({
            'date': day.isoformat(),
            'usage': round(usage, 2)
        })
    
    total_usage = sum(d['usage'] for d in daily_usage)
    avg_daily = total_usage / len(daily_usage) if daily_usage else 0
    
    # Get latest local oil price for cost estimation
    latest_price = db.query(OilPrice).join(Company).filter(
        Company.is_market_index == False
    ).order_by(desc(OilPrice.date_reported)).first()
    
    price_per_gallon = float(latest_price.price_per_gallon) if latest_price else 0
    estimated_cost = total_usage * price_per_gallon
    
    return {
        "daily_usage": daily_usage,
        "total_usage": round(total_usage, 2),
        "avg_daily_usage": round(avg_daily, 2),
        "estimated_cost": round(estimated_cost, 2),
        "latest_price": price_per_gallon,
        "days_analyzed": len(daily_usage)
    }


@router.get("/fill-events")
async def get_fill_events(
    location_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Get all detected fill events for a location."""
    fills = db.query(TankReading).filter(
        TankReading.location_id == location_id,
        TankReading.is_fill_event == True
    ).order_by(TankReading.timestamp.desc()).all()
    
    return [
        {
            "date": f.timestamp.isoformat(),
            "gallons_after_fill": f.gallons
        }
        for f in fills
    ]


@router.get("/current-level")
async def get_current_level(
    location_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """Get the most recent tank level."""
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    reading = db.query(TankReading).filter(
        TankReading.location_id == location_id,
        TankReading.is_anomaly == False
    ).order_by(TankReading.timestamp.desc()).first()
    
    if not reading:
        return {
            "current_gallons": None,
            "tank_capacity": location.tank_capacity,
            "percent_full": None,
            "last_reading": None
        }
    
    tank_capacity = location.tank_capacity or 275.0
    percent = (reading.gallons / tank_capacity) * 100 if tank_capacity > 0 else 0
    
    return {
        "current_gallons": round(reading.gallons, 1),
        "tank_capacity": tank_capacity,
        "percent_full": round(percent, 1),
        "last_reading": reading.timestamp.isoformat()
    }


@router.post("/recalculate-daily-usage")
async def recalculate_daily_usage(
    location_id: int = Query(..., description="Location ID to normalize"),
    days: Optional[int] = Query(None, description="Number of days back to recalculate (default: full history)"),
    db: Session = Depends(get_db)
):
    """
    Trigger a full recalculation of DailyUsage based on Orders and Tank Readings.
    This reconstructs the daily usage history using the UsageNormalizer service.
    """
    normalizer = UsageNormalizer(db)
    normalizer.recalculate_usage(location_id, days=days)
    
    count = db.query(DailyUsage).filter(DailyUsage.location_id == location_id).count()
    
    return {
        "message": "Recalculation complete",
        "days_processed": days if days else "all",
        "total_records": count
    }
