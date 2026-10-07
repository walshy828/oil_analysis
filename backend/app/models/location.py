from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    address = Column(String(500), nullable=True)
    city = Column(String(255), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    tank_capacity = Column(Float, nullable=True, default=275.0)  # Default 275 gallon tank
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    oil_orders = relationship("OilOrder", back_populates="location")
    temperatures = relationship("Temperature", back_populates="location")
    tank_readings = relationship("TankReading", back_populates="location")
    daily_usage = relationship("DailyUsage", back_populates="location")

    def __repr__(self):
        return f"<Location(id={self.id}, name='{self.name}')>"
