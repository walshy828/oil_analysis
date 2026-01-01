from sqlalchemy import Column, Integer, Numeric, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from app.database import Base


class Temperature(Base):
    __tablename__ = "temperatures"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    date = Column(Date, nullable=False, index=True)
    low_temp = Column(Numeric(5, 2), nullable=True)
    high_temp = Column(Numeric(5, 2), nullable=True)

    # Unique constraint for location + date
    __table_args__ = (
        UniqueConstraint('location_id', 'date', name='uq_location_date'),
    )

    # Relationships
    location = relationship("Location", back_populates="temperatures")

    @hybrid_property
    def avg_temp(self):
        """Calculate average temperature."""
        if self.low_temp is not None and self.high_temp is not None:
            return (float(self.low_temp) + float(self.high_temp)) / 2
        return None

    def __repr__(self):
        return f"<Temperature(id={self.id}, date={self.date}, low={self.low_temp}, high={self.high_temp})>"
