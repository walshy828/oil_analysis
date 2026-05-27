"""
Historical data import for market indices.
- Yahoo Finance: Uses chart API for historical prices
- EIA: Uses their open data API (key from environment only)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
import httpx

from app.database import get_db
from app.models import OilPrice
from app.config import settings
from app.services.company_service import find_or_create_market_company

router = APIRouter()

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
EIA_API_URL = "https://api.eia.gov/v2/petroleum/pri/spt/data/"

YAHOO_SYMBOLS = {
    "ulsd":     {"symbol": "HO=F",  "name": "Market Index: NY Harbor ULSD"},
    "brent":    {"symbol": "BZ=F",  "name": "Market Index: Brent Crude"},
    "wti":      {"symbol": "CL=F",  "name": "Market Index: WTI Crude"},
    "gasoline": {"symbol": "RB=F",  "name": "Market Index: RBOB Gasoline"},
}

EIA_SERIES = {
    "wti":      {"series_id": "RWTC",                      "name": "EIA Index: WTI Crude Spot"},
    "brent":    {"series_id": "RBRTE",                     "name": "EIA Index: Brent Crude Spot"},
    "ulsd":     {"series_id": "EER_EPD2DXL0_PF4_RGC_DPG", "name": "EIA Index: NY Harbor ULSD Spot"},
    "gasoline": {"series_id": "EER_EPMRR_PF4_RGC_DPG",    "name": "EIA Index: NY Harbor Gasoline Spot"},
}


@router.post("/yahoo-finance")
async def import_yahoo_historical(
    symbol: str = Query(..., description="Symbol key: ulsd, brent, wti, gasoline"),
    days: Optional[int] = Query(None, description="Number of days of history to import"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    db: Session = Depends(get_db)
):
    """Import historical data from Yahoo Finance chart API."""
    if symbol not in YAHOO_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Unknown symbol. Valid: {list(YAHOO_SYMBOLS.keys())}")

    info = YAHOO_SYMBOLS[symbol]

    if start_date and end_date:
        start_time = int(datetime.combine(start_date, datetime.min.time()).timestamp())
        end_time = int(datetime.combine(end_date, datetime.max.time()).timestamp())
    elif days:
        end_time = int(datetime.now().timestamp())
        start_time = int((datetime.now() - timedelta(days=days)).timestamp())
    else:
        end_time = int(datetime.now().timestamp())
        start_time = int((datetime.now() - timedelta(days=365)).timestamp())

    url = YAHOO_CHART_URL.format(symbol=info["symbol"])
    params = {
        "period1": start_time,
        "period2": end_time,
        "interval": "1d",
        "includePrePost": "false",
    }
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=headers, timeout=30.0)
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Yahoo Finance API error: {response.status_code}")
        data = response.json()

    try:
        chart = data["chart"]["result"][0]
        timestamps = chart["timestamp"]
        closes = chart["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError) as e:
        raise HTTPException(status_code=502, detail=f"Failed to parse Yahoo data: {e}")

    company = find_or_create_market_company(db, info["name"], "https://finance.yahoo.com")

    existing_dates = {
        d[0] for d in db.query(OilPrice.date_reported).filter(OilPrice.company_id == company.id).all()
    }

    created = 0
    skipped = 0
    for i, ts in enumerate(timestamps):
        if closes[i] is None:
            continue
        price_date = datetime.fromtimestamp(ts).date()
        if price_date in existing_dates:
            skipped += 1
            continue
        db.add(OilPrice(
            company_id=company.id,
            price_per_gallon=Decimal(str(round(closes[i], 4))),
            town="NYMEX / Global",
            date_reported=price_date,
        ))
        created += 1

    db.commit()

    return {
        "message": f"Imported historical data for {info['name']}",
        "symbol": info["symbol"],
        "created": created,
        "skipped": skipped,
        "date_range": (
            f"{datetime.fromtimestamp(timestamps[0]).date()} to {datetime.fromtimestamp(timestamps[-1]).date()}"
            if timestamps else "N/A"
        ),
    }


@router.post("/eia")
async def import_eia_historical(
    series: str = Query(..., description="Series key: wti, brent, ulsd, gasoline"),
    start_date: date = Query(None, description="Start date (defaults to 1 year ago)"),
    end_date: date = Query(None, description="End date (defaults to today)"),
    db: Session = Depends(get_db)
):
    """
    Import historical spot prices from EIA.gov API.
    Requires EIA_API_KEY environment variable.
    """
    if not settings.eia_api_key:
        raise HTTPException(
            status_code=400,
            detail="EIA_API_KEY is not configured on the server. Set the environment variable."
        )
    if series not in EIA_SERIES:
        raise HTTPException(status_code=400, detail=f"Unknown series. Valid: {list(EIA_SERIES.keys())}")

    info = EIA_SERIES[series]
    if not start_date:
        start_date = date.today() - timedelta(days=365)
    if not end_date:
        end_date = date.today()

    params = {
        "api_key": settings.eia_api_key,
        "frequency": "daily",
        "data[0]": "value",
        "facets[series][]": info["series_id"],
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(EIA_API_URL, params=params, timeout=30.0)
        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"EIA API error: {response.status_code}. Check your API key."
            )
        data = response.json()

    try:
        records = data["response"]["data"]
    except (KeyError, TypeError):
        raise HTTPException(status_code=502, detail="Failed to parse EIA response")

    if not records:
        return {"message": "No data found for the specified date range", "created": 0, "skipped": 0}

    company = find_or_create_market_company(db, info["name"], "https://www.eia.gov")
    existing_dates = {
        d[0] for d in db.query(OilPrice.date_reported).filter(OilPrice.company_id == company.id).all()
    }

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
            db.add(OilPrice(
                company_id=company.id,
                price_per_gallon=Decimal(str(round(float(value), 4))),
                town="EIA Spot / Global",
                date_reported=price_date,
            ))
            created += 1
        except (KeyError, ValueError):
            continue

    db.commit()

    return {
        "message": f"Imported historical EIA data for {info['name']}",
        "series": info["series_id"],
        "created": created,
        "skipped": skipped,
        "date_range": f"{start_date} to {end_date}",
    }


@router.get("/available-symbols")
async def list_available_symbols():
    return {
        "yahoo_finance": {k: {"symbol": v["symbol"], "name": v["name"]} for k, v in YAHOO_SYMBOLS.items()},
        "eia": {k: {"series_id": v["series_id"], "name": v["name"]} for k, v in EIA_SERIES.items()},
        "notes": {
            "yahoo_finance": "No API key required.",
            "eia": "Requires EIA_API_KEY environment variable (free at eia.gov).",
        },
        "eia_key_configured": settings.eia_api_key is not None,
    }


@router.post("/eia/crack-spread-bulk")
async def import_eia_crack_spread_components(
    days: int = Query(365, description="Number of days to import"),
    db: Session = Depends(get_db)
):
    """Convenience endpoint to import all components needed for 3:2:1 crack spread."""
    if not settings.eia_api_key:
        raise HTTPException(
            status_code=400,
            detail="EIA_API_KEY is not configured on the server."
        )

    start_date = date.today() - timedelta(days=days)
    results = []

    for comp in ["wti", "ulsd", "gasoline"]:
        try:
            res = await import_eia_historical(comp, start_date, date.today(), db)
            results.append(res)
        except Exception as e:
            results.append({"series": comp, "error": str(e)})

    return {"message": "Bulk import completed", "results": results}
