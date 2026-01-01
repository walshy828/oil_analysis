import logging
from app.database import SessionLocal
from app.models import Location
from app.services.usage_normalization import UsageNormalizer

logger = logging.getLogger(__name__)

def update_daily_usage_job():
    """
    Scheduled job to recalculate daily usage for the recent period
    for all locations.
    """
    logger.info("Starting scheduled daily usage update")
    session = SessionLocal()
    try:
        locations = session.query(Location).all()
        # Initialize normalizer with the session
        normalizer = UsageNormalizer(session)
        
        for loc in locations:
            logger.info(f"Updating usage for location {loc.name} (ID: {loc.id})")
            try:
                # Recalculate last 45 days. 
                # This ensures any recent delayed orders or sensor updates are captured.
                normalizer.recalculate_usage(loc.id, days=45)
                session.commit() # Commit per location or batch? Normalizer commits internally?
                # Normalizer does self.db.commit().
            except Exception as e:
                logger.error(f"Error updating usage for location {loc.id}: {e}")
                session.rollback()
                
    except Exception as e:
        logger.error(f"Scheduler job failed: {e}")
    finally:
        session.close()
    logger.info("Scheduled daily usage update completed")
