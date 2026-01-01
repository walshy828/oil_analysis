from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional
from datetime import date, timedelta
import csv
import io
import httpx

from app.database import get_db
from app.models import Temperature, Location, TankReading

router = APIRouter()

# Base temperature for HDD calculation (standard is 65°F)
HDD_BASE_TEMP = 65.0


def calculate_hdd(avg_temp: float, base_temp: float = HDD_BASE_TEMP) -> float:
    """Calculate Heating Degree Days.
    HDD = max(0, base_temp - avg_temp)
    Higher HDD = more heating needed = more oil usage.
    """
    return max(0, base_temp - avg_temp)


@router.get("", response_model=List[dict])
async def list_temperatures(
    skip: int = 0,
    limit: int = 365,
    location_id: int = None,
    date_from: date = None,
    date_to: date = None,
    db: Session = Depends(get_db)
):
    """List temperature records with optional filtering."""
    query = db.query(Temperature)
    
    if location_id:
        query = query.filter(Temperature.location_id == location_id)
    
    if date_from:
        query = query.filter(Temperature.date >= date_from)
    
    if date_to:
        query = query.filter(Temperature.date <= date_to)
    
    temps = query.order_by(desc(Temperature.date)).offset(skip).limit(limit).all()
    
    results = []
    for t in temps:
        avg = t.avg_temp
        hdd = calculate_hdd(avg) if avg is not None else None
        results.append({
            "id": t.id,
            "location_id": t.location_id,
            "date": t.date,
            "low_temp": float(t.low_temp) if t.low_temp else None,
            "high_temp": float(t.high_temp) if t.high_temp else None,
            "avg_temp": avg,
            "hdd": hdd,
        })
    
    return results


@router.post("", response_model=dict)
async def create_temperature(
    location_id: Optional[int] = None,
    temp_date: date = Query(..., alias="date"),
    low_temp: Optional[float] = None,
    high_temp: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Create a single temperature record."""
    # Check for existing record
    existing = db.query(Temperature).filter(
        Temperature.location_id == location_id,
        Temperature.date == temp_date
    ).first()
    
    if existing:
        # Update existing record
        existing.low_temp = low_temp
        existing.high_temp = high_temp
        db.commit()
        db.refresh(existing)
        avg = existing.avg_temp
        return {
            "id": existing.id,
            "location_id": existing.location_id,
            "date": existing.date,
            "low_temp": float(existing.low_temp) if existing.low_temp else None,
            "high_temp": float(existing.high_temp) if existing.high_temp else None,
            "avg_temp": avg,
            "hdd": calculate_hdd(avg) if avg else None,
        }
    
    db_temp = Temperature(location_id=location_id, date=temp_date, low_temp=low_temp, high_temp=high_temp)
    db.add(db_temp)
    db.commit()
    db.refresh(db_temp)
    avg = db_temp.avg_temp
    return {
        "id": db_temp.id,
        "location_id": db_temp.location_id,
        "date": db_temp.date,
        "low_temp": float(db_temp.low_temp) if db_temp.low_temp else None,
        "high_temp": float(db_temp.high_temp) if db_temp.high_temp else None,
        "avg_temp": avg,
        "hdd": calculate_hdd(avg) if avg else None,
    }


@router.post("/fetch-weather")
async def fetch_weather_data(
    latitude: float = Query(..., description="Location latitude"),
    longitude: float = Query(..., description="Location longitude"),
    location_id: Optional[int] = None,
    start_date: date = Query(None, description="Start date (defaults to 30 days ago)"),
    end_date: date = Query(None, description="End date (defaults to yesterday)"),
    db: Session = Depends(get_db)
):
    """
    Fetch historical weather data from Open-Meteo API (free, no API key needed).
    Data includes daily min/max temperatures.
    """
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today() - timedelta(days=1)
    
    # Open-Meteo historical weather API
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit",
        "timezone": "America/New_York"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=30.0)
        
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Weather API error: {response.text}")
        
        data = response.json()
    
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    
    created = 0
    updated = 0
    
    for i, d in enumerate(dates):
        temp_date = date.fromisoformat(d)
        high = highs[i] if i < len(highs) and highs[i] is not None else None
        low = lows[i] if i < len(lows) and lows[i] is not None else None
        
        existing = db.query(Temperature).filter(
            Temperature.location_id == location_id,
            Temperature.date == temp_date
        ).first()
        
        if existing:
            existing.low_temp = low
            existing.high_temp = high
            updated += 1
        else:
            db.add(Temperature(
                location_id=location_id,
                date=temp_date,
                low_temp=low,
                high_temp=high
            ))
            created += 1
    
    db.commit()
    
    return {
        "message": "Weather data fetched successfully",
        "created": created,
        "updated": updated,
        "date_range": f"{start_date} to {end_date}"
    }


@router.get("/hdd-summary")
async def get_hdd_summary(
    location_id: Optional[int] = None,
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get Heating Degree Days (HDD) summary.
    HDD is the standard measure for heating fuel demand.
    Higher HDD = colder weather = more oil usage.
    """
    start_date = date.today() - timedelta(days=days)
    
    query = db.query(Temperature).filter(Temperature.date >= start_date)
    if location_id:
        query = query.filter(Temperature.location_id == location_id)
    
    temps = query.order_by(Temperature.date).all()
    
    daily_data = []
    total_hdd = 0
    
    for t in temps:
        avg = t.avg_temp
        if avg is not None:
            hdd = calculate_hdd(avg)
            total_hdd += hdd
            daily_data.append({
                "date": t.date.isoformat(),
                "avg_temp": round(avg, 1),
                "hdd": round(hdd, 1)
            })
    
    return {
        "total_hdd": round(total_hdd, 1),
        "avg_daily_hdd": round(total_hdd / len(daily_data), 1) if daily_data else 0,
        "days_analyzed": len(daily_data),
        "daily_data": daily_data
    }


@router.get("/usage-correlation")
async def get_usage_correlation(
    location_id: int = Query(..., description="Location ID"),
    days: int = Query(90, description="Days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Analyze correlation between temperature (HDD) and oil usage.
    Returns daily data combining HDD and oil consumption for visualization.
    """
    start_date = date.today() - timedelta(days=days)
    
    # Get temperature data
    temps = db.query(Temperature).filter(
        Temperature.location_id == location_id,
        Temperature.date >= start_date
    ).order_by(Temperature.date).all()
    
    # Get tank readings for usage calculation
    readings = db.query(TankReading).filter(
        TankReading.location_id == location_id,
        TankReading.timestamp >= start_date,
        TankReading.is_anomaly == False,
        TankReading.is_post_fill_unstable == False,
        TankReading.is_fill_event == False
    ).order_by(TankReading.timestamp).all()
    
    # Calculate daily usage
    daily_usage = {}
    for r in readings:
        day = r.timestamp.date()
        if day not in daily_usage:
            daily_usage[day] = {'first': r.gallons, 'last': r.gallons}
        else:
            daily_usage[day]['last'] = r.gallons
    
    # Calculate actual usage per day
    usage_by_date = {}
    for day, data in daily_usage.items():
        usage = max(0, data['first'] - data['last'])
        usage_by_date[day] = round(usage, 2)
    
    # Combine temperature and usage data
    combined_data = []
    for t in temps:
        avg = t.avg_temp
        if avg is not None:
            hdd = calculate_hdd(avg)
            usage = usage_by_date.get(t.date, 0)
            combined_data.append({
                "date": t.date.isoformat(),
                "avg_temp": round(avg, 1),
                "hdd": round(hdd, 1),
                "usage": usage
            })
    
    # Calculate correlation coefficient if we have enough data
    correlation = None
    if len(combined_data) >= 7:
        hdds = [d['hdd'] for d in combined_data if d['usage'] > 0]
        usages = [d['usage'] for d in combined_data if d['usage'] > 0]
        
        if len(hdds) >= 7 and sum(usages) > 0:
            # Simple correlation calculation
            n = len(hdds)
            sum_hdd = sum(hdds)
            sum_usage = sum(usages)
            sum_hdd_usage = sum(h * u for h, u in zip(hdds, usages))
            sum_hdd_sq = sum(h * h for h in hdds)
            sum_usage_sq = sum(u * u for u in usages)
            
            numerator = n * sum_hdd_usage - sum_hdd * sum_usage
            denominator = ((n * sum_hdd_sq - sum_hdd ** 2) * (n * sum_usage_sq - sum_usage ** 2)) ** 0.5
            
            if denominator > 0:
                correlation = round(numerator / denominator, 3)
    
    return {
        "location_id": location_id,
        "days_analyzed": len(combined_data),
        "correlation": correlation,
        "correlation_interpretation": (
            "Strong positive" if correlation and correlation > 0.7 else
            "Moderate positive" if correlation and correlation > 0.4 else
            "Weak positive" if correlation and correlation > 0.1 else
            "No correlation" if correlation is not None else
            "Insufficient data"
        ),
        "daily_data": combined_data
    }


@router.post("/upload")
async def upload_temperature_csv(
    file: UploadFile = File(...),
    location_id: int = None,
    db: Session = Depends(get_db)
):
    """Upload temperature data from a CSV file.
    
    Expected CSV format:
    date,low_temp,high_temp
    2024-01-01,20,35
    2024-01-02,18,32
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    decoded = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))
    
    created = 0
    updated = 0
    errors = []
    
    for row_num, row in enumerate(reader, start=2):
        try:
            temp_date = date.fromisoformat(row.get('date', '').strip())
            low_temp = float(row.get('low_temp', '').strip()) if row.get('low_temp', '').strip() else None
            high_temp = float(row.get('high_temp', '').strip()) if row.get('high_temp', '').strip() else None
            
            existing = db.query(Temperature).filter(
                Temperature.location_id == location_id,
                Temperature.date == temp_date
            ).first()
            
            if existing:
                existing.low_temp = low_temp
                existing.high_temp = high_temp
                updated += 1
            else:
                db_temp = Temperature(
                    location_id=location_id,
                    date=temp_date,
                    low_temp=low_temp,
                    high_temp=high_temp
                )
                db.add(db_temp)
                created += 1
        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")
    
    db.commit()
    
    return {
        "created": created,
        "updated": updated,
        "errors": errors[:10] if errors else [],
        "total_errors": len(errors)
    }


@router.delete("/{temperature_id}")
async def delete_temperature(temperature_id: int, db: Session = Depends(get_db)):
    """Delete a temperature record."""
    temp = db.query(Temperature).filter(Temperature.id == temperature_id).first()
    if not temp:
        raise HTTPException(status_code=404, detail="Temperature record not found")
    
    db.delete(temp)
    db.commit()
    return {"message": "Temperature record deleted"}

