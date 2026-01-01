# Oil Price Tracker

A comprehensive web application for tracking oil prices, orders, and usage trends with temperature correlation analysis.

## Features

- **Price Scraping**: Automatically scrape oil prices from New England Oil and other sources
- **Order Tracking**: Track oil deliveries with computed metrics (cost per day, gallons per day)
- **Dashboard**: Visual KPIs and charts showing price trends and order history
- **Temperature Correlation**: Visualize how temperature affects oil usage
- **Scheduling**: Configure recurring scrape schedules (daily, hourly, interval)
- **Extensible**: Easy to add new scrapers for water, electric rates, etc.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                            │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│  Frontend   │   Backend   │   Worker    │   Data Layer     │
│   (Nginx)   │  (FastAPI)  │  (Python)   │                  │
│             │             │             │  PostgreSQL      │
│  Static     │  REST API   │  Scrapers   │  Redis           │
│  Files      │  Scheduler  │  Tasks      │                  │
└─────────────┴─────────────┴─────────────┴──────────────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Installation

1. Clone the repository:
```bash
cd /Users/dpw/Documents/Development/oil_prices
```

2. Copy the environment file:
```bash
cp .env.example .env
```

3. Start the services:
```bash
docker-compose up --build
```

4. Access the application:
- **Frontend**: http://localhost:8080
- **API Docs**: http://localhost:8028/docs

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_USER` | Database username | `oil_prices` |
| `POSTGRES_PASSWORD` | Database password | `oil_prices_dev` |
| `POSTGRES_DB` | Database name | `oil_prices` |
| `SECRET_KEY` | Application secret key | `dev_secret_key` |

### Scrape Scheduling

The worker container handles scheduled scraping. Configure schedules via the web UI:

- **Daily**: Run at a specific time (e.g., `09:00`)
- **Hourly**: Run at a specific minute of each hour (e.g., `30`)
- **Interval**: Run every X hours (e.g., `4`)

## Usage

### Adding Your First Location

1. Navigate to **Locations** in the sidebar
2. Click **Add Location**
3. Enter your home or property details

### Recording Oil Deliveries

1. Navigate to **Oil Orders**
2. Click **Add Order**
3. Select location, enter delivery details
4. The system automatically prevents overlapping date ranges

### Uploading Historical Data

#### Temperature Data

Upload a CSV file with columns: `date`, `low_temp`, `high_temp`

```csv
date,low_temp,high_temp
2024-01-01,20,35
2024-01-02,18,32
```

Use the API endpoint: `POST /api/temperatures/upload`

#### Historical Orders

Add orders through the web UI or API: `POST /api/orders`

### Setting Up Price Scraping

1. Navigate to **Scrape Config**
2. Click **Add Scraper**
3. Configure the New England Oil scraper:
   - Name: `Zone 11 Oil Prices`
   - Type: `New England Oil`
   - URL: `https://www.newenglandoil.com/massachusetts/zone11.asp?x=0`
   - Schedule: Daily at `09:00`

## API Reference

### Dashboard
- `GET /api/dashboard/summary` - KPIs and summary data
- `GET /api/dashboard/price-trends` - Price trend chart data
- `GET /api/dashboard/order-trends` - Order trend chart data
- `GET /api/dashboard/temperature-correlation` - Temperature vs usage data

### Oil Prices
- `GET /api/oil-prices` - List prices with filtering
- `GET /api/oil-prices/latest` - Latest prices by company

### Orders
- `GET /api/orders` - List orders
- `POST /api/orders` - Create order
- `PUT /api/orders/{id}` - Update order
- `DELETE /api/orders/{id}` - Delete order
- `GET /api/orders/validate-dates` - Validate date ranges

### Locations
- `GET /api/locations` - List locations
- `POST /api/locations` - Create location
- `PUT /api/locations/{id}` - Update location
- `DELETE /api/locations/{id}` - Delete location

### Temperatures
- `GET /api/temperatures` - List temperature records
- `POST /api/temperatures/upload` - Upload CSV

### Scrape
- `GET /api/scrape/configs` - List scrape configs
- `POST /api/scrape/configs` - Create config
- `POST /api/scrape/run/{id}` - Run scraper on-demand
- `GET /api/scrape/history` - Scrape run history

## Development

### Running Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Worker
cd backend
python -m app.worker
```

### Adding New Scrapers

1. Create a new file in `backend/app/scrapers/`
2. Inherit from `BaseScraper`
3. Implement `scrape()` and `get_scraper_type()`
4. Register in `backend/app/scrapers/__init__.py`

Example:
```python
from app.scrapers.base import BaseScraper

class WaterRateScraper(BaseScraper):
    @classmethod
    def get_scraper_type(cls) -> str:
        return "water_rates"
    
    async def scrape(self, db):
        # Your scraping logic here
        pass
```

## Future Enhancements

- [ ] Smart Oil Gauge integration for real-time usage tracking
- [ ] Water and electric rate scrapers
- [ ] Email notifications for price drops
- [ ] Mobile app / PWA

## License

MIT
