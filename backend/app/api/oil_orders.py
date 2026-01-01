from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from typing import List, Optional
from datetime import date, datetime, timedelta
import csv
import io
from decimal import Decimal

from app.database import get_db
from app.models import OilOrder, Location, Company
from app.schemas import OilOrderCreate, OilOrderUpdate, OilOrderResponse, OilOrderValidation
from app.services.company_service import find_or_create_company

router = APIRouter()


def check_date_overlap(
    db: Session,
    location_id: int,
    start_date: date,
    end_date: date = None,
    exclude_order_id: int = None
) -> bool:
    """Check if there's a date overlap with existing orders for the same location."""
    query = db.query(OilOrder).filter(OilOrder.location_id == location_id)
    
    if exclude_order_id:
        query = query.filter(OilOrder.id != exclude_order_id)
    
    # If no end date, just check if start_date falls within any existing range
    if end_date is None:
        end_date = start_date
    
    # Check for overlapping ranges
    # An overlap occurs when: existing.start <= new.end AND existing.end >= new.start
    overlapping = query.filter(
        and_(
            OilOrder.start_date <= end_date,
            or_(
                OilOrder.end_date >= start_date,
                OilOrder.end_date.is_(None)
            )
        )
    ).first()
    
    return overlapping is not None


@router.get("", response_model=List[OilOrderResponse])
async def list_orders(
    skip: int = 0,
    limit: int = 100,
    location_id: int = None,
    db: Session = Depends(get_db)
):
    """List all oil orders with optional location filter."""
    query = db.query(OilOrder, Location, Company).outerjoin(
        Location, OilOrder.location_id == Location.id
    ).outerjoin(
        Company, OilOrder.company_id == Company.id
    )
    
    if location_id:
        query = query.filter(OilOrder.location_id == location_id)
    
    results = query.order_by(desc(OilOrder.start_date)).offset(skip).limit(limit).all()
    
    orders = []
    for order, location, company in results:
        order_dict = {
            "id": order.id,
            "location_id": order.location_id,
            "company_id": order.company_id,
            "start_date": order.start_date,
            "end_date": order.end_date,
            "gallons": order.gallons,
            "price_per_gallon": order.price_per_gallon,
            "total_cost": order.total_cost,
            "days_duration": order.days_duration,
            "cost_per_day": order.cost_per_day,
            "gallons_per_day": order.gallons_per_day,
            "location_name": location.name if location else None,
            "company_name": company.name if company else None,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }
        orders.append(order_dict)
    
    return orders


@router.post("", response_model=OilOrderResponse)
async def create_order(order: OilOrderCreate, db: Session = Depends(get_db)):
    """Create a new oil order."""
    # Check location exists
    location = db.query(Location).filter(Location.id == order.location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    if check_date_overlap(db, order.location_id, order.start_date, order.end_date):
        raise HTTPException(
            status_code=400,
            detail="Date range overlaps with an existing order for this location"
        )
    
    # Auto-close previous open order (if any)
    previous_open_order = db.query(OilOrder).filter(
        OilOrder.location_id == order.location_id,
        OilOrder.end_date.is_(None),
        OilOrder.start_date < order.start_date
    ).order_by(desc(OilOrder.start_date)).first()

    if previous_open_order:
        # Close it one day before the new order starts
        previous_open_order.end_date = order.start_date - timedelta(days=1)
    
    db_order = OilOrder(**order.model_dump())
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    # Return with computed fields
    return {
        "id": db_order.id,
        "location_id": db_order.location_id,
        "company_id": db_order.company_id,
        "start_date": db_order.start_date,
        "end_date": db_order.end_date,
        "gallons": db_order.gallons,
        "price_per_gallon": db_order.price_per_gallon,
        "total_cost": db_order.total_cost,
        "days_duration": db_order.days_duration,
        "cost_per_day": db_order.cost_per_day,
        "gallons_per_day": db_order.gallons_per_day,
        "location_name": location.name,
        "company_name": None,
        "created_at": db_order.created_at,
        "updated_at": db_order.updated_at,
    }


@router.get("/validate-dates")
async def validate_order_dates(
    location_id: int,
    start_date: date,
    end_date: date = None,
    exclude_order_id: int = None,
    db: Session = Depends(get_db)
):
    """Validate that dates don't overlap with existing orders."""
    has_overlap = check_date_overlap(db, location_id, start_date, end_date, exclude_order_id)
    
    # Get the suggested next start date (day after last order's end date)
    last_order = db.query(OilOrder).filter(
        OilOrder.location_id == location_id
    ).order_by(desc(OilOrder.end_date)).first()
    
    suggested_start = None
    if last_order and last_order.end_date:
        from datetime import timedelta
        suggested_start = (last_order.end_date + timedelta(days=1)).isoformat()
    
    return {
        "valid": not has_overlap,
        "has_overlap": has_overlap,
        "suggested_start_date": suggested_start,
    }


@router.get("/{order_id}", response_model=OilOrderResponse)
async def get_order(order_id: int, db: Session = Depends(get_db)):
    """Get a specific oil order."""
    result = db.query(OilOrder, Location, Company).outerjoin(
        Location, OilOrder.location_id == Location.id
    ).outerjoin(
        Company, OilOrder.company_id == Company.id
    ).filter(OilOrder.id == order_id).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order, location, company = result
    return {
        "id": order.id,
        "location_id": order.location_id,
        "company_id": order.company_id,
        "start_date": order.start_date,
        "end_date": order.end_date,
        "gallons": order.gallons,
        "price_per_gallon": order.price_per_gallon,
        "total_cost": order.total_cost,
        "days_duration": order.days_duration,
        "cost_per_day": order.cost_per_day,
        "gallons_per_day": order.gallons_per_day,
        "location_name": location.name if location else None,
        "company_name": company.name if company else None,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


@router.put("/{order_id}", response_model=OilOrderResponse)
async def update_order(
    order_id: int,
    order_update: OilOrderUpdate,
    db: Session = Depends(get_db)
):
    """Update an oil order."""
    order = db.query(OilOrder).filter(OilOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    update_data = order_update.model_dump(exclude_unset=True)
    
    # Check for date overlap if dates are being updated
    start_date = update_data.get('start_date', order.start_date)
    end_date = update_data.get('end_date', order.end_date)
    location_id = update_data.get('location_id', order.location_id)
    
    if check_date_overlap(db, location_id, start_date, end_date, order_id):
        raise HTTPException(
            status_code=400,
            detail="Date range overlaps with an existing order for this location"
        )
    
    for field, value in update_data.items():
        setattr(order, field, value)
    
    db.commit()
    db.refresh(order)
    
    # Get location and company names
    location = db.query(Location).filter(Location.id == order.location_id).first()
    company = db.query(Company).filter(Company.id == order.company_id).first() if order.company_id else None
    
    return {
        "id": order.id,
        "location_id": order.location_id,
        "company_id": order.company_id,
        "start_date": order.start_date,
        "end_date": order.end_date,
        "gallons": order.gallons,
        "price_per_gallon": order.price_per_gallon,
        "total_cost": order.total_cost,
        "days_duration": order.days_duration,
        "cost_per_day": order.cost_per_day,
        "gallons_per_day": order.gallons_per_day,
        "location_name": location.name if location else None,
        "company_name": company.name if company else None,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


@router.delete("/{order_id}")
async def delete_order(order_id: int, db: Session = Depends(get_db)):
    """Delete an oil order."""
    order = db.query(OilOrder).filter(OilOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    db.delete(order)
    db.commit()
    return {"message": "Order deleted"}


@router.post("/import")
async def import_orders_csv(
    location_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Import oil orders from a CSV file."""
    # Check location exists
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

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
    
    # Normalize field names (remove spaces, lowercase)
    def normalize_field(field):
        return field.strip().lower().replace(" ", "").replace("_", "")

    field_map = {normalize_field(f): f for f in reader.fieldnames}
    
    required_fields = ["startdate", "companyname", "price", "gallons"]
    missing = [f for f in required_fields if f not in field_map]
    
    if missing:
        raise HTTPException(
            status_code=400, 
            detail=f"Missing required columns: {', '.join(missing)}. Found: {', '.join(reader.fieldnames)}"
        )

    orders_created = 0
    errors = []

    for row_num, row in enumerate(reader, start=2):
        try:
            # Map normalized fields back to original row keys
            start_date_raw = row[field_map["startdate"]]
            company_name_raw = row[field_map["companyname"]]
            price_raw = row[field_map["price"]]
            gallons_raw = row[field_map["gallons"]]
            
            end_date_raw = row.get(field_map.get("enddate")) if "enddate" in field_map else None

            # Parse dates
            def parse_date(date_str):
                if not date_str: return None
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
                    try:
                        return datetime.strptime(date_str.strip(), fmt).date()
                    except ValueError:
                        continue
                raise ValueError(f"Invalid date format: {date_str}")

            start_date = parse_date(start_date_raw)
            end_date = parse_date(end_date_raw) if end_date_raw else None

            # Parse numeric
            def parse_decimal(val):
                if not val: return Decimal('0')
                clean_val = val.strip().replace("$", "").replace(",", "")
                return Decimal(clean_val)

            price = parse_decimal(price_raw)
            gallons = parse_decimal(gallons_raw)

            # Find/Create company
            company = find_or_create_company(db, company_name_raw)

            # Check for overlap
            if check_date_overlap(db, location_id, start_date, end_date):
                errors.append(f"Row {row_num}: Date overlap for {start_date}")
                continue

            # Create order
            new_order = OilOrder(
                location_id=location_id,
                company_id=company.id,
                start_date=start_date,
                end_date=end_date,
                price_per_gallon=price,
                gallons=gallons
            )
            db.add(new_order)
            orders_created += 1

        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")

    if orders_created > 0:
        db.commit()
    
    return {
        "message": f"Successfully imported {orders_created} orders",
        "created": orders_created,
        "errors": errors
    }
