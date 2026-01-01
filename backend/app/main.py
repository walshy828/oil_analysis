from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging

from app.config import settings
from app.database import engine, Base
from app.api import dashboard, companies, oil_prices, locations, oil_orders, temperatures, scrape, system, analytics, tank_usage, historical_import


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create scheduler
scheduler = AsyncIOScheduler()


from app.tasks.usage_update import update_daily_usage_job

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application...")
    # Base.metadata.create_all(bind=engine) # Production: Use Alembic migrations
    scheduler.start()
    
    # Schedule recurring tasks
    scheduler.add_job(
        update_daily_usage_job, 
        'cron', 
        hour=3, 
        minute=0, 
        id='daily_usage_update', 
        replace_existing=True
    )
    logger.info("Scheduled daily usage update job for 03:00")
    
    yield
    # Shutdown
    logger.info("Shutting down application...")
    scheduler.shutdown()


app = FastAPI(
    title="Oil Price Tracker",
    description="Track oil prices, orders, and usage with temperature correlation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])
app.include_router(oil_prices.router, prefix="/api/oil-prices", tags=["Oil Prices"])
app.include_router(locations.router, prefix="/api/locations", tags=["Locations"])
app.include_router(oil_orders.router, prefix="/api/orders", tags=["Oil Orders"])
app.include_router(temperatures.router, prefix="/api/temperatures", tags=["Temperatures"])
app.include_router(scrape.router, prefix="/api/scrape", tags=["Scrape"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(tank_usage.router, prefix="/api/tank", tags=["Tank Usage"])
app.include_router(historical_import.router, prefix="/api/import", tags=["Historical Import"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {"message": "Oil Price Tracker API", "docs": "/docs"}
