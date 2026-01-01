from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    is_market_index = Column(Boolean, default=False, nullable=False)
    website = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # For merging: if set, this company has been merged into another
    merged_into_id = Column(Integer, ForeignKey("companies.id"), nullable=True)

    # Relationships
    oil_prices = relationship("OilPrice", back_populates="company")
    oil_orders = relationship("OilOrder", back_populates="company")
    merged_into = relationship("Company", remote_side=[id], foreign_keys=[merged_into_id])
    aliases = relationship("CompanyAlias", back_populates="company", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Company(id={self.id}, name='{self.name}')>"


class CompanyAlias(Base):
    """Stores alternative names that should map to a specific company during scraping."""
    __tablename__ = "company_aliases"

    id = Column(Integer, primary_key=True, index=True)
    alias_name = Column(String(255), unique=True, nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="aliases")

    def __repr__(self):
        return f"<CompanyAlias(alias='{self.alias_name}', company_id={self.company_id})>"
