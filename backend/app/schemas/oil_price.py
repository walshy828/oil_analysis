from pydantic import BaseModel, field_serializer
from datetime import date, datetime
from typing import Optional
from decimal import Decimal


class OilPriceBase(BaseModel):
    company_id: int
    price_per_gallon: Decimal
    town: Optional[str] = None
    date_reported: date


class OilPriceCreate(OilPriceBase):
    pass


class OilPriceResponse(OilPriceBase):
    id: int
    scraped_at: datetime
    company_name: Optional[str] = None

    @field_serializer('scraped_at')
    def serialize_dt(self, dt: datetime, _info):
        if dt is None: return None
        if dt.tzinfo is None:
            return dt.isoformat() + 'Z'
        return dt

    class Config:
        from_attributes = True


class OilPriceFilter(BaseModel):
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    price_min: Optional[Decimal] = None
    price_max: Optional[Decimal] = None
    town: Optional[str] = None
