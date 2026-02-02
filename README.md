# assist me api

FastAPI backend for the Assist Me personal assistant app.

## Run locally

1) Create a venv and install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

2) Start the server:

```bash
uvicorn app.main:app --reload
```

## Endpoints

- `GET /api/v1/health`
- `GET /api/v1/weather/current?lat=..&lon=..&timezone=..`
- `GET /api/v1/news/top?limit=10&q=..&sources=a,b`
- `GET /api/v1/dashboard/morning?lat=..&lon=..&timezone=..&limit=10&q=..`

## Configuration (env)

- `ASSISTME_CORS_ORIGINS` JSON array or comma-separated string
- `ASSISTME_RSS_FEEDS` JSON array or comma-separated string
- `ASSISTME_RSS_TTL_SECONDS` (default 1200)
- `ASSISTME_WEATHER_TTL_SECONDS` (default 600)
