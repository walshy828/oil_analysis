from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db

router = APIRouter()

@router.post("/reset-database")
async def reset_database(
    include_locations: bool = False,
    db: Session = Depends(get_db)
):
    """
    Clear all data from the database.
    By default, keeps 'locations' table as it contains user configuration.
    """
    try:
        # Delete in correct order to respect Foreign Keys
        
        # 1. Company Aliases (depends on companies)
        db.execute(text("DELETE FROM company_aliases"))
        
        # 2. Oil Orders (depends on companies and locations)
        db.execute(text("DELETE FROM oil_orders"))
        
        # 3. Oil Prices (depends on companies)
        db.execute(text("DELETE FROM oil_prices"))
        
        # 4. Companies (parent)
        db.execute(text("DELETE FROM companies"))
        
        if include_locations:
             db.execute(text("DELETE FROM locations"))

        db.commit()
        return {"message": "Database cleared successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
