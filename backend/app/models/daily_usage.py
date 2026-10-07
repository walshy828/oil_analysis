from sqlalchemy import Column, Integer, Float, Date, ForeignKey, Boolean, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class DailyUsage(Base):
    """
    Normalized daily oil usage derived from tank readings and orders.
    This table provides a clean, reconciled dataset for analytics.
    """
    __tablename__ = "daily_usage"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    gallons = Column(Float, nullable=False)
    
    # Metadata
    is_estimated = Column(Boolean, default=False)
    source = Column(String, default="sensor") # 'sensor_adjusted', 'hdd_estimated', 'sensor_raw'
    temperature_avg = Column(Float, nullable=True)
    hdd = Column(Float, nullable=True) # Heating Degree Days for this date
    
    # Calculation Transparency
    raw_sensor_value = Column(Float, nullable=True)  # Original sensor reading before adjustments
    adjustment_reason = Column(String, nullable=True)  # Why value was adjusted (e.g., 'capped', 'spike_smoothed')
    notes = Column(String, nullable=True)  # Detailed calculation notes for data science review
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    location = relationship("Location", back_populates="daily_usage")
