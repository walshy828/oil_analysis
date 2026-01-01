from pydantic import BaseModel
from datetime import date
from typing import Optional, List
from decimal import Decimal


class TemperatureBase(BaseModel):
    location_id: Optional[int] = None
    date: date
    low_temp: Optional[Decimal] = None
    high_temp: Optional[Decimal] = None


class TemperatureCreate(TemperatureBase):
    pass


class TemperatureResponse(TemperatureBase):
    id: int
    avg_temp: Optional[float] = None

    class Config:
        from_attributes = True


class TemperatureBulkUpload(BaseModel):
    temperatures: List[TemperatureCreate]
