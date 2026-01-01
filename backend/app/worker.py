"""
Worker process for running scheduled scrape tasks.
"""
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import redis

from app.config import settings
from app.database import SessionLocal
from app.models import ScrapeConfig, ScrapeHistory
from app.models.scrape_config import ScheduleType
from app.scrapers import get_scraper


# Redis connection for distributed locking
redis_client = redis.from_url(settings.redis_url)


async def run_scrape_job(config_id: int):
    """Execute a scrape job."""
    db = SessionLocal()
    
    try:
        config = db.query(ScrapeConfig).filter(ScrapeConfig.id == config_id).first()
        if not config or not config.enabled:
            return
        
        # Create history record
        history = ScrapeHistory(config_id=config_id, status="running")
        db.add(history)
        db.commit()
        db.refresh(history)
        
        print(f"[{datetime.now()}] Starting scrape: {config.name}")
        
        try:
            # Get the appropriate scraper
            scraper = get_scraper(config.scraper_type, config.url)
            
            # Run the scraper
            records = await scraper.scrape(db)
            
            # Update history
            history.status = "success"
            history.records_scraped = len(records)
            history.completed_at = datetime.utcnow()
            
            # Update config last run
            config.last_run = datetime.utcnow()
            
            print(f"[{datetime.now()}] Scrape completed: {config.name} - {len(records)} records")
            
        except Exception as e:
            history.status = "failed"
            history.error_message = str(e)
            history.completed_at = datetime.utcnow()
            print(f"[{datetime.now()}] Scrape failed: {config.name} - {str(e)}")
        
        db.commit()
        
    finally:
        db.close()


def get_trigger(schedule_type: ScheduleType, schedule_value: str):
    """Convert schedule configuration to APScheduler trigger."""
    if schedule_type == ScheduleType.DAILY:
        # schedule_value is time like "09:00"
        hour, minute = schedule_value.split(':') if schedule_value else ("9", "0")
        return CronTrigger(hour=int(hour), minute=int(minute))
    
    elif schedule_type == ScheduleType.HOURLY:
        # schedule_value is minute of the hour
        minute = int(schedule_value) if schedule_value else 0
        return CronTrigger(minute=minute)
    
    elif schedule_type == ScheduleType.INTERVAL:
        # schedule_value is hours between runs
        hours = int(schedule_value) if schedule_value else 4
        return IntervalTrigger(hours=hours)
    
    elif schedule_type == ScheduleType.CRON:
        # schedule_value is a cron expression
        # Parse cron expression: "minute hour day month day_of_week"
        parts = schedule_value.split() if schedule_value else ["0", "9", "*", "*", "*"]
        return CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2] if len(parts) > 2 else "*",
            month=parts[3] if len(parts) > 3 else "*",
            day_of_week=parts[4] if len(parts) > 4 else "*"
        )
    
    # Default to daily at 9am
    return CronTrigger(hour=9, minute=0)


def setup_scheduler():
    """Set up the APScheduler with all configured scrape jobs."""
    scheduler = AsyncIOScheduler()
    
    db = SessionLocal()
    try:
        configs = db.query(ScrapeConfig).filter(ScrapeConfig.enabled == True).all()
        
        for config in configs:
            trigger = get_trigger(config.schedule_type, config.schedule_value)
            
            scheduler.add_job(
                run_scrape_job,
                trigger=trigger,
                args=[config.id],
                id=f"scrape_{config.id}",
                name=f"Scrape: {config.name}",
                replace_existing=True
            )
            
            print(f"Scheduled job: {config.name} ({config.schedule_type.value})")
    
    finally:
        db.close()
    
    return scheduler


async def refresh_scheduler(scheduler: AsyncIOScheduler):
    """Refresh scheduler jobs from database (for dynamic updates)."""
    db = SessionLocal()
    try:
        configs = db.query(ScrapeConfig).all()
        
        # Remove jobs that are disabled or deleted
        existing_job_ids = {job.id for job in scheduler.get_jobs()}
        config_job_ids = {f"scrape_{c.id}" for c in configs if c.enabled}
        
        for job_id in existing_job_ids - config_job_ids:
            scheduler.remove_job(job_id)
        
        # Add/update jobs
        for config in configs:
            job_id = f"scrape_{config.id}"
            
            if not config.enabled:
                if job_id in existing_job_ids:
                    scheduler.remove_job(job_id)
                continue
            
            trigger = get_trigger(config.schedule_type, config.schedule_value)
            
            scheduler.add_job(
                run_scrape_job,
                trigger=trigger,
                args=[config.id],
                id=job_id,
                name=f"Scrape: {config.name}",
                replace_existing=True
            )
    
    finally:
        db.close()


async def main():
    """Main worker entry point."""
    print("Starting Oil Prices Worker...")
    
    scheduler = setup_scheduler()
    scheduler.start()
    
    print("Worker started. Press Ctrl+C to exit.")
    
    # Keep the worker running
    try:
        while True:
            # Periodically refresh scheduler (every 5 minutes)
            await asyncio.sleep(300)
            await refresh_scheduler(scheduler)
    except KeyboardInterrupt:
        print("Shutting down worker...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
