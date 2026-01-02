from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict
from statistics import mean

from app.database import get_db
from app.models import OilPrice, Company, OilOrder, Temperature

router = APIRouter()

@router.get("/company-trends")
async def get_company_trends(
    company_ids: List[int] = Query(...),
    date_from: date = Query(None),
    date_to: date = Query(None),
    aggregation: str = Query("daily", enum=["daily", "weekly", "monthly"]),
    db: Session = Depends(get_db)
):
    """Fetch price trends for multiple companies with forward-filling and aggregation."""
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=90)
        
    companies = db.query(Company).filter(Company.id.in_(company_ids)).all()
    company_map = {c.id: c.name for c in companies}
    
    results = {}
    all_dates = set()
    
    for cid in company_ids:
        prices = db.query(OilPrice.date_reported, OilPrice.price_per_gallon).filter(
            OilPrice.company_id == cid,
            OilPrice.date_reported >= date_from,
            OilPrice.date_reported <= date_to
        ).order_by(OilPrice.date_reported).all()
        
        # Forward fill
        series = {}
        curr = date_from
        last_val = None
        data_map = {p.date_reported: float(p.price_per_gallon) for p in prices}
        
        while curr <= date_to:
            val = data_map.get(curr)
            if val is not None:
                last_val = val
            series[curr.isoformat()] = last_val
            curr += timedelta(days=1)
            
        agg = aggregate_series(series, aggregation)
        results[str(cid)] = {
            "name": company_map.get(cid, f"Company {cid}"),
            "data": agg
        }
        all_dates.update(agg.keys())
        
    return {
        "dates": sorted(list(all_dates)),
        "trends": results
    }

def aggregate_series(series: Dict[str, float], aggregation: str) -> Dict[str, float]:
    """Aggregate a timeseries (date_str -> value) by day, week, or month."""
    if aggregation == "daily":
        return series
        
    grouped = {}
    for d_str, val in series.items():
        dt = date.fromisoformat(d_str)
        if aggregation == "weekly":
            # Start of week (Sunday)
            key = (dt - timedelta(days=dt.weekday() + 1 if dt.weekday() != 6 else 0)).isoformat()
        elif aggregation == "monthly":
            key = dt.replace(day=1).isoformat()
        else:
            key = d_str
            
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(val)
        
    return {k: round(mean(v), 4) for k, v in grouped.items()}


@router.get("/lead-lag")
async def get_lead_lag_analysis(
    date_from: date = Query(None),
    date_to: date = Query(None),
    aggregation: str = Query("daily", enum=["daily", "weekly", "monthly"]),
    db: Session = Depends(get_db)
):
    """
    Compare NY Harbor ULSD Futures (Market) vs Local Retail Prices.
    Includes forward-filling for gaps and multi-term trend analysis.
    """
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=90)
    
    # 1. Fetch NY Harbor ULSD Futures
    market_prices = db.query(OilPrice).join(Company).filter(
        Company.name == "Market Index: NY Harbor ULSD",
        OilPrice.date_reported >= date_from,
        OilPrice.date_reported <= date_to
    ).order_by(OilPrice.date_reported).all()
    
    # 2. Fetch Average Local Retail Price per day
    local_avg_daily = db.query(
        OilPrice.date_reported,
        func.avg(OilPrice.price_per_gallon).label('avg_price')
    ).join(Company).filter(
        Company.is_market_index == False,
        OilPrice.date_reported >= date_from,
        OilPrice.date_reported <= date_to
    ).group_by(OilPrice.date_reported).order_by(OilPrice.date_reported).all()
    
    # Create forward-filled series
    def forward_fill(data_points, start, end):
        res = {}
        curr = start
        last_val = None
        data_map = {p.date_reported: float(getattr(p, 'price_per_gallon', getattr(p, 'avg_price', 0))) for p in data_points}
        
        while curr <= end:
            val = data_map.get(curr)
            if val is not None:
                last_val = val
            res[curr.isoformat()] = last_val
            curr += timedelta(days=1)
        return res

    market_full = forward_fill(market_prices, date_from, date_to)
    local_full = forward_fill(local_avg_daily, date_from, date_to)
    
    # Aggregate
    market_series = aggregate_series(market_full, aggregation)
    local_series = aggregate_series(local_full, aggregation)
    
    # Multi-term trends (Local)
    def get_trend(series_map, days):
        d_to = date_to.isoformat()
        d_prev = (date_to - timedelta(days=days)).isoformat()
        v_to = series_map.get(d_to)
        v_prev = series_map.get(d_prev)
        if v_to is not None and v_prev is not None:
            return round(v_to - v_prev, 4)
        return 0

    local_trend_7d = get_trend(local_full, 7)
    local_trend_30d = get_trend(local_full, 30)
    local_trend_90d = get_trend(local_full, 90)
    
    # Market (Futures) Trend for prediction
    market_trend_7d = get_trend(market_full, 7)
    
    # 3. Consider Crack Spread for Prediction
    # We'll peak at the latest crack spread
    crack_res = await get_crack_spread(date_from=date_to - timedelta(days=7), date_to=date_to, db=db)
    latest_spread = crack_res[-1]["spread"] if crack_res else 0
    prev_spread = crack_res[0]["spread"] if len(crack_res) > 1 else latest_spread
    spread_delta = latest_spread - prev_spread

    # Prediction Logic
    # 1. Futures Lead: Futures usually lead local prices by 2-5 days
    # 2. Crack Spread: Widening spread (high margin) means refined product is expensive. 
    #    If spread is rising, it adds upward pressure even if crude is flat.
    
    score = 0
    if market_trend_7d > 0.05: score += 2  # Strong futures hike
    elif market_trend_7d > 0.02: score += 1
    elif market_trend_7d < -0.05: score -= 2 # Strong futures drop
    elif market_trend_7d < -0.02: score -= 1
    
    if spread_delta > 1.0: score += 1 # Widening spread adds pressure
    elif spread_delta < -1.0: score -= 1 # Narrows spread relieves pressure
    
    prediction = "Stable"
    if score >= 2: prediction = "Rise Likely"
    elif score >= 1: prediction = "Slight Upward Pressure"
    elif score <= -2: prediction = "Fall Likely"
    elif score <= -1: prediction = "Slight Downward Pressure"
        
    return {
        "analysis": {
            "prediction": prediction,
            "futures_trend_7d": round(market_trend_7d, 4),
            "local_trends": {
                "7d": local_trend_7d,
                "30d": local_trend_30d,
                "90d": local_trend_90d
            },
            "crack_spread_impact": "Positive" if spread_delta > 0 else "Negative" if spread_delta < 0 else "Neutral"
        },
        "series": {
            "dates": sorted(list(market_series.keys())),
            "market_ulds": market_series,
            "local_avg": local_series
        }
    }

@router.get("/company-rankings")
async def get_company_rankings(
    date_from: date = Query(None),
    date_to: date = Query(None),
    db: Session = Depends(get_db)
):
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=30)
        
    # Subquery for latest price per company
    latest_prices_sub = db.query(
        OilPrice.company_id,
        OilPrice.price_per_gallon,
        OilPrice.date_reported,
        func.row_number().over(
            partition_by=OilPrice.company_id,
            order_by=desc(OilPrice.date_reported)
        ).label('rn')
    ).subquery()

    rankings = db.query(
        Company.name,
        func.avg(OilPrice.price_per_gallon).label('avg_price'),
        func.count(OilPrice.id).label('sample_count'),
        latest_prices_sub.c.price_per_gallon.label('latest_price'),
        latest_prices_sub.c.date_reported.label('latest_date')
    ).join(OilPrice).join(
        latest_prices_sub, and_(
            latest_prices_sub.c.company_id == Company.id,
            latest_prices_sub.c.rn == 1
        )
    ).filter(
        Company.is_market_index == False,
        OilPrice.date_reported >= date_from,
        OilPrice.date_reported <= date_to,
        Company.merged_into_id == None
    ).group_by(
        Company.name, 
        latest_prices_sub.c.price_per_gallon, 
        latest_prices_sub.c.date_reported
    ).having(
        func.count(OilPrice.id) >= 2
    ).order_by(func.avg(OilPrice.price_per_gallon)).limit(10).all()
    
    return [
        {
            "company": r.name,
            "avg_price": float(r.avg_price),
            "samples": r.sample_count,
            "latest_price": float(r.latest_price),
            "latest_date": r.latest_date.isoformat()
        }
        for r in rankings
    ]

@router.get("/crack-spread")
async def get_crack_spread(
    date_from: date = Query(None),
    date_to: date = Query(None),
    aggregation: str = Query("daily", enum=["daily", "weekly", "monthly"]),
    db: Session = Depends(get_db)
):
    """
    Calculate 3:2:1 Crack Spread.
    Formula: 28*Gas + 14*Diesel - Crude (normalized to BBL)
    """
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=180)
    
    def get_series_robust(aliases: List[str]):
        """Try multiple names for the same series."""
        res = db.query(OilPrice.date_reported, OilPrice.price_per_gallon).join(Company).filter(
            Company.name.in_(aliases),
            OilPrice.date_reported >= date_from,
            OilPrice.date_reported <= date_to
        ).all()
        return {r.date_reported.isoformat(): float(r.price_per_gallon) for r in res}
        
    wti_series = get_series_robust(["EIA Index: WTI Crude Spot", "Market Index: WTI Crude"])
    ulsd_series = get_series_robust(["EIA Index: NY Harbor ULSD Spot", "Market Index: NY Harbor ULSD"])
    gas_series = get_series_robust(["EIA Index: NY Harbor Gasoline Spot", "Market Index: RBOB Gasoline"])
    
    dates = sorted(list(set(list(wti_series.keys()) + list(ulsd_series.keys()) + list(gas_series.keys()))))
    full_spread_series = {}
    
    for d in dates:
        wti = wti_series.get(d)
        ulsd = ulsd_series.get(d)
        gas = gas_series.get(d)
        
        if wti is not None and ulsd is not None and gas is not None:
            # Spread/bbl = 28*Gas + 14*Diesel - Crude
            spread = 28 * gas + 14 * ulsd - wti
            full_spread_series[d] = spread
            
    # Aggregate
    agg_spread = aggregate_series(full_spread_series, aggregation)
    
    return [
        {"date": d, "spread": round(val, 2)}
        for d, val in sorted(agg_spread.items())
    ]


@router.get("/yoy-comparison")
async def get_yoy_comparison(
    location_id: Optional[int] = Query(None),
    year: int = Query(None),
    db: Session = Depends(get_db)
):
    """
    Comparison of indices for a given year vs previous year.
    Includes usage analysis, gap filling from orders, and temperature trends.
    """
    from app.models import TankReading
    current_year = year or date.today().year
    prev_year = current_year - 1
    
    def get_year_data(target_year):
        start = date(target_year, 1, 1)
        end = date(target_year, 12, 31)
        
        # 1. Orders data
        orders = db.query(OilOrder).filter(
            OilOrder.start_date >= start,
            OilOrder.start_date <= end
        )
        if location_id:
            orders = orders.filter(OilOrder.location_id == location_id)
        orders = orders.all()
        sorted_orders = sorted(orders, key=lambda x: x.start_date)
        
        # Helper to find price for a given date
        def get_price_for_date(d):
            # 1. Check if d falls within an order's range [start, end]
            for o in sorted_orders:
                if o.end_date and o.start_date <= d <= o.end_date:
                    return float(o.price_per_gallon)
            # 2. Fallback: most recent order before d
            best_o = None
            for o in sorted_orders:
                if o.start_date <= d:
                    best_o = o
                else: break
            
            # 3. If still nothing, try the first order of the year
            if not best_o and sorted_orders:
                best_o = sorted_orders[0]
            return float(best_o.price_per_gallon) if best_o else 0

        # 2. Temperature data (HDD)
        temps = db.query(Temperature).filter(
            Temperature.date >= start,
            Temperature.date <= end
        )
        if location_id:
            temps = temps.filter(Temperature.location_id == location_id)
        temps = temps.all()
        
        # 3. Tank Reading data
        readings = db.query(TankReading).filter(
            TankReading.timestamp >= datetime(target_year, 1, 1),
            TankReading.timestamp <= datetime(target_year, 12, 31, 23, 59, 59),
            TankReading.is_anomaly == False,
            TankReading.is_post_fill_unstable == False,
            TankReading.is_fill_event == False
        )
        if location_id:
            readings = readings.filter(TankReading.location_id == location_id)
        readings = readings.order_by(TankReading.timestamp).all()

        daily_usage_readings = {}
        for r in readings:
            day = r.timestamp.date()
            if day not in daily_usage_readings:
                daily_usage_readings[day] = {'first': float(r.gallons), 'last': float(r.gallons)}
            else:
                daily_usage_readings[day]['last'] = float(r.gallons)

        # Aggregate by month maps
        monthly = {m: {
            "order_cost": 0, 
            "order_gallons": 0, 
            "order_count": 0, 
            "hdd": 0, 
            "avg_temp": [],
            "usage_gallons": 0,
            "usage_cost": 0,
            "days_with_usage": 0
        } for m in range(1, 13)}
        
        # Process Orders
        for o in orders:
            m = o.start_date.month
            monthly[m]["order_cost"] += float(o.total_cost)
            monthly[m]["order_gallons"] += float(o.gallons)
            monthly[m]["order_count"] += 1
            
        # Process Temperatures
        for t in temps:
            m = t.date.month
            if t.avg_temp is not None:
                hdd = max(0, 65.0 - float(t.avg_temp))
                monthly[m]["hdd"] += hdd
                monthly[m]["avg_temp"].append(float(t.avg_temp))

        # Process Daily Usage (Tank readings + Gap filling)
        curr_d = start
        today = date.today()
        while curr_d <= end and curr_d <= today:
            m = curr_d.month
            day_usage = 0
            has_data = False
            
            if curr_d in daily_usage_readings:
                data = daily_usage_readings[curr_d]
                day_usage = max(0, data['first'] - data['last'])
                has_data = True
            
            # Gap fill from orders if no tank data
            if not has_data:
                for o in sorted_orders:
                    if o.end_date and o.start_date <= curr_d <= o.end_date:
                        day_usage = float(o.gallons_per_day) if o.gallons_per_day else 0
                        has_data = True
                        break
            
            if has_data:
                price = get_price_for_date(curr_d)
                monthly[m]["usage_gallons"] += day_usage
                monthly[m]["usage_cost"] += (day_usage * price)
                monthly[m]["days_with_usage"] += 1
            
            curr_d += timedelta(days=1)
        
        # Final monthly cleanup
        results = []
        for m in range(1, 13):
            data = monthly[m]
            avg_temp = mean(data["avg_temp"]) if data["avg_temp"] else None
            
            results.append({
                "month": m,
                "order_cost": round(data["order_cost"], 2),
                "order_gallons": round(data["order_gallons"], 2),
                "usage_gallons": round(data["usage_gallons"], 2),
                "usage_cost": round(data["usage_cost"], 2),
                "usage_per_day": round(data["usage_gallons"] / data["days_with_usage"], 2) if data["days_with_usage"] > 0 else 0,
                "avg_price": round(data["order_cost"] / data["order_gallons"], 4) if data["order_gallons"] > 0 else 0,
                "order_count": data["order_count"],
                "total_hdd": round(data["hdd"], 1),
                "avg_temp": round(avg_temp, 1) if avg_temp is not None else None
            })
        return results

    current_data = get_year_data(current_year)
    prev_data = get_year_data(prev_year)
    
    return {
        "current_year": current_year,
        "previous_year": prev_year,
        "current": current_data,
        "previous": prev_data
    }
