from datetime import date, datetime
from typing import Iterable, Tuple, Optional
from sqlalchemy.orm import Session

from app.models import MarketIndicator


def upsert_indicator_rows(
    db: Session,
    series_key: str,
    rows: Iterable[Tuple[date, float]],
    unit: Optional[str] = None,
    source: Optional[str] = None,
    label: Optional[str] = None,
    snapshot_id: Optional[str] = None,
    scraped_at: Optional[datetime] = None,
) -> int:
    """
    Insert or update (series_key, obs_date) rows. Returns the number of rows
    inserted or changed. Does not commit.
    """
    rows = [(d, float(v)) for d, v in rows if d is not None and v is not None]
    if not rows:
        return 0

    dates = [d for d, _ in rows]
    existing = {
        r.obs_date: r
        for r in db.query(MarketIndicator).filter(
            MarketIndicator.series_key == series_key,
            MarketIndicator.obs_date >= min(dates),
            MarketIndicator.obs_date <= max(dates),
        ).all()
    }

    ts = scraped_at or datetime.utcnow()
    changed = 0
    for d, v in rows:
        row = existing.get(d)
        if row is None:
            db.add(MarketIndicator(
                series_key=series_key, obs_date=d, value=v, unit=unit,
                source=source, label=label, scraped_at=ts, snapshot_id=snapshot_id,
            ))
            changed += 1
        elif abs(row.value - v) > 1e-9:
            row.value = v
            row.scraped_at = ts
            row.snapshot_id = snapshot_id
            if label:
                row.label = label
            changed += 1
    return changed
