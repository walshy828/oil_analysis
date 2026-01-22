from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum, JSON
from datetime import datetime
import enum
from app.database import Base


class ScheduleType(str, enum.Enum):
    DAILY = "daily"
    HOURLY = "hourly"
    INTERVAL = "interval"
    CRON = "cron"


class ScrapeConfig(Base):
    __tablename__ = "scrape_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    scraper_type = Column(String(100), nullable=False)  # e.g., "newengland_oil", "water", "electric"
    url = Column(String(1000), nullable=False)
    enabled = Column(Boolean, default=True)
    
    # Schedule configuration
    schedule_type = Column(Enum(ScheduleType), default=ScheduleType.DAILY)
    schedule_value = Column(String(100), nullable=True)  # e.g., "09:00" for daily, "4" for every 4 hours
    
    # Tracking
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ScrapeConfig(id={self.id}, name='{self.name}', type='{self.scraper_type}')>"


class ScrapeHistory(Base):
    __tablename__ = "scrape_history"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), default="running")  # running, success, failed
    records_scraped = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    # Store summary of scraped data for visibility
    scraped_data = Column(JSON, nullable=True)  # List of {company, price, date, ...}
    snapshot_id = Column(String(36), nullable=True, index=True)  # Links to oil_prices.snapshot_id

    def __repr__(self):
        return f"<ScrapeHistory(id={self.id}, config_id={self.config_id}, status='{self.status}')>"
