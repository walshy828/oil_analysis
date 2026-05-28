from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func
from datetime import date, datetime
from typing import List, Optional
from decimal import Decimal
import csv
import io

from app.database import get_db
from app.models import OilPrice, Company, CompanyAlias
from app.schemas import OilPriceResponse
from app.schemas.oil_price import OilPriceUpdate
from app.services.company_service import find_or_create_company

router = APIRouter()

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.get("", response_model=List[OilPriceResponse])
async def list_oil_prices(
    skip: int = 0,
    limit: int = 100,
    company_id: Optional[int] = None,
    company_name: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    price_min: Optional[Decimal] = None,
    price_max: Optional[Decimal] = None,
    town: Optional[str] = None,
    type: str = Query("local", regex="^(local|market|all)$"),
    snapshot_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(OilPrice, Company.name.label('company_name')).join(Company)

    if type == 'local':
        query = query.filter(Company.is_market_index == False)
    elif type == 'market':
        query = query.filter(Company.is_market_index == True)

    if company_id:
        query = query.filter(OilPrice.company_id == company_id)
    if company_name:
        query = query.filter(Company.name.ilike(f"%{company_name}%"))
    if date_from:
        query = query.filter(OilPrice.date_reported >= date_from)
    if date_to:
        query = query.filter(OilPrice.date_reported <= date_to)
    if price_min:
        query = query.filter(OilPrice.price_per_gallon >= price_min)
    if price_max:
        query = query.filter(OilPrice.price_per_gallon <= price_max)
    if town:
        query = query.filter(OilPrice.town.ilike(f"%{town}%"))
    if snapshot_id:
        query = query.filter(OilPrice.snapshot_id == snapshot_id)

    results = query.order_by(desc(OilPrice.date_reported)).offset(skip).limit(limit).all()

    return [
        {
            "id": price.id,
            "company_id": price.company_id,
            "price_per_gallon": price.price_per_gallon,
            "town": price.town,
            "date_reported": price.date_reported,
            "scraped_at": (price.scraped_at.isoformat() + "Z") if price.scraped_at else None,
            "company_name": cname,
        }
        for price, cname in results
    ]


@router.get("/latest")
async def get_latest_prices(
    type: str = Query("local", regex="^(local|market|all)$"),
    sort_by: str = Query("price", regex="^(price|name|date)$"),
    order: str = Query("asc", regex="^(asc|desc)$"),
    stale_days: int = Query(0, ge=0, description="Age-out filter on date_reported. 0 = no limit."),
    db: Session = Depends(get_db)
):
    """
    Return the single most-recent price per company.

    Uses DISTINCT ON ordered by date_reported DESC — no snapshot_id restriction.
    This correctly handles both scraper-sourced prices (with snapshot_id) and
    CSV-imported prices (snapshot_id IS NULL), returning whichever record is
    newest for each company regardless of origin.

    stale_days > 0: exclude companies whose most recent price is older than N days.
    stale_days = 0: no age-out (return all companies ever seen).
    """
    from sqlalchemy import text
    from datetime import timedelta

    if type == "local":
        type_sql = "AND c.is_market_index = FALSE"
    elif type == "market":
        type_sql = "AND c.is_market_index = TRUE"
    else:
        type_sql = ""

    params: dict = {}
    staleness_sql = ""
    if stale_days > 0:
        params["cutoff"] = date.today() - timedelta(days=stale_days)
        staleness_sql = "AND p.date_reported >= :cutoff"

    query_text = f"""
        SELECT DISTINCT ON (p.company_id)
            p.id,
            p.company_id,
            c.name       AS company_name,
            c.website    AS company_website,
            c.phone      AS company_phone,
            p.price_per_gallon,
            p.town,
            p.date_reported,
            p.scraped_at,
            p.snapshot_id
        FROM oil_prices p
        JOIN companies c ON p.company_id = c.id
        WHERE c.merged_into_id IS NULL
          {type_sql}
          {staleness_sql}
        ORDER BY p.company_id, p.date_reported DESC, p.scraped_at DESC NULLS LAST
    """
    rows = db.execute(text(query_text), params).fetchall()

    if not rows:
        return []

    company_ids = [row.company_id for row in rows]

    # ── Batch query 1: aliases ──────────────────────────────────────────────
    alias_rows = db.query(CompanyAlias).filter(
        CompanyAlias.company_id.in_(company_ids)
    ).all()
    aliases_by_company: dict[int, list] = {}
    for a in alias_rows:
        aliases_by_company.setdefault(a.company_id, []).append(a)

    # ── Batch query 2: last 11 prices per company (sparkline + prev price) ──
    price_history_sub = db.query(
        OilPrice.company_id,
        OilPrice.price_per_gallon,
        OilPrice.date_reported,
        func.row_number().over(
            partition_by=OilPrice.company_id,
            order_by=desc(OilPrice.date_reported)
        ).label('rn')
    ).filter(OilPrice.company_id.in_(company_ids)).subquery()

    history_rows = db.query(price_history_sub).filter(price_history_sub.c.rn <= 11).all()

    history_by_company: dict[int, list] = {}
    for h in history_rows:
        history_by_company.setdefault(h.company_id, []).append(h)

    # ── Build response ──────────────────────────────────────────────────────
    response = []
    for row in rows:
        cid = row.company_id
        history = history_by_company.get(cid, [])
        # history is ordered newest-first (rn=1 first)
        sparkline = [
            {"price": float(h.price_per_gallon), "date": h.date_reported.isoformat()}
            for h in sorted(history[:10], key=lambda x: x.date_reported)
        ]
        prev_price = float(history[1].price_per_gallon) if len(history) > 1 else None

        response.append({
            "id": row.id,
            "company_id": cid,
            "company_name": row.company_name,
            "company_website": row.company_website,
            "company_phone": row.company_phone,
            "price_per_gallon": float(row.price_per_gallon),
            "previous_price": prev_price,
            "price_change": (float(row.price_per_gallon) - prev_price) if prev_price else 0,
            "sparkline": sparkline,
            "town": row.town,
            "date_reported": row.date_reported.isoformat() if row.date_reported else None,
            "scraped_at": (row.scraped_at.isoformat() + "Z") if row.scraped_at else None,
            "snapshot_id": row.snapshot_id,
            "aliases": [{"id": a.id, "alias_name": a.alias_name} for a in aliases_by_company.get(cid, [])],
        })

    reverse = (order == "desc")
    if sort_by == "price":
        response.sort(key=lambda x: x["price_per_gallon"], reverse=reverse)
    elif sort_by == "name":
        response.sort(key=lambda x: x["company_name"].lower(), reverse=reverse)
    elif sort_by == "date":
        response.sort(key=lambda x: x["date_reported"] or "", reverse=reverse)

    return response


@router.get("/snapshots")
async def list_snapshots(
    type: str = Query("local", regex="^(local|market|all)$"),
    limit: int = Query(30),
    db: Session = Depends(get_db)
):
    """
    Return a list of distinct scrape snapshots (by snapshot_id + scraped_at date),
    newest first. Used to populate the snapshot selector in the Price Explorer.
    Snapshots with NULL snapshot_id are excluded (CSV imports have no batch identity).
    """
    from sqlalchemy import text

    if type == "local":
        type_sql = "AND c.is_market_index = FALSE"
    elif type == "market":
        type_sql = "AND c.is_market_index = TRUE"
    else:
        type_sql = ""

    rows = db.execute(text(f"""
        SELECT
            p.snapshot_id,
            MIN(p.scraped_at)  AS scraped_at,
            MIN(p.date_reported) AS earliest_reported,
            MAX(p.date_reported) AS latest_reported,
            COUNT(DISTINCT p.company_id) AS company_count
        FROM oil_prices p
        JOIN companies c ON p.company_id = c.id
        WHERE p.snapshot_id IS NOT NULL
          AND c.merged_into_id IS NULL
          {type_sql}
        GROUP BY p.snapshot_id
        ORDER BY MIN(p.scraped_at) DESC NULLS LAST
        LIMIT :limit
    """), {"limit": limit}).fetchall()

    return [
        {
            "snapshot_id": r.snapshot_id,
            "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
            "earliest_reported": r.earliest_reported.isoformat() if r.earliest_reported else None,
            "latest_reported": r.latest_reported.isoformat() if r.latest_reported else None,
            "company_count": r.company_count,
        }
        for r in rows
    ]


@router.get("/history/{company_id}")
async def get_company_price_history(
    company_id: int,
    days: int = 90,
    db: Session = Depends(get_db)
):
    from datetime import timedelta
    start_date = date.today() - timedelta(days=days)

    prices = db.query(OilPrice).filter(
        OilPrice.company_id == company_id,
        OilPrice.date_reported >= start_date
    ).order_by(OilPrice.date_reported).all()

    return [{"date": p.date_reported.isoformat(), "price": float(p.price_per_gallon)} for p in prices]


@router.put("/{price_id}", response_model=OilPriceResponse)
async def update_oil_price(
    price_id: int,
    price_data: OilPriceUpdate,
    db: Session = Depends(get_db)
):
    price = db.query(OilPrice).filter(OilPrice.id == price_id).first()
    if not price:
        raise HTTPException(status_code=404, detail="Price not found")

    update = price_data.model_dump(exclude_unset=True)
    for field, value in update.items():
        setattr(price, field, value)

    db.commit()
    db.refresh(price)

    return {
        "id": price.id,
        "company_id": price.company_id,
        "price_per_gallon": price.price_per_gallon,
        "town": price.town,
        "date_reported": price.date_reported,
        "scraped_at": price.scraped_at,
        "company_name": price.company.name,
    }


@router.delete("/{price_id}")
async def delete_oil_price(price_id: int, db: Session = Depends(get_db)):
    price = db.query(OilPrice).filter(OilPrice.id == price_id).first()
    if not price:
        raise HTTPException(status_code=404, detail="Price not found")
    db.delete(price)
    db.commit()
    return {"message": "Price deleted"}


@router.delete("")
async def delete_oil_prices_bulk(
    ids: Optional[List[int]] = Query(None),
    date_before: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(OilPrice)

    if ids:
        query = query.filter(OilPrice.id.in_(ids))
    elif date_before:
        query = query.filter(OilPrice.date_reported < date_before)
    else:
        raise HTTPException(status_code=400, detail="Must provide ids or date_before")

    count = query.count()
    if count == 0:
        return {"message": "No records found to delete", "count": 0}

    query.delete(synchronize_session=False)
    db.commit()
    return {"message": f"Deleted {count} records", "count": count}


@router.post("/import")
async def import_prices_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Import oil price history from a CSV file (max 10 MB)."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    content = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10 MB.")

    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            decoded = content.decode('latin-1')
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Could not decode CSV file. Please use UTF-8 or Latin-1.")

    reader = csv.DictReader(io.StringIO(decoded))

    def normalize_field(field):
        return field.strip().lower().replace(" ", "").replace("_", "")

    field_map = {normalize_field(f): f for f in reader.fieldnames}

    if "date" in field_map and "pricedate" not in field_map:
        field_map["pricedate"] = field_map["date"]

    missing = [f for f in ["companyname", "price", "pricedate"] if f not in field_map]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(missing)}. Found: {', '.join(reader.fieldnames)}"
        )

    prices_created = 0
    skipped_duplicates = 0
    errors = []

    for row_num, row in enumerate(reader, start=2):
        if len(errors) >= 50:
            errors.append("Too many errors — stopping early.")
            break
        try:
            company_name_raw = row[field_map["companyname"]]
            price_raw = row[field_map["price"]]
            date_raw = row[field_map["pricedate"]]
            town = row.get(field_map.get("town"), "Default") if "town" in field_map else "Default"

            def parse_date(date_str):
                if not date_str:
                    return None
                date_str = date_str.strip()
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        return datetime.strptime(date_str[:10], "%Y-%m-%d").date() if (
                            "-" in date_str and len(date_str) > 10
                        ) else datetime.strptime(date_str, fmt).date()
                    except ValueError:
                        continue
                try:
                    return date.fromisoformat(date_str)
                except Exception:
                    pass
                raise ValueError(f"Invalid date format: {date_str}")

            def parse_decimal(val):
                if not val:
                    return Decimal('0')
                return Decimal(val.strip().replace("$", "").replace(",", ""))

            price_date = parse_date(date_raw)
            price_val = parse_decimal(price_raw)
            company = find_or_create_company(db, company_name_raw)

            existing = db.query(OilPrice).filter(
                OilPrice.company_id == company.id,
                OilPrice.town == town,
                OilPrice.date_reported == price_date
            ).first()

            if existing:
                skipped_duplicates += 1
                continue

            db.add(OilPrice(
                company_id=company.id,
                price_per_gallon=price_val,
                town=town,
                date_reported=price_date,
            ))
            prices_created += 1

        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")

    if prices_created > 0:
        db.commit()

    return {
        "message": f"Successfully imported {prices_created} prices",
        "created": prices_created,
        "skipped_duplicates": skipped_duplicates,
        "errors": errors,
    }
