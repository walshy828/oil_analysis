from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, Text, UniqueConstraint
from datetime import datetime
from app.database import Base


class MarketIndicator(Base):
    """
    Generic time series store for market-intel inputs (EIA inventories, CFTC
    positioning, futures contracts, HDD forecasts, ...). One row per series per date.
    """
    __tablename__ = "market_indicators"

    id = Column(Integer, primary_key=True, index=True)
    series_key = Column(String(100), nullable=False, index=True)
    obs_date = Column(Date, nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String(32), nullable=True)
    source = Column(String(64), nullable=True)
    label = Column(String(255), nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    snapshot_id = Column(String(255), nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("series_key", "obs_date", name="uq_market_indicator_series_date"),
    )

    def __repr__(self):
        return f"<MarketIndicator({self.series_key} {self.obs_date}={self.value})>"


class MarketEvent(Base):
    """
    Hand-maintained geopolitical/supply event (e.g. 'Russia diesel export ban').
    Feeds the signal model as a bounded bullish/bearish adjustment.
    """
    __tablename__ = "market_events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    category = Column(String(64), nullable=True)      # export_ban, refinery_outage, shipping, diplomacy, weather, other
    direction = Column(Integer, nullable=False, default=1)   # +1 bullish (prices up), -1 bearish, 0 neutral
    magnitude = Column(Integer, nullable=False, default=1)   # 1 (minor) .. 3 (major)
    horizon = Column(String(16), nullable=False, default="all")  # days | weeks | months | all
    start_date = Column(Date, nullable=False, default=datetime.utcnow)
    expires_on = Column(Date, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MarketEvent({self.title} dir={self.direction} mag={self.magnitude})>"
