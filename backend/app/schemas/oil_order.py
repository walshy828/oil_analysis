from pydantic import BaseModel, field_validator
from datetime import date, datetime
from typing import Optional
from decimal import Decimal


class OilOrderBase(BaseModel):
    location_id: int
    company_id: Optional[int] = None
    start_date: date
    end_date: Optional[date] = None
    gallons: Decimal
    price_per_gallon: Decimal

    @field_validator('end_date')
    @classmethod
    def end_date_after_start(cls, v, info):
        if v is not None and 'start_date' in info.data:
            if v < info.data['start_date']:
                raise ValueError('end_date must be after or equal to start_date')
        return v

    @field_validator('gallons', 'price_per_gallon')
    @classmethod
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Value must be positive')
        return v


class OilOrderCreate(OilOrderBase):
    pass


class OilOrderUpdate(BaseModel):
    location_id: Optional[int] = None
    company_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    gallons: Optional[Decimal] = None
    price_per_gallon: Optional[Decimal] = None


class OilOrderResponse(OilOrderBase):
    id: int
    total_cost: Optional[float] = None
    days_duration: Optional[int] = None
    cost_per_day: Optional[float] = None
    gallons_per_day: Optional[float] = None
    location_name: Optional[str] = None
    company_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OilOrderValidation(BaseModel):
    location_id: int
    start_date: date
    end_date: Optional[date] = None
    exclude_order_id: Optional[int] = None  # For edit validation
