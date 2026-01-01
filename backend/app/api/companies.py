from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.database import get_db
from app.models import Company
from app.schemas import CompanyCreate, CompanyUpdate, CompanyResponse

router = APIRouter()


@router.get("", response_model=List[CompanyResponse])
async def list_companies(
    skip: int = 0,
    limit: int = 100,
    search: str = None,
    merged: bool = None,  # If True, show only merged. If False, show only active. If None, show all.
    db: Session = Depends(get_db)
):
    """List all companies with optional search and merge status filter."""
    query = db.query(Company).options(joinedload(Company.aliases))
    
    if search:
        query = query.filter(Company.name.ilike(f"%{search}%"))
        
    if merged is True:
        query = query.filter(Company.merged_into_id.isnot(None))
    elif merged is False:
        query = query.filter(Company.merged_into_id.is_(None))
    
    return query.offset(skip).limit(limit).all()


@router.post("", response_model=CompanyResponse)
async def create_company(company: CompanyCreate, db: Session = Depends(get_db)):
    """Create a new company."""
    # Check if company already exists
    existing = db.query(Company).filter(Company.name == company.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Company already exists")
    
    db_company = Company(**company.model_dump())
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: int, db: Session = Depends(get_db)):
    """Get a specific company."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: int,
    company_update: CompanyUpdate,
    db: Session = Depends(get_db)
):
    """Update a company."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    update_data = company_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)
    
    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}")
async def delete_company(company_id: int, db: Session = Depends(get_db)):
    """Delete a company and its associated prices. Orders are unlinked."""
    from app.models import OilPrice, OilOrder, CompanyAlias

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Delete associated prices
    db.query(OilPrice).filter(OilPrice.company_id == company_id).delete()
    
    # Unlink associated orders (set company_id to NULL)
    db.query(OilOrder).filter(OilOrder.company_id == company_id).update({OilOrder.company_id: None})
    
    # Delete aliases
    db.query(CompanyAlias).filter(CompanyAlias.company_id == company_id).delete()

    # Delete company
    db.delete(company)
    db.commit()
    return {"message": "Company deleted"}


@router.post("/{company_id}/merge/{target_company_id}")
async def merge_companies(
    company_id: int,
    target_company_id: int,
    db: Session = Depends(get_db)
):
    """
    Merge company_id INTO target_company_id.
    - Reassigns all oil prices and orders from company_id to target_company_id.
    - Adds the source company's name as an alias for the target company.
    - Marks the source company as merged.
    """
    from app.models import OilPrice, OilOrder, CompanyAlias
    
    if company_id == target_company_id:
        raise HTTPException(status_code=400, detail="Cannot merge a company into itself")
    
    source = db.query(Company).filter(Company.id == company_id).first()
    target = db.query(Company).filter(Company.id == target_company_id).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source company not found")
    if not target:
        raise HTTPException(status_code=404, detail="Target company not found")
    
    # Reassign all oil prices
    db.query(OilPrice).filter(OilPrice.company_id == company_id).update(
        {"company_id": target_company_id}, synchronize_session=False
    )
    
    # Reassign all oil orders
    db.query(OilOrder).filter(OilOrder.company_id == company_id).update(
        {"company_id": target_company_id}, synchronize_session=False
    )
    
    # Create alias for the source company's name pointing to the target
    existing_alias = db.query(CompanyAlias).filter(
        CompanyAlias.alias_name == source.name
    ).first()
    
    if not existing_alias:
        alias = CompanyAlias(alias_name=source.name, company_id=target_company_id)
        db.add(alias)
    
    # Mark the source company as merged
    source.merged_into_id = target_company_id
    
    db.commit()
    
    return {
        "message": f"Merged '{source.name}' into '{target.name}'",
        "prices_moved": db.query(OilPrice).filter(OilPrice.company_id == target_company_id).count(),
        "orders_moved": db.query(OilOrder).filter(OilOrder.company_id == target_company_id).count(),
    }

