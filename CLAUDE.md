# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Running the full stack
```bash
docker-compose up --build
# Frontend: http://localhost:8088
# API + Swagger docs: http://localhost:8028/docs
```

### Local backend development
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8028
```

### Local worker development
```bash
cd backend
python -m app.worker
```

### Database migrations
```bash
cd backend
alembic upgrade head                                   # Apply migrations
alembic revision --autogenerate -m "description"      # Generate migration from model changes
```

### Environment variables
Copy `.env.example` to `.env`. Key variables:
- `API_KEY` — **required**; all `/api/*` endpoints return 403 without it. Generate: `python -c "import secrets; print(secrets.token_hex(32))"`
- `DATABASE_URL` — defaults to `postgresql://oil_prices:oil_prices_dev@localhost:5432/oil_prices`
- `REDIS_URL` — defaults to `redis://localhost:6379/0`
- `EIA_API_KEY` — required for EIA spot price scraper
- `SMART_OIL_USERNAME` / `SMART_OIL_PASSWORD` — required for Smart Oil Gauge scraper

## Architecture

### Service layout
Four Docker Compose services: **frontend** (Nginx serving static files, port 8088), **backend** (FastAPI, port 8028), **worker** (standalone Python process), **postgres + redis** (data layer).

The backend and worker both mount `./backend:/app` so code changes are reflected without rebuilds in development.

### Backend (`backend/app/`)

**Entry point**: `main.py` — wires up all FastAPI routers, starts APScheduler for the `daily_usage_update` cron job (03:00 daily).

**Routers** (`api/`): `dashboard`, `analytics`, `companies`, `oil_prices`, `locations`, `oil_orders`, `temperatures`, `scrape`, `system`, `tank_usage`, `historical_import`, `market_intel` — all mounted under `/api/<resource>`.

**Models** (`models/`): SQLAlchemy ORM models — `Company`, `CompanyAlias`, `OilPrice`, `Location`, `OilOrder`, `Temperature`, `ScrapeConfig`, `ScrapeHistory`, `TankReading`, `DailyUsage`, `MarketIndicator`, `MarketEvent`. All use the shared `Base` from `database.py`.

**Schemas** (`schemas/`): Pydantic v2 schemas for request/response validation, mirroring the model structure.

**Database**: `database.py` exports `engine`, `SessionLocal`, and `get_db()` (FastAPI dependency). Uses synchronous SQLAlchemy with a connection pool.

### Worker (`backend/app/worker.py`)
Separate process that runs scrapers on schedule. Loads `ScrapeConfig` rows from the DB and registers APScheduler jobs. Refreshes job schedule every 5 minutes to pick up config changes made via the API. Uses Redis for distributed locking.

The main FastAPI app does **not** run scrapers — that is exclusively the worker's responsibility.

### Scraper system (`backend/app/scrapers/`)
Plugin architecture via `SCRAPER_REGISTRY` dict in `__init__.py`. To add a new scraper:
1. Create a file in `scrapers/`, subclass `BaseScraper`
2. Implement `scrape(db, snapshot_id, scraped_at) -> List[Dict]` and `get_scraper_type() -> str`
3. Add to `SCRAPER_REGISTRY` in `__init__.py`

Each scrape run gets a `snapshot_id` (UUID) written to `ScrapeHistory` for data lineage. Currently registered scrapers: `newengland_oil`, `market_commodities`, `eia_spot_prices`, `weather`, `smart_oil_gauge`, plus the Market Intel feeds `eia_market_data`, `cftc_cot`, `futures_curve`, `weather_forecast`.

**Smart Oil Gauge scraper**: Logs in via form POST, calls the AJAX API to get tank list/details, saves current level via `TankService`, then exports a 30-day CSV history. Currently hardcoded to use `db.query(Location).first()`.

### Services (`backend/app/services/`)

**`TankService`**: Handles persisting tank readings with anomaly detection. Three flags per reading: `is_anomaly` (sensor noise — small upward spikes ≤2 gal), `is_fill_event` (jump >30 gal), `is_post_fill_unstable` (high-level fluctuation within 48h after fill). Also handles CSV import from Smart Oil Gauge export format.

**`UsageNormalizer`**: Builds the `DailyUsage` table from raw tank readings and oil orders. Strategy selection: if sensor-derived total drop is within 50–150% of the known delivery volume, use sensor data (shaped to delivery total); otherwise fall back to HDD-weighted estimation using a k-factor (gallons/HDD) derived from recent confirmed data. Applies a seasonal daily cap (2 gal/day in summer, 15 gal/day in winter) and contextual spike smoothing (7-day median window).

**Market Intel signal model** (`services/market_signals.py`, `api/market_intel.py`): feeds write to the generic `market_indicators` table (one row per `series_key` per date; ULSD contracts are stored per delivery month as `ho_fut:YYYYMM`). `SignalContext` loads every series once; each `sig_*` function scores one signal -2..+2 for the days/weeks/months horizons "as of" a date, and `WEIGHTS` combines them into an outlook, confidence and drivers. The same code powers `/api/market-intel/backtest`. `MarketEvent` rows (hand-logged geopolitical events) feed the `events` signal. `POST /api/market-intel/setup` creates the four feed `ScrapeConfig`s; `POST /api/market-intel/curve/import` loads a ULSD curve by hand because the free Yahoo source can return HTTP 429. `python backend/verify_market_feeds.py` checks the feeds against the live sources. `/api/analytics/lead-lag` uses the model's days-horizon outlook once at least 4 signals are available.

### Frontend (`frontend/static/`)
Vanilla HTML/JS/CSS — no build step. Market Intel panels live in `js/market-intel.js`. Nginx serves the files directly. API calls go to `/api/*` which nginx proxies to the backend container.

### Scheduling
Two independent schedulers:
- **Backend** (`main.py`): APScheduler for `update_daily_usage_job` at 03:00 daily
- **Worker** (`worker.py`): APScheduler for all scrape configs loaded from DB; refreshes every 5 min

Schedule types in `ScrapeConfig`: `DAILY` (time string `"HH:MM"`), `HOURLY` (minute offset), `INTERVAL` (hours), `CRON` (5-part cron expression). All times are `America/New_York`.
