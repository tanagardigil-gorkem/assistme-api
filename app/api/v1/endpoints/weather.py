from fastapi import APIRouter, Query

from app.schemas.weather import WeatherCurrentResponse
from app.services.weather.open_meteo import get_current_weather


router = APIRouter()


@router.get("/current", response_model=WeatherCurrentResponse)
async def current_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    timezone: str = Query(..., min_length=1, max_length=64),
):
    return await get_current_weather(lat=lat, lon=lon, timezone=timezone)
