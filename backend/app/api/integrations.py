"""
Home Assistant integration endpoints.

Three endpoints designed for HA's `rest` sensor platform:

  GET /api/integrations/home-assistant
      Single combined payload: tank status, burn rate, lowest price + all
      vendor prices, and last order.  Map to a single REST sensor and pull
      individual values via value_template / json_attributes.

  GET /api/integrations/home-assistant/daily-usage
      Normalized daily burn-rate time series (from DailyUsage table) with
      per-row rolling 7-day average.  Use for history graphs or statistics.

  GET /api/integrations/home-assistant/orders
      Order history with last_order as a flat attribute block.

All endpoints accept an optional `location_id` query param; if omitted the
first location is used (single-house installations don't need it).
"""

from datetime import date, timedelta
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, text
from sqlalchemy.orm import Session

from app.api.dashboard import get_season_label, get_seasonal_burn_rate
from app.database import get_db
from app.models import Company, DailyUsage, Location, OilOrder, OilPrice, TankReading

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

def _iqr_avg(values: list[float]) -> float:
    """Mean of values after removing IQR upper-fence outliers (if ≥70% survive)."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    q1, q3 = s[n // 4], s[(3 * n) // 4]
    upper = q3 + 1.5 * (q3 - q1)
    filtered = [v for v in s if v <= upper]
    if len(filtered) >= int(n * 0.7):
        s = filtered
    return sum(s) / len(s)


def _smoothed_burn_stats(usage_rows) -> dict:
    """
    Compute burn-rate statistics from DailyUsage rows.

    Returns avg, median, plus rolling 7 / 14 / 30-day averages with IQR
    filtering applied to each window so isolated spikes don't inflate the
    figure that HA uses for days-remaining math.
    """
    if not usage_rows:
        return {"avg": 0.0, "median": 0.0, "7d_avg": 0.0, "14d_avg": 0.0, "30d_avg": 0.0}

    rows = sorted(usage_rows, key=lambda r: r.date)
    values = [float(r.gallons) for r in rows]

    avg = round(_iqr_avg(values), 3)
    median = round(float(np.median(values)), 3)

    def _window_avg(n: int) -> float:
        return round(_iqr_avg([float(r.gallons) for r in rows[-n:]]), 3)

    return {
        "avg": avg,
        "median": median,
        "7d_avg": _window_avg(7),
        "14d_avg": _window_avg(14),
        "30d_avg": _window_avg(30),
    }


def _resolve_location(db: Session, location_id: Optional[int]) -> Optional[Location]:
    q = db.query(Location)
    if location_id:
        q = q.filter(Location.id == location_id)
    return q.first()


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/home-assistant")
async def get_home_assistant_state(
    location_id: Optional[int] = None,
    stale_days: int = Query(
        30, ge=0,
        description="Exclude vendor prices older than N days (0 = no limit)."
    ),
    usage_days: int = Query(
        30, ge=7, le=90,
        description="Rolling window used for the 30-day burn-rate fallback."
    ),
    db: Session = Depends(get_db),
):
    """
    Single combined payload for Home Assistant REST sensors.

    Suggested HA configuration:

        sensor:
          - platform: rest
            resource: http://<host>:8028/api/integrations/home-assistant
            headers:
              X-API-Key: !secret oil_api_key
            name: Oil Monitor
            value_template: "{{ value_json.tank_percent_full }}"
            unit_of_measurement: "%"
            scan_interval: 3600
            json_attributes:
              - tank_gallons
              - tank_capacity
              - tank_space_available
              - tank_urgency
              - tank_days_remaining
              - tank_depletion_date
              - burn_rate_daily
              - burn_rate_source
              - burn_rate_7d
              - burn_rate_30d
              - burn_rate_seasonal
              - season
              - lowest_price
              - lowest_price_vendor
              - price_date
              - price_scraped_at
              - avg_price_30d
              - vendor_prices
              - last_order_date
              - last_order_gallons
              - last_order_total_cost
              - last_order_price_per_gallon
              - last_order_vendor
              - days_since_last_order
    """
    location = _resolve_location(db, location_id)

    # ── Tank Level ────────────────────────────────────────────────────────────
    tank_gallons = None
    tank_capacity = 275.0
    tank_percent_full = None
    tank_space_available = None
    tank_last_reading_at = None

    if location:
        tank_capacity = float(location.tank_capacity or 275.0)
        reading = (
            db.query(TankReading)
            .filter(
                TankReading.location_id == location.id,
                TankReading.is_anomaly == False,
            )
            .order_by(TankReading.timestamp.desc())
            .first()
        )
        if reading:
            tank_gallons = round(float(reading.gallons), 1)
            tank_percent_full = round(tank_gallons / tank_capacity * 100, 1)
            tank_space_available = round(tank_capacity - tank_gallons, 1)
            tank_last_reading_at = reading.timestamp.isoformat()

    # ── Burn Rate (IQR-smoothed, seasonal-aware) ──────────────────────────────
    burn_rate_daily = 0.0
    burn_rate_source = "none"
    burn_rate_7d = 0.0
    burn_rate_30d = 0.0
    burn_rate_seasonal = None
    season = get_season_label(date.today().month)

    if location:
        cutoff = date.today() - timedelta(days=usage_days)
        usage_rows = (
            db.query(DailyUsage)
            .filter(
                DailyUsage.location_id == location.id,
                DailyUsage.date >= cutoff,
            )
            .order_by(DailyUsage.date)
            .all()
        )

        stats = _smoothed_burn_stats(usage_rows)
        burn_rate_7d = stats["7d_avg"]
        burn_rate_30d = stats["30d_avg"]

        seasonal_rate, _ = get_seasonal_burn_rate(db, location.id)
        burn_rate_seasonal = seasonal_rate

        if seasonal_rate is not None:
            burn_rate_daily = seasonal_rate
            burn_rate_source = "seasonal"
        elif burn_rate_30d > 0:
            burn_rate_daily = burn_rate_30d
            burn_rate_source = f"{usage_days}d_rolling"

    # ── Days Remaining / Urgency ──────────────────────────────────────────────
    days_remaining = None
    depletion_date = None
    urgency = "unknown"

    if tank_gallons is not None and burn_rate_daily > 0:
        days_remaining = round(tank_gallons / burn_rate_daily, 0)
        depletion_date = (
            date.today() + timedelta(days=int(days_remaining))
        ).isoformat()
        if days_remaining < 10:
            urgency = "critical"
        elif days_remaining < 21:
            urgency = "low"
        elif days_remaining < 40:
            urgency = "watch"
        else:
            urgency = "ok"

    # ── Oil Prices ────────────────────────────────────────────────────────────
    lowest_price = None
    lowest_price_vendor = None
    price_date = None
    price_scraped_at = None
    avg_price_30d = None
    vendor_prices: dict = {}

    staleness_sql = ""
    params: dict = {}
    if stale_days > 0:
        params["cutoff"] = date.today() - timedelta(days=stale_days)
        staleness_sql = "AND p.date_reported >= :cutoff"

    price_rows = db.execute(
        text(f"""
            SELECT DISTINCT ON (p.company_id)
                c.name          AS company_name,
                p.price_per_gallon,
                p.date_reported,
                p.scraped_at
            FROM oil_prices p
            JOIN companies c ON p.company_id = c.id
            WHERE c.is_market_index = FALSE
              AND c.merged_into_id IS NULL
              {staleness_sql}
            ORDER BY p.company_id, p.date_reported DESC, p.scraped_at DESC NULLS LAST
        """),
        params,
    ).fetchall()

    if price_rows:
        prices = sorted(
            [
                (row.company_name, float(row.price_per_gallon), row.date_reported, row.scraped_at)
                for row in price_rows
            ],
            key=lambda x: x[1],
        )
        lowest_price = prices[0][1]
        lowest_price_vendor = prices[0][0]
        price_date = prices[0][2].isoformat() if prices[0][2] else None
        price_scraped_at = (prices[0][3].isoformat() + "Z") if prices[0][3] else None
        vendor_prices = {name: price for name, price, _, _ in prices}

        avg_result = (
            db.query(func.avg(OilPrice.price_per_gallon))
            .join(Company)
            .filter(
                OilPrice.date_reported >= date.today() - timedelta(days=30),
                Company.is_market_index == False,
            )
            .scalar()
        )
        avg_price_30d = round(float(avg_result), 4) if avg_result else None

    # ── Last Oil Order ────────────────────────────────────────────────────────
    last_order_date = None
    last_order_gallons = None
    last_order_total_cost = None
    last_order_price_per_gallon = None
    last_order_vendor = None
    days_since_last_order = None

    order_q = db.query(OilOrder, Company).outerjoin(
        Company, OilOrder.company_id == Company.id
    )
    if location:
        order_q = order_q.filter(OilOrder.location_id == location.id)
    order_result = order_q.order_by(desc(OilOrder.start_date)).first()

    if order_result:
        order, company = order_result
        last_order_date = order.start_date.isoformat()
        last_order_gallons = float(order.gallons)
        last_order_price_per_gallon = float(order.price_per_gallon)
        last_order_total_cost = round(last_order_gallons * last_order_price_per_gallon, 2)
        last_order_vendor = company.name if company else None
        days_since_last_order = (date.today() - order.start_date).days

    return {
        # Tank
        "tank_gallons": tank_gallons,
        "tank_capacity": tank_capacity,
        "tank_percent_full": tank_percent_full,
        "tank_space_available": tank_space_available,
        "tank_urgency": urgency,
        "tank_days_remaining": days_remaining,
        "tank_depletion_date": depletion_date,
        "tank_last_reading_at": tank_last_reading_at,
        # Burn rate
        "burn_rate_daily": round(burn_rate_daily, 3),
        "burn_rate_source": burn_rate_source,
        "burn_rate_7d": burn_rate_7d,
        "burn_rate_30d": burn_rate_30d,
        "burn_rate_seasonal": burn_rate_seasonal,
        "season": season,
        # Prices
        "lowest_price": lowest_price,
        "lowest_price_vendor": lowest_price_vendor,
        "price_date": price_date,
        "price_scraped_at": price_scraped_at,
        "avg_price_30d": avg_price_30d,
        "vendor_count": len(vendor_prices),
        "vendor_prices": vendor_prices,
        # Last order
        "last_order_date": last_order_date,
        "last_order_gallons": last_order_gallons,
        "last_order_total_cost": last_order_total_cost,
        "last_order_price_per_gallon": last_order_price_per_gallon,
        "last_order_vendor": last_order_vendor,
        "days_since_last_order": days_since_last_order,
    }


@router.get("/home-assistant/daily-usage")
async def get_ha_daily_usage(
    location_id: Optional[int] = None,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Normalized daily burn-rate time series for HA history graphing.

    Draws exclusively from the DailyUsage table (pre-processed by
    UsageNormalizer) so fill events, top-of-tank noise, and seasonal
    anomalies are already handled.  Each row includes a rolling 7-day
    average that HA statistics sensors can consume directly.
    """
    location = _resolve_location(db, location_id)
    if not location:
        return {"days": [], "avg_daily": 0.0, "total": 0.0, "period_days": days}

    cutoff = date.today() - timedelta(days=days)
    usage_rows = (
        db.query(DailyUsage)
        .filter(
            DailyUsage.location_id == location.id,
            DailyUsage.date >= cutoff,
        )
        .order_by(DailyUsage.date)
        .all()
    )

    if not usage_rows:
        return {
            "location_id": location.id,
            "location_name": location.name,
            "days": [],
            "avg_daily": 0.0,
            "total": 0.0,
            "period_days": 0,
        }

    values = [float(r.gallons) for r in usage_rows]
    total = round(sum(values), 2)
    avg_daily = round(_iqr_avg(values), 3)

    daily = []
    for i, row in enumerate(usage_rows):
        window = values[max(0, i - 6) : i + 1]
        rolling_7d = round(sum(window) / len(window), 3)
        daily.append(
            {
                "date": row.date.isoformat(),
                "gallons": round(float(row.gallons), 3),
                "source": row.source,
                "hdd": round(float(row.hdd), 1) if row.hdd else 0.0,
                "adjustment": row.adjustment_reason,
                "rolling_7d_avg": rolling_7d,
            }
        )

    return {
        "location_id": location.id,
        "location_name": location.name,
        "days": daily,
        "avg_daily": avg_daily,
        "total": total,
        "period_days": len(daily),
    }


@router.get("/home-assistant/orders")
async def get_ha_orders(
    location_id: Optional[int] = None,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Oil order history for Home Assistant sensors.

    `last_order` is a flat attribute dict so HA template sensors can
    reference individual fields (e.g. `{{ state_attr('sensor.oil_orders',
    'last_order')['total_cost'] }}`).  `orders` is the full list.
    """
    query = db.query(OilOrder, Company).outerjoin(
        Company, OilOrder.company_id == Company.id
    )
    if location_id:
        query = query.filter(OilOrder.location_id == location_id)
    results = query.order_by(desc(OilOrder.start_date)).limit(limit).all()

    if not results:
        return {"last_order": None, "orders": [], "total_orders": 0}

    orders = [
        {
            "id": order.id,
            "date": order.start_date.isoformat(),
            "gallons": float(order.gallons),
            "price_per_gallon": float(order.price_per_gallon),
            "total_cost": round(float(order.gallons) * float(order.price_per_gallon), 2),
            "vendor": company.name if company else None,
            "days_ago": (date.today() - order.start_date).days,
        }
        for order, company in results
    ]

    return {
        "last_order": orders[0],
        "orders": orders,
        "total_orders": len(orders),
    }
