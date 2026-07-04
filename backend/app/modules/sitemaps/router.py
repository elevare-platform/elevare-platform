"""HTTP endpoints for sitemap.xml and robots.txt."""
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db, get_redis_client
from app.modules.sitemaps.service import SitemapService

router = APIRouter()


@router.get("/sitemap.xml")
async def get_sitemap(
    redis: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return the sitemap XML, served from Redis cache when available."""
    service = SitemapService(db, redis)
    xml = await service.get_sitemap_xml()
    return Response(content=xml, media_type="application/xml")


@router.get("/robots.txt")
async def get_robots() -> Response:
    """Return the robots.txt with crawl rules and sitemap location."""
    content = f"""User-agent: *
Allow: /
Allow: /jobs
Allow: /jobs/
Allow: /about
Allow: /how-it-works
Allow: /contact
Allow: /pricing

Disallow: /admin
Disallow: /candidate
Disallow: /employer
Disallow: /api
Disallow: /auth

Sitemap: {settings.site_url.rstrip("/")}/sitemap.xml
"""
    return Response(content=content, media_type="text/plain")
