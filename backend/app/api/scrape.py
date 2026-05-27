from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import uuid

from app.database import get_db, SessionLocal
from app.models import ScrapeConfig, ScrapeHistory
from app.schemas import ScrapeConfigCreate, ScrapeConfigUpdate, ScrapeConfigResponse, ScrapeHistoryResponse
from app.scrapers import get_scraper

router = APIRouter()


@router.get("/configs", response_model=List[ScrapeConfigResponse])
async def list_scrape_configs(db: Session = Depends(get_db)):
    return db.query(ScrapeConfig).all()


@router.post("/configs", response_model=ScrapeConfigResponse)
async def create_scrape_config(config: ScrapeConfigCreate, db: Session = Depends(get_db)):
    existing = db.query(ScrapeConfig).filter(ScrapeConfig.name == config.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Configuration name already exists")

    db_config = ScrapeConfig(**config.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


@router.get("/configs/{config_id}", response_model=ScrapeConfigResponse)
async def get_scrape_config(config_id: int, db: Session = Depends(get_db)):
    config = db.query(ScrapeConfig).filter(ScrapeConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config


@router.put("/configs/{config_id}", response_model=ScrapeConfigResponse)
async def update_scrape_config(
    config_id: int,
    config_update: ScrapeConfigUpdate,
    db: Session = Depends(get_db)
):
    config = db.query(ScrapeConfig).filter(ScrapeConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    update_data = config_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    db.commit()
    db.refresh(config)
    return config


@router.delete("/configs/{config_id}")
async def delete_scrape_config(config_id: int, db: Session = Depends(get_db)):
    config = db.query(ScrapeConfig).filter(ScrapeConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    db.delete(config)
    db.commit()
    return {"message": "Configuration deleted"}


async def _run_scraper_background(config_id: int) -> None:
    """
    Background task that owns its own DB session.
    Must not reuse the request-scoped session from Depends(get_db).
    """
    db = SessionLocal()
    try:
        config = db.query(ScrapeConfig).filter(ScrapeConfig.id == config_id).first()
        if not config:
            return

        snapshot_id = str(uuid.uuid4())
        scrape_ts = datetime.utcnow()

        history = ScrapeHistory(
            config_id=config_id,
            status="running",
            snapshot_id=snapshot_id
        )
        db.add(history)
        db.commit()
        db.refresh(history)

        try:
            scraper = get_scraper(config.scraper_type, config.url)
            records = await scraper.scrape(db, snapshot_id=snapshot_id, scraped_at=scrape_ts)

            history.status = "success"
            history.records_scraped = len(records)
            history.completed_at = datetime.utcnow()
            history.scraped_data = records
            config.last_run = scrape_ts

        except Exception as e:
            history.status = "failed"
            history.error_message = str(e)
            history.completed_at = datetime.utcnow()

        db.commit()
    finally:
        db.close()


@router.post("/run/{config_id}")
async def run_scrape_now(
    config_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Run a scraper immediately (on-demand)."""
    config = db.query(ScrapeConfig).filter(ScrapeConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    background_tasks.add_task(_run_scraper_background, config_id)
    return {"message": "Scrape started", "config_id": config_id}


@router.get("/history", response_model=List[ScrapeHistoryResponse])
async def get_scrape_history(
    skip: int = 0,
    limit: int = 50,
    config_id: int = None,
    days: int = None,
    db: Session = Depends(get_db)
):
    query = db.query(ScrapeHistory)

    if config_id:
        query = query.filter(ScrapeHistory.config_id == config_id)

    if days:
        from datetime import timedelta
        date_threshold = datetime.utcnow() - timedelta(days=days)
        query = query.filter(ScrapeHistory.started_at >= date_threshold)

    return query.order_by(ScrapeHistory.started_at.desc()).offset(skip).limit(limit).all()


@router.get("/types")
async def get_scraper_types():
    return {
        "types": [
            {"id": "newengland_oil", "name": "New England Oil", "description": "Scrapes oil prices from newenglandoil.com"},
            {"id": "market_commodities", "name": "Market Commodities", "description": "NYMEX ULSD & Brent Crude via Yahoo Finance"},
            {"id": "eia_spot_prices", "name": "EIA Spot Prices", "description": "Daily WTI, Brent, and NY Harbor ULSD Spot Prices from EIA.gov"},
            {"id": "smart_oil_gauge", "name": "Smart Oil Gauge", "description": "Scrapes current oil level and history from Smart Oil Gauge app"},
            {"id": "weather", "name": "Weather Data", "description": "Updates daily temperature history for all locations"},
            {"id": "water", "name": "Water Rates", "description": "Water utility rates (coming soon)", "disabled": True},
            {"id": "electric", "name": "Electric Rates", "description": "Electric utility rates (coming soon)", "disabled": True},
        ]
    }
