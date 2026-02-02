from fastapi import APIRouter, Query

from app.schemas.news import NewsTopResponse
from app.services.news.rss import get_top_news


router = APIRouter()


@router.get("/top", response_model=NewsTopResponse)
async def top_news(
    limit: int = Query(10, ge=1, le=50),
    q: str | None = Query(None, min_length=1, max_length=120),
    sources: str | None = Query(
        None,
        description="Comma-separated source filters (matches feed title/host).",
        max_length=300,
    ),
):
    source_list = None
    if sources:
        source_list = [s.strip() for s in sources.split(",") if s.strip()]
    return await get_top_news(limit=limit, q=q, sources=source_list)
