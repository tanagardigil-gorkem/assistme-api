from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.dashboard import router as dashboard_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.integrations import router as integrations_router
from app.api.v1.endpoints.news import router as news_router
from app.api.v1.endpoints.tasks import router as tasks_router
from app.api.v1.endpoints.weather import router as weather_router


api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(weather_router, prefix="/weather", tags=["weather"])
api_v1_router.include_router(news_router, prefix="/news", tags=["news"])
api_v1_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_v1_router.include_router(integrations_router, prefix="/integrations", tags=["integrations"])
api_v1_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
