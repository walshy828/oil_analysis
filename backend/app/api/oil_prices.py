from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from datetime import date, datetime
from typing import List, Optional
from decimal import Decimal
import csv
import io

from app.database import get_db
from app.models import OilPrice, Company, CompanyAlias
from app.schemas import OilPriceResponse
from app.services.company_service import find_or_create_company

router = APIRouter()


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
    db: Session = Depends(get_db)
):
    """List oil prices with filtering options."""
    query = db.query(OilPrice, Company.name.label('company_name')).join(Company)
    
    # Apply filters
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
    
    results = query.order_by(desc(OilPrice.date_reported)).offset(skip).limit(limit).all()
    
    # Transform results to include company name
    prices = []
    for price, company_name in results:
        price_dict = {
            "id": price.id,
            "company_id": price.company_id,
            "price_per_gallon": price.price_per_gallon,
            "town": price.town,
            "date_reported": price.date_reported,
            "scraped_at": (price.scraped_at.isoformat() + "Z") if price.scraped_at else None,
            "company_name": company_name,
        }
        prices.append(price_dict)
    
    return prices


@router.get("/latest")
async def get_latest_prices(
    type: str = Query("local", regex="^(local|market|all)$"),
    sort_by: str = Query("price", regex="^(price|name|date)$"),
    order: str = Query("asc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """Get the most recent price snapshot for every company."""
    from sqlalchemy import text, func
    
    # 1. Identify the latest successful batch
    # We first try to find the latest NOT NULL snapshot_id
    latest_snapshot = db.query(OilPrice.snapshot_id).filter(
        OilPrice.snapshot_id.isnot(None)
    ).order_by(desc(OilPrice.scraped_at)).first()
    
    latest_ts = None
    if latest_snapshot:
        latest_snapshot_id = latest_snapshot[0]
        # Get the timestamp for this snapshot as well to handle fallbacks
        latest_ts = db.query(OilPrice.scraped_at).filter(
            OilPrice.snapshot_id == latest_snapshot_id
        ).limit(1).scalar()
    else:
        # Fallback to absolute latest timestamp if no snapshot IDs exist (old data)
        latest_snapshot_id = None
        latest_ts = db.query(func.max(OilPrice.scraped_at)).scalar()
    
    # 2. Build query
    where_clause = "WHERE c.merged_into_id IS NULL AND (:type = 'all' OR (:type = 'local' AND c.is_market_index = false) OR (:type = 'market' AND c.is_market_index = true))"
    
    params = {"type": type}
    
    if latest_snapshot_id:
        where_clause += " AND p.snapshot_id = :snapshot_id"
        params["snapshot_id"] = latest_snapshot_id
    elif latest_ts:
        # Fallback: find records within 1 minute of latest_ts to handle slightly staggered old scrapes
        where_clause += " AND p.scraped_at >= :ts_start AND p.scraped_at <= :ts_end"
        from datetime import timedelta
        params["ts_start"] = latest_ts - timedelta(minutes=1)
        params["ts_end"] = latest_ts + timedelta(minutes=1)
        
    query_text = f"""
        SELECT DISTINCT ON (p.company_id)
            p.id, 
            p.company_id, 
            c.name as company_name,
            c.website as company_website,
            c.phone as company_phone,
            p.price_per_gallon,
            p.town,
            p.date_reported,
            p.scraped_at,
            p.snapshot_id
        FROM oil_prices p
        JOIN companies c ON p.company_id = c.id
        {where_clause}
        ORDER BY p.company_id, p.scraped_at DESC
    """
    
    result = db.execute(text(query_text), params)
    rows = result.fetchall()
    
    # Build response
    response = []
    for row in rows:
        # Fetch aliases for this company
        aliases = db.query(CompanyAlias).filter(
            CompanyAlias.company_id == row.company_id
        ).all()
        
        response.append({
            "id": row.id,
            "company_id": row.company_id,
            "company_name": row.company_name,
            "company_website": row.company_website,
            "company_phone": row.company_phone,
            "price_per_gallon": float(row.price_per_gallon),
            "town": row.town,
            "date_reported": row.date_reported.isoformat() if row.date_reported else None,
            "scraped_at": (row.scraped_at.isoformat() + "Z") if row.scraped_at else None,
            "snapshot_id": row.snapshot_id,
            "aliases": [{"id": a.id, "alias_name": a.alias_name} for a in aliases]
        })
    
    # Apply Sorting
    reverse = (order == "desc")
    if sort_by == "price":
        response.sort(key=lambda x: x["price_per_gallon"], reverse=reverse)
    elif sort_by == "name":
        response.sort(key=lambda x: x["company_name"].lower(), reverse=reverse)
    elif sort_by == "date":
        response.sort(key=lambda x: x["date_reported"] or "", reverse=reverse)
    elif sort_by == "scraped_at":
        response.sort(key=lambda x: x["scraped_at"] or "", reverse=reverse)
    
    return response


@router.get("/history/{company_id}")
async def get_company_price_history(
    company_id: int,
    days: int = 90,
    db: Session = Depends(get_db)
):
    """Get price history for a specific company."""
    from datetime import timedelta
    start_date = date.today() - timedelta(days=days)
    
    prices = db.query(OilPrice).filter(
        OilPrice.company_id == company_id,
        OilPrice.date_reported >= start_date
    ).order_by(OilPrice.date_reported).all()
    
    return [
        {
            "date": p.date_reported.isoformat(),
            "price": float(p.price_per_gallon),
        }
        for p in prices
    ]


@router.put("/{price_id}", response_model=OilPriceResponse)
async def update_oil_price(
    price_id: int,
    price_data: dict,  # Using dict for simplicity, ideally use a Pydantic schema
    db: Session = Depends(get_db)
):
    """Update a specific oil price record."""
    price = db.query(OilPrice).filter(OilPrice.id == price_id).first()
    if not price:
        raise HTTPException(status_code=404, detail="Price not found")
    
    if "price_per_gallon" in price_data:
        price.price_per_gallon = Decimal(str(price_data["price_per_gallon"]))
    if "town" in price_data:
        price.town = price_data["town"]
    
    db.commit()
    db.refresh(price)
    
    # Return formatted response
    return {
        "id": price.id,
        "company_id": price.company_id,
        "price_per_gallon": price.price_per_gallon,
        "town": price.town,
        "date_reported": price.date_reported,
        "scraped_at": price.scraped_at,
        "company_name": price.company.name
    }


@router.delete("/{price_id}")
async def delete_oil_price(price_id: int, db: Session = Depends(get_db)):
    """Delete a specific oil price record."""
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
    """Bulk delete oil prices by ID list or date threshold."""
    query = db.query(OilPrice)
    
    if ids:
        query = query.filter(OilPrice.id.in_(ids))
    elif date_before:
        query = query.filter(OilPrice.date_reported < date_before)
    else:
        raise HTTPException(status_code=400, detail="Must provide ids or date_before")
    
    # Count before deletion
    count = query.count()
    if count == 0:
        return {"message": "No records found to delete", "count": 0}

    # Execute delete
    query.delete(synchronize_session=False)
    db.commit()
    
    return {"message": f"Deleted {count} records", "count": count}


@router.post("/import")
async def import_prices_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Import oil price history from a CSV file."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    content = await file.read()
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            decoded = content.decode('latin-1')
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Could not decode CSV file. Please use UTF-8 or Latin-1.")

    reader = csv.DictReader(io.StringIO(decoded))
    
    # Normalize field names
    def normalize_field(field):
        return field.strip().lower().replace(" ", "").replace("_", "")

    field_map = {normalize_field(f): f for f in reader.fieldnames}
    
    required_fields = ["companyname", "price", "pricedate"] # pricedate or date
    # Fallback for pricedate
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
        try:
            company_name_raw = row[field_map["companyname"]]
            price_raw = row[field_map["price"]]
            date_raw = row[field_map["pricedate"]]
            town = row.get(field_map.get("town"), "Default") if "town" in field_map else "Default"

            # Parse date
            def parse_date(date_str):
                if not date_str: return None
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        return datetime.strptime(date_str.strip()[:10], "%Y-%m-%d").date() if "-" in date_str and len(date_str) > 10 else datetime.strptime(date_str.strip(), fmt).date()
                    except ValueError:
                        continue
                # Try simple isoformat
                try: return date.fromisoformat(date_str.strip())
                except: pass
                raise ValueError(f"Invalid date format: {date_str}")

            price_date = parse_date(date_raw)

            # Parse price
            def parse_decimal(val):
                if not val: return Decimal('0')
                clean_val = val.strip().replace("$", "").replace(",", "")
                return Decimal(clean_val)

            price_val = parse_decimal(price_raw)

            # Find/Create company
            company = find_or_create_company(db, company_name_raw)

            # Check for duplicate: same company, town, and date
            existing = db.query(OilPrice).filter(
                OilPrice.company_id == company.id,
                OilPrice.town == town,
                OilPrice.date_reported == price_date
            ).first()

            if existing:
                skipped_duplicates += 1
                continue

            # Create price record
            new_price = OilPrice(
                company_id=company.id,
                price_per_gallon=price_val,
                town=town,
                date_reported=price_date
            )
            db.add(new_price)
            prices_created += 1

        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")

    if prices_created > 0:
        db.commit()
    
    return {
        "message": f"Successfully imported {prices_created} prices",
        "created": prices_created,
        "skipped_duplicates": skipped_duplicates,
        "errors": errors[:50] # Limit error output
    }
