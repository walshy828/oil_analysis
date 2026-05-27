from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import date, datetime, timedelta
import json
import re

from app.database import get_db
from app.models import TankReading, Location, OilPrice, Company, DailyUsage, Temperature, OilOrder
from app.config import settings

router = APIRouter()


async def _gather_context(db: Session) -> dict:
    location = db.query(Location).first()

    tank_data = {}
    if location:
        reading = db.query(TankReading).filter(
            TankReading.location_id == location.id,
            TankReading.is_anomaly == False
        ).order_by(TankReading.timestamp.desc()).first()

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        readings_30d = db.query(TankReading).filter(
            TankReading.location_id == location.id,
            TankReading.timestamp >= thirty_days_ago,
            TankReading.is_anomaly == False,
            TankReading.is_fill_event == False,
            TankReading.is_post_fill_unstable == False
        ).order_by(TankReading.timestamp).all()

        day_buckets = {}
        for r in readings_30d:
            day = r.timestamp.date()
            if day not in day_buckets:
                day_buckets[day] = {"first": float(r.gallons), "last": float(r.gallons)}
            else:
                day_buckets[day]["last"] = float(r.gallons)

        total_usage_30d = sum(max(0, v["first"] - v["last"]) for v in day_buckets.values())
        days_with_data = len(day_buckets)
        avg_daily = total_usage_30d / days_with_data if days_with_data > 0 else 0

        current_gallons = float(reading.gallons) if reading else None
        capacity = float(location.tank_capacity or 275)
        days_remaining = (current_gallons / avg_daily) if (current_gallons and avg_daily > 0) else None

        tank_data = {
            "current_gallons": round(current_gallons, 1) if current_gallons else None,
            "capacity_gallons": capacity,
            "percent_full": round((current_gallons / capacity) * 100, 1) if current_gallons else None,
            "avg_daily_usage_gallons": round(avg_daily, 2),
            "days_remaining": round(days_remaining, 0) if days_remaining else None,
            "estimated_depletion_date": (date.today() + timedelta(days=int(days_remaining))).isoformat() if days_remaining else None,
        }

    # Latest local prices
    latest_scrape_time = db.query(func.max(OilPrice.scraped_at)).join(Company).filter(
        Company.is_market_index == False
    ).scalar()

    local_prices = []
    if latest_scrape_time:
        prices = db.query(OilPrice, Company).join(Company).filter(
            OilPrice.scraped_at == latest_scrape_time,
            Company.is_market_index == False
        ).order_by(OilPrice.price_per_gallon).all()
        local_prices = [
            {"company": c.name, "price": float(p.price_per_gallon)}
            for p, c in prices[:8]
        ]

    thirty_days_ago_date = date.today() - timedelta(days=30)
    avg_price_30d = db.query(func.avg(OilPrice.price_per_gallon)).join(Company).filter(
        OilPrice.date_reported >= thirty_days_ago_date,
        Company.is_market_index == False
    ).scalar()

    market_prices = {}
    for name in ["EIA Index: NY Harbor ULSD Spot", "EIA Index: WTI Crude Spot"]:
        p = db.query(OilPrice).join(Company).filter(
            Company.name == name
        ).order_by(OilPrice.date_reported.desc()).first()
        if p:
            market_prices[name] = {"price": float(p.price_per_gallon), "date": p.date_reported.isoformat()}

    seven_days_ago = date.today() - timedelta(days=7)
    ulsd_week_start = db.query(OilPrice).join(Company).filter(
        Company.name == "EIA Index: NY Harbor ULSD Spot",
        OilPrice.date_reported >= seven_days_ago
    ).order_by(OilPrice.date_reported).first()
    ulsd_latest = db.query(OilPrice).join(Company).filter(
        Company.name == "EIA Index: NY Harbor ULSD Spot"
    ).order_by(OilPrice.date_reported.desc()).first()

    ulsd_7d_change = None
    if ulsd_week_start and ulsd_latest:
        ulsd_7d_change = round(float(ulsd_latest.price_per_gallon) - float(ulsd_week_start.price_per_gallon), 4)

    recent_hdd = 0
    if location:
        fourteen_days_ago = date.today() - timedelta(days=14)
        temps = db.query(Temperature).filter(
            Temperature.location_id == location.id,
            Temperature.date >= fourteen_days_ago
        ).all()
        recent_hdd = sum(max(0, 65.0 - float(t.avg_temp)) for t in temps if t.avg_temp is not None)

    last_order_row = db.query(OilOrder, Company).outerjoin(
        Company, OilOrder.company_id == Company.id
    ).order_by(desc(OilOrder.start_date)).first()

    last_order_data = None
    if last_order_row:
        o, c = last_order_row
        last_order_data = {
            "date": o.start_date.isoformat(),
            "gallons": float(o.gallons),
            "price_per_gallon": float(o.price_per_gallon),
            "company": c.name if c else None,
            "days_ago": (date.today() - o.start_date).days,
        }

    return {
        "tank": tank_data,
        "local_prices": local_prices,
        "avg_price_30d": round(float(avg_price_30d), 3) if avg_price_30d else None,
        "market_indices": market_prices,
        "ulsd_7d_change": ulsd_7d_change,
        "recent_hdd_14d": round(recent_hdd, 1),
        "last_order": last_order_data,
        "analysis_date": date.today().isoformat(),
        "location_name": location.name if location else "Unknown",
    }


@router.get("/analysis")
async def get_ai_analysis(db: Session = Depends(get_db)):
    """Generate AI-powered buy recommendation using Claude."""
    if not settings.anthropic_api_key:
        return {
            "available": False,
            "message": "Set ANTHROPIC_API_KEY in your .env to enable AI analysis.",
        }

    try:
        import anthropic

        ctx = await _gather_context(db)
        tank = ctx.get("tank", {})
        local_prices = ctx.get("local_prices", [])
        market = ctx.get("market_indices", {})

        lowest_local = min((p["price"] for p in local_prices), default=None)
        highest_local = max((p["price"] for p in local_prices), default=None)
        cheapest = local_prices[0] if local_prices else None
        ulsd = market.get("EIA Index: NY Harbor ULSD Spot", {})
        wti = market.get("EIA Index: WTI Crude Spot", {})

        lo = ctx.get("last_order")
        lo_str = "No previous orders on record"
        if lo:
            lo_str = (
                f"Date: {lo['date']}, Gallons: {lo['gallons']:.0f}, "
                f"Price: ${lo['price_per_gallon']:.3f}/gal, "
                f"Vendor: {lo['company'] or 'Unknown'}, "
                f"Days ago: {lo['days_ago']}"
            )

        prompt = f"""You are an expert home heating oil analyst helping a homeowner in Central Massachusetts time oil purchases optimally.

CURRENT DATA ({ctx['analysis_date']}):

TANK:
- Level: {tank.get('current_gallons', 'Unknown')} gal ({tank.get('percent_full', '?')}% of {tank.get('capacity_gallons', 275)} gal capacity)
- Daily burn rate: {tank.get('avg_daily_usage_gallons', '?')} gal/day (30-day avg)
- Estimated days remaining: {tank.get('days_remaining', 'Unknown')}
- Projected empty date: {tank.get('estimated_depletion_date', 'Unknown')}

LOCAL MARKET (Central MA):
- Lowest price: ${f'{lowest_local:.3f}' if lowest_local else 'N/A'}/gal ({cheapest['company'] if cheapest else 'N/A'})
- Highest price: ${f'{highest_local:.3f}' if highest_local else 'N/A'}/gal
- 30-day avg: ${f'{ctx["avg_price_30d"]:.3f}' if ctx.get("avg_price_30d") else 'N/A'}/gal
- Vendors tracked: {len(local_prices)}

UPSTREAM SIGNALS:
- NY Harbor ULSD: ${f'{ulsd["price"]:.3f}' if ulsd.get("price") else 'N/A'}/gal (as of {ulsd.get('date', 'N/A')})
- ULSD 7-day change: {f'+{ctx["ulsd_7d_change"]:.4f}' if (ctx.get("ulsd_7d_change") or 0) >= 0 else f'{ctx["ulsd_7d_change"]:.4f}'}/gal
- WTI Crude: ${f'{wti["price"]:.2f}' if wti.get("price") else 'N/A'}/bbl
- Recent HDD (14 days): {ctx.get('recent_hdd_14d', 'N/A')} (heating demand)

LAST ORDER: {lo_str}

Based on this data, return ONLY a JSON object — no other text — with exactly these fields:
{{
  "recommendation": "BUY_NOW" | "BUY_SOON" | "MONITOR" | "WAIT",
  "confidence": "high" | "medium" | "low",
  "days_to_act": <integer, 0 means order today>,
  "suggested_gallons": <integer>,
  "price_outlook": "rising" | "falling" | "stable" | "uncertain",
  "narrative": "<3-4 sentence plain English explanation>",
  "key_factors": ["<factor 1>", "<factor 2>", "<factor 3>"],
  "risk_note": "<1 sentence about main uncertainty>"
}}"""

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        text = message.content[0].text.strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        result = json.loads(match.group() if match else text)

        return {
            "available": True,
            "context_snapshot": {
                "tank_gallons": tank.get("current_gallons"),
                "tank_percent": tank.get("percent_full"),
                "days_remaining": tank.get("days_remaining"),
                "lowest_local_price": lowest_local,
                "cheapest_vendor": cheapest["company"] if cheapest else None,
                "ulsd_7d_change": ctx.get("ulsd_7d_change"),
                "analysis_date": ctx["analysis_date"],
            },
            **result,
        }

    except Exception as e:
        return {
            "available": True,
            "recommendation": "MONITOR",
            "confidence": "low",
            "narrative": f"AI analysis temporarily unavailable: {str(e)[:120]}",
            "key_factors": [],
            "days_to_act": None,
            "suggested_gallons": None,
            "price_outlook": "uncertain",
            "risk_note": "Unable to complete AI analysis at this time.",
        }
