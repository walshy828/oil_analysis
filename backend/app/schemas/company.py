from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CompanyBase(BaseModel):
    name: str
    website: Optional[str] = None
    phone: Optional[str] = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None


from typing import List, Optional

class CompanyAliasResponse(BaseModel):
    id: int
    alias_name: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class CompanyResponse(CompanyBase):
    id: int
    is_market_index: bool
    created_at: datetime
    updated_at: datetime
    merged_into_id: Optional[int] = None
    aliases: List[CompanyAliasResponse] = []

    class Config:
        from_attributes = True
