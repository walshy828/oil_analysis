from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import date, timedelta
from typing import Optional

from app.database import get_db
from app.models import OilPrice, OilOrder, Company, Temperature, Location, TankReading, DailyUsage

router = APIRouter()


@router.get("/summary")
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """Get dashboard summary with latest price, last order, and key metrics."""
    
    # Get latest oil price (excluding market indices)
    latest_price = db.query(OilPrice).join(Company).filter(
        Company.is_market_index == False
    ).order_by(desc(OilPrice.date_reported)).first()
    
    # Get cheapest vendor from latest scrape (local only)
    if latest_price:
        latest_date = latest_price.date_reported
        cheapest = db.query(OilPrice, Company).join(Company).filter(
            OilPrice.date_reported == latest_date,
            Company.is_market_index == False
        ).order_by(OilPrice.price_per_gallon).first()
    else:
        cheapest = None
    
    # Get last oil order
    last_order = db.query(OilOrder, Location, Company).outerjoin(
        Location, OilOrder.location_id == Location.id
    ).outerjoin(
        Company, OilOrder.company_id == Company.id
    ).order_by(desc(OilOrder.start_date)).first()
    
    # Calculate days since last delivery
    days_since_delivery = None
    if last_order:
        order, location, company = last_order
        days_since_delivery = (date.today() - order.start_date).days
    
    # Get average price for last 30 days (local only)
    thirty_days_ago = date.today() - timedelta(days=30)
    avg_price_30d = db.query(func.avg(OilPrice.price_per_gallon)).join(Company).filter(
        OilPrice.date_reported >= thirty_days_ago,
        Company.is_market_index == False
    ).scalar()
    
    # Get total gallons this year
    year_start = date(date.today().year, 1, 1)
    total_gallons_year = db.query(func.sum(OilOrder.gallons)).filter(
        OilOrder.start_date >= year_start
    ).scalar() or 0
    
    # Get total cost this year
    total_cost_year = db.query(
        func.sum(OilOrder.gallons * OilOrder.price_per_gallon)
    ).filter(OilOrder.start_date >= year_start).scalar() or 0
    
    return {
        "latest_price": {
            "price": float(latest_price.price_per_gallon) if latest_price else None,
            "date": latest_price.date_reported.isoformat() if latest_price else None,
            "company": cheapest[1].name if cheapest else None,
        } if latest_price else None,
        "cheapest_vendor": {
            "name": cheapest[1].name,
            "price": float(cheapest[0].price_per_gallon),
        } if cheapest else None,
        "last_order": {
            "date": last_order[0].start_date.isoformat(),
            "gallons": float(last_order[0].gallons),
            "total_cost": float(last_order[0].gallons * last_order[0].price_per_gallon),
            "location": last_order[1].name if last_order[1] else None,
            "company": last_order[2].name if last_order[2] else None,
        } if last_order else None,
        "days_since_delivery": days_since_delivery,
        "avg_price_30d": float(avg_price_30d) if avg_price_30d else None,
        "year_to_date": {
            "total_gallons": float(total_gallons_year),
            "total_cost": float(total_cost_year),
        }
    }


@router.get("/price-trends")
async def get_price_trends(
    days: int = 90,
    company_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get price trends for charting."""
    start_date = date.today() - timedelta(days=days)
    
    query = db.query(
        OilPrice.date_reported,
        func.min(OilPrice.price_per_gallon).label('min_price'),
        func.max(OilPrice.price_per_gallon).label('max_price'),
        func.avg(OilPrice.price_per_gallon).label('avg_price')
    ).join(Company).filter(OilPrice.date_reported >= start_date)
    
    if company_id:
        query = query.filter(OilPrice.company_id == company_id)
    else:
        # If no company specified, default to local deliveries only
        query = query.filter(Company.is_market_index == False)
    
    results = query.group_by(OilPrice.date_reported).order_by(OilPrice.date_reported).all()
    
    return {
        "labels": [r.date_reported.isoformat() for r in results],
        "datasets": {
            "min": [float(r.min_price) for r in results],
            "max": [float(r.max_price) for r in results],
            "avg": [float(r.avg_price) for r in results],
        }
    }


@router.get("/order-trends")
async def get_order_trends(
    months: int = 12,
    location_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get order trends for charting."""
    # Get orders from last N months
    start_date = date.today() - timedelta(days=months * 30)
    
    query = db.query(OilOrder, Location, Company).outerjoin(
        Location, OilOrder.location_id == Location.id
    ).outerjoin(
        Company, OilOrder.company_id == Company.id
    ).filter(OilOrder.start_date >= start_date)
    
    if location_id:
        query = query.filter(OilOrder.location_id == location_id)
    
    orders = query.order_by(OilOrder.start_date).all()
    
    return {
        "orders": [
            {
                "date": order.start_date.isoformat(),
                "gallons": float(order.gallons),
                "price_per_gallon": float(order.price_per_gallon),
                "total_cost": float(order.gallons * order.price_per_gallon),
                "location": location.name if location else None,
                "company": company.name if company else None,
            }
            for order, location, company in orders
        ]
    }


@router.get("/temperature-correlation")
async def get_temperature_correlation(
    days: int = 365,
    location_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get temperature and oil usage data for correlation."""
    start_date = date.today() - timedelta(days=days)
    
    # Get temperatures
    query = db.query(Temperature).filter(Temperature.date >= start_date)
    if location_id:
        query = query.filter(Temperature.location_id == location_id)
    temps = query.order_by(Temperature.date).all()
    
    # Get daily usage from normalized table
    usage_query = db.query(DailyUsage).filter(DailyUsage.date >= start_date)
    
    if location_id:
        usage_query = usage_query.filter(DailyUsage.location_id == location_id)
        
    usage_records = usage_query.order_by(DailyUsage.date).all()
    
    usage_data = [
        {
            "date": r.date.isoformat(),
            "gallons": float(r.gallons)
        }
        for r in usage_records
    ]
    
    return {
        "temperatures": {
            "labels": [t.date.isoformat() for t in temps],
            "low": [float(t.low_temp) if t.low_temp else None for t in temps],
            "high": [float(t.high_temp) if t.high_temp else None for t in temps],
            "avg": [
                (float(t.low_temp) + float(t.high_temp)) / 2 
                if t.low_temp and t.high_temp else None 
                for t in temps
            ],
        },
        "orders": usage_data  # Returning usage as 'orders' key for compatibility
    }
