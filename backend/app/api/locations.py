from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Location
from app.schemas import LocationCreate, LocationUpdate, LocationResponse

router = APIRouter()


@router.get("", response_model=List[LocationResponse])
async def list_locations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all locations."""
    return db.query(Location).offset(skip).limit(limit).all()


@router.post("", response_model=LocationResponse)
async def create_location(location: LocationCreate, db: Session = Depends(get_db)):
    """Create a new location."""
    # Check if location already exists
    existing = db.query(Location).filter(Location.name == location.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Location already exists")
    
    db_location = Location(**location.model_dump())
    db.add(db_location)
    db.commit()
    db.refresh(db_location)
    return db_location


@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(location_id: int, db: Session = Depends(get_db)):
    """Get a specific location."""
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


@router.put("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: int,
    location_update: LocationUpdate,
    db: Session = Depends(get_db)
):
    """Update a location."""
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    update_data = location_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(location, field, value)
    
    db.commit()
    db.refresh(location)
    return location


@router.delete("/{location_id}")
async def delete_location(location_id: int, db: Session = Depends(get_db)):
    """Delete a location."""
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    db.delete(location)
    db.commit()
    return {"message": "Location deleted"}
