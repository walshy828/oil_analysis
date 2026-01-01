from sqlalchemy import Column, Integer, Numeric, Date, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime
from app.database import Base


class OilOrder(Base):
    __tablename__ = "oil_orders"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=True, index=True)
    gallons = Column(Numeric(10, 2), nullable=False)
    price_per_gallon = Column(Numeric(10, 4), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constraints
    __table_args__ = (
        CheckConstraint('end_date IS NULL OR end_date >= start_date', name='check_dates'),
        CheckConstraint('gallons > 0', name='check_gallons_positive'),
        CheckConstraint('price_per_gallon > 0', name='check_price_positive'),
    )

    # Relationships
    location = relationship("Location", back_populates="oil_orders")
    company = relationship("Company", back_populates="oil_orders")

    @hybrid_property
    def total_cost(self):
        """Calculate total cost of the order."""
        return float(self.gallons) * float(self.price_per_gallon)

    @hybrid_property
    def days_duration(self):
        """Calculate number of days between start and end date."""
        if self.end_date and self.start_date:
            return (self.end_date - self.start_date).days + 1
        return None

    @hybrid_property
    def cost_per_day(self):
        """Calculate cost per day if both dates are set."""
        if self.days_duration and self.days_duration > 0:
            return self.total_cost / self.days_duration
        return None

    @hybrid_property
    def gallons_per_day(self):
        """Calculate gallons used per day if both dates are set."""
        if self.days_duration and self.days_duration > 0:
            return float(self.gallons) / self.days_duration
        return None

    def __repr__(self):
        return f"<OilOrder(id={self.id}, location_id={self.location_id}, gallons={self.gallons})>"
