"""
Historical data import for market indices.
- Yahoo Finance: Uses chart API for historical prices
- EIA: Uses their open data API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict
import httpx

from app.database import get_db
from app.models import Company, OilPrice
from app.config import settings

router = APIRouter()

# Yahoo Finance historical chart API
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# EIA Open Data API (free with key)
EIA_API_URL = "https://api.eia.gov/v2/petroleum/pri/spt/data/"

# Symbol mappings
YAHOO_SYMBOLS = {
    "ulsd": {"symbol": "HO=F", "name": "Market Index: NY Harbor ULSD"},
    "brent": {"symbol": "BZ=F", "name": "Market Index: Brent Crude"},
    "wti": {"symbol": "CL=F", "name": "Market Index: WTI Crude"},
    "gasoline": {"symbol": "RB=F", "name": "Market Index: RBOB Gasoline"},
}

EIA_SERIES = {
    "wti": {"series_id": "RWTC", "name": "EIA Index: WTI Crude Spot"},
    "brent": {"series_id": "RBRTE", "name": "EIA Index: Brent Crude Spot"},
    "ulsd": {"series_id": "EER_EPD2DXL0_PF4_RGC_DPG", "name": "EIA Index: NY Harbor ULSD Spot"},
    "gasoline": {"series_id": "EER_EPMRR_PF4_RGC_DPG", "name": "EIA Index: NY Harbor Gasoline Spot"},
}


def _find_or_create_company(db: Session, name: str, website: str) -> Company:
    """Get or create a market index company."""
    company = db.query(Company).filter(Company.name == name).first()
    if not company:
        company = Company(
            name=name,
            is_market_index=True,
            website=website,
            phone="N/A"
        )
        db.add(company)
        db.commit()
        db.refresh(company)
    return company


@router.post("/yahoo-finance")
async def import_yahoo_historical(
    symbol: str = Query(..., description="Symbol key: ulsd, brent, wti, gasoline"),
    days: Optional[int] = Query(None, description="Number of days of history to import"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    db: Session = Depends(get_db)
):
    """
    Import historical data from Yahoo Finance.
    Uses their chart API to get OHLC data.
    """
    if symbol not in YAHOO_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Unknown symbol. Valid: {list(YAHOO_SYMBOLS.keys())}")
    
    info = YAHOO_SYMBOLS[symbol]
    yahoo_symbol = info["symbol"]
    
    # Calculate time range
    if start_date and end_date:
        # Convert date to timestamp (Yahoo wants seconds)
        start_time = int(datetime.combine(start_date, datetime.min.time()).timestamp())
        end_time = int(datetime.combine(end_date, datetime.max.time()).timestamp())
    elif days:
        end_time = int(datetime.now().timestamp())
        start_time = int((datetime.now() - timedelta(days=days)).timestamp())
    else:
        # Default to 365 days if nothing provided
        end_time = int(datetime.now().timestamp())
        start_time = int((datetime.now() - timedelta(days=365)).timestamp())
    
    url = YAHOO_CHART_URL.format(symbol=yahoo_symbol)
    params = {
        "period1": start_time,
        "period2": end_time,
        "interval": "1d",  # Daily data
        "includePrePost": "false"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=headers, timeout=30.0)
        
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Yahoo Finance API error: {response.status_code}")
        
        data = response.json()
    
    # Parse response
    try:
        chart = data["chart"]["result"][0]
        timestamps = chart["timestamp"]
        closes = chart["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError) as e:
        raise HTTPException(status_code=502, detail=f"Failed to parse Yahoo data: {e}")
    
    # Find or create company
    company = _find_or_create_company(db, info["name"], "https://finance.yahoo.com")
    
    # Get existing dates to avoid duplicates
    existing_dates = set(
        d[0] for d in db.query(OilPrice.date_reported).filter(
            OilPrice.company_id == company.id
        ).all()
    )
    
    created = 0
    skipped = 0
    
    for i, ts in enumerate(timestamps):
        if closes[i] is None:
            continue
            
        price_date = datetime.fromtimestamp(ts).date()
        
        if price_date in existing_dates:
            skipped += 1
            continue
        
        oil_price = OilPrice(
            company_id=company.id,
            price_per_gallon=Decimal(str(round(closes[i], 4))),
            town="NYMEX / Global",
            date_reported=price_date
        )
        db.add(oil_price)
        created += 1
    
    db.commit()
    
    return {
        "message": f"Imported historical data for {info['name']}",
        "symbol": yahoo_symbol,
        "created": created,
        "skipped": skipped,
        "date_range": f"{datetime.fromtimestamp(timestamps[0]).date()} to {datetime.fromtimestamp(timestamps[-1]).date()}" if timestamps else "N/A"
    }


@router.post("/eia")
async def import_eia_historical(
    series: str = Query(..., description="Series key: wti, brent, ulsd, gasoline"),
    api_key: Optional[str] = Query(None, description="EIA API key (get free at eia.gov)"),
    start_date: date = Query(None, description="Start date (defaults to 1 year ago)"),
    end_date: date = Query(None, description="End date (defaults to today)"),
    db: Session = Depends(get_db)
):
    """
    Import historical spot prices from EIA.gov API.
    Fallback to environment EIA_API_KEY if not provided.
    """
    effective_api_key = api_key or settings.eia_api_key
    if not effective_api_key:
        raise HTTPException(status_code=400, detail="EIA API key required. Provide in request or set in environment.")
    
    if series not in EIA_SERIES:
        raise HTTPException(status_code=400, detail=f"Unknown series. Valid: {list(EIA_SERIES.keys())}")
    
    info = EIA_SERIES[series]
    
    if not start_date:
        start_date = date.today() - timedelta(days=365)
    if not end_date:
        end_date = date.today()
    
    # EIA API v2 request
    params = {
        "api_key": effective_api_key,
        "frequency": "daily",
        "data[0]": "value",
        "facets[series][]": info["series_id"],
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "sort[0][column]": "period",
        "sort[0][direction]": "asc"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(EIA_API_URL, params=params, timeout=30.0)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=502, 
                detail=f"EIA API error: {response.status_code}. Check your API key."
            )
        
        data = response.json()
    
    # Parse response
    try:
        records = data["response"]["data"]
    except (KeyError, TypeError):
        raise HTTPException(status_code=502, detail="Failed to parse EIA response")
    
    if not records:
        return {
            "message": "No data found for the specified date range",
            "series": info["series_id"],
            "created": 0,
            "skipped": 0
        }
    
    # Find or create company
    company = _find_or_create_company(db, info["name"], "https://www.eia.gov")
    
    # Get existing dates to avoid duplicates
    existing_dates = set(
        d[0] for d in db.query(OilPrice.date_reported).filter(
            OilPrice.company_id == company.id
        ).all()
    )
    
    created = 0
    skipped = 0
    
    for record in records:
        try:
            price_date = date.fromisoformat(record["period"])
            value = record["value"]
            
            if value is None:
                continue
                
            if price_date in existing_dates:
                skipped += 1
                continue
            
            oil_price = OilPrice(
                company_id=company.id,
                price_per_gallon=Decimal(str(round(float(value), 4))),
                town="EIA Spot / Global",
                date_reported=price_date
            )
            db.add(oil_price)
            created += 1
            
        except (KeyError, ValueError) as e:
            continue
    
    db.commit()
    
    return {
        "message": f"Imported historical EIA data for {info['name']}",
        "series": info["series_id"],
        "created": created,
        "skipped": skipped,
        "date_range": f"{start_date} to {end_date}"
    }


@router.get("/available-symbols")
async def list_available_symbols():
    """List all available symbols for historical import."""
    return {
        "yahoo_finance": {
            key: {"symbol": v["symbol"], "name": v["name"]} 
            for key, v in YAHOO_SYMBOLS.items()
        },
        "eia": {
            key: {"series_id": v["series_id"], "name": v["name"]} 
            for key, v in EIA_SERIES.items()
        },
        "notes": {
            "yahoo_finance": "No API key required. Data from Yahoo Finance chart API.",
            "eia": "Requires free API key from https://www.eia.gov/opendata/register.php"
        },
        "eia_key_configured": settings.eia_api_key is not None
    }
@router.post("/eia/crack-spread-bulk")
async def import_eia_crack_spread_components(
    api_key: Optional[str] = Query(None, description="EIA API key"),
    days: int = Query(365, description="Number of days to import"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint to import all components needed for 3:2:1 Crack Spread.
    Fallback to environment EIA_API_KEY if not provided.
    """
    effective_api_key = api_key or settings.eia_api_key
    if not effective_api_key:
        raise HTTPException(status_code=400, detail="EIA API key required. Provide in request or set in environment.")

    components = ["wti", "ulsd", "gasoline"]
    results = []
    
    start_date = date.today() - timedelta(days=days)
    
    for comp in components:
        try:
            res = await import_eia_historical(comp, effective_api_key, start_date, date.today(), db)
            results.append(res)
        except Exception as e:
            results.append({"series": comp, "error": str(e)})
            
    return {
        "message": "Bulk import completed",
        "results": results
    }
