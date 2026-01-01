from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Boolean, String, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class TankReading(Base):
    """Model for oil tank level readings from Smart Oil Gauge or similar devices."""
    __tablename__ = "tank_readings"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    gallons = Column(Float, nullable=False)
    
    # Data quality flags
    is_anomaly = Column(Boolean, default=False)  # Unexpected increase (noise)
    is_fill_event = Column(Boolean, default=False)  # Large increase indicating tank fill
    is_post_fill_unstable = Column(Boolean, default=False)  # Near max capacity, readings unstable
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    location = relationship("Location", back_populates="tank_readings")

    # Composite index for efficient queries
    __table_args__ = (
        Index('ix_tank_readings_location_timestamp', 'location_id', 'timestamp'),
    )

    def __repr__(self):
        return f"<TankReading(id={self.id}, timestamp='{self.timestamp}', gallons={self.gallons})>"
