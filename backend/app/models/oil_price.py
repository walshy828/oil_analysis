from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class OilPrice(Base):
    __tablename__ = "oil_prices"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    price_per_gallon = Column(Numeric(10, 4), nullable=False)
    town = Column(String(255), nullable=True)
    date_reported = Column(Date, nullable=False, index=True)
    scraped_at = Column(DateTime, default=datetime.utcnow, index=True)
    snapshot_id = Column(String(255), nullable=True, index=True)

    # Relationships
    company = relationship("Company", back_populates="oil_prices")

    def __repr__(self):
        return f"<OilPrice(id={self.id}, company_id={self.company_id}, price={self.price_per_gallon})>"
