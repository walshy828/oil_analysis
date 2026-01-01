from pydantic import BaseModel, field_serializer
from datetime import datetime
from typing import Optional
from app.models.scrape_config import ScheduleType


class ScrapeConfigBase(BaseModel):
    name: str
    scraper_type: str
    url: str
    enabled: bool = True
    schedule_type: ScheduleType = ScheduleType.DAILY
    schedule_value: Optional[str] = None


class ScrapeConfigCreate(ScrapeConfigBase):
    pass


class ScrapeConfigUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None
    schedule_type: Optional[ScheduleType] = None
    schedule_value: Optional[str] = None


class ScrapeConfigResponse(ScrapeConfigBase):
    id: int
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer('last_run', 'next_run', 'created_at', 'updated_at')
    def serialize_dt(self, dt: datetime, _info):
        if dt is None: return None
        if dt.tzinfo is None:
            return dt.isoformat() + 'Z'
        return dt

    class Config:
        from_attributes = True


class ScrapeHistoryResponse(BaseModel):
    id: int
    config_id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    records_scraped: int
    error_message: Optional[str] = None

    @field_serializer('started_at', 'completed_at')
    def serialize_dt(self, dt: datetime, _info):
        if dt is None: return None
        if dt.tzinfo is None:
            return dt.isoformat() + 'Z'
        return dt

    class Config:
        from_attributes = True
