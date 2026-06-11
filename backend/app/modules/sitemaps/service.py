from app.core.config import settings
from app.modules.jobs.repository import JobRepository
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis


class SitemapService:

    KEY = "sitemap:xml"

    def __init__(self, db: AsyncSession, redis: aioredis.Redis):
        self._db = db
        self._redis = redis
        self._repo = JobRepository(db)

    def _build_xml(self, jobs) -> str:
        """Build the sitemap XML string from job rows and static pages."""
        base = settings.site_url.rstrip("/")
        static_pages = [
            (f"{base}/", "weekly", "1.0"),
            (f"{base}/jobs", "daily", "0.9"),
            (f"{base}/about", "monthly", "0.5"),
            (f"{base}/how-it-works", "monthly", "0.5"),
            (f"{base}/contact", "monthly", "0.5"),
            (f"{base}/pricing", "monthly", "0.5"),
        ]

        url_blocks = []
        for loc, changefreq, priority in static_pages:
            url_blocks.append(
                f"  <url>\n"
                f"    <loc>{loc}</loc>\n"
                f"    <changefreq>{changefreq}</changefreq>\n"
                f"    <priority>{priority}</priority>\n"
                f"  </url>"
            )

        for job in jobs:
            lastmod = job.updated_at.strftime("%Y-%m-%d")
            url_blocks.append(
                f"  <url>\n"
                f"    <loc>{base}/jobs/{job.id}</loc>\n"
                f"    <lastmod>{lastmod}</lastmod>\n"
                f"    <changefreq>weekly</changefreq>\n"
                f"    <priority>0.8</priority>\n"
                f"  </url>"
            )

        body = "\n".join(url_blocks)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{body}\n"
            "</urlset>"
        )

    async def get_sitemap_xml(self) -> str:
        """Return sitemap XML — served from Redis cache if available."""
        cached = await self._redis.get(self.KEY)
        if cached:
            return cached.decode("utf-8")

        jobs = await self._repo.get_sitemap_jobs()
        xml = self._build_xml(jobs)
        await self._redis.setex(self.KEY, 3600, xml)
        return xml
