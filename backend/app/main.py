"""FastAPI application entry point for the Elevare platform.

Configures middleware, exception handlers, and mounts all API routers.
The ``lifespan`` context manager handles startup (logging, DB ping) and
shutdown (engine disposal).
"""

import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
import sentry_sdk
import spacy
from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

import app.core.model_registry  # noqa: F401
from app.core.config import settings
from app.core.database import engine

# Initialise Sentry before anything else
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=settings.app_version,
        traces_sample_rate=0.2,
        profiles_sample_rate=0.1,
    )
from app.core.exception_handler import (
    handle_generic_exception,
    handle_http_exception,
    handle_platform_exception,
    handle_pydantic_validation_error,
)
from app.core.exceptions import PlatformError
from app.core.limiter import limiter
from app.core.logging import setup_logging
from app.core.middleware import RequestLoggingMiddleware, SecurityHeadersMiddleware
from app.modules.admin.router import router as admin_router
from app.modules.ai.cv_parsing_router import router as cv_parsing_router
from app.modules.ai.router import router as ai_router
from app.modules.applications.router import router as app_router
from app.modules.auth.router import router as auth_router
from app.modules.candidates.router import router as candidates_router
from app.modules.contact.router import router as contact_router
from app.modules.credits.router import router as credits_router
from app.modules.employer.router import router as employer_router
from app.modules.ingestion.router import router as ingestion_router
from app.modules.introductions.router import mine_router as intro_mine_router
from app.modules.introductions.router import public_router as intro_public_router
from app.modules.jobs.access_token_router import router as access_token_router
from app.modules.jobs.router import router as jobs_router
from app.modules.sitemaps.router import router as sitemap_router
from app.modules.talent_pool.router import router as talent_pool_router
from app.modules.testimonials.router import router as testimonials_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events.

    Performs initialization (logging, connection pings) on startup and
    cleanup (session disposal) on shutdown.

    Args:
    ----
        app: The current FastAPI instance.

    Yields:
    ------
        None: Control to the application until shutdown.

    """
    setup_logging(debug=settings.debug)

    # Startup
    logger.info(
        "Starting Elevare API",
        extra={"environment": settings.environment, "version": settings.app_version},
    )

    # Verify database connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception:
        logger.error("Database connection failed", exc_info=True)

    # Verify redis connection
    try:
        async with aioredis.from_url(settings.redis_url) as redis_client:
            await redis_client.ping()
            await redis_client.aclose()
            logger.info("Redis connection verified")
    except Exception:
        logger.error("Redis connection failed", exc_info=True)

    # Load spaCy model once at startup
    try:
        app.state.nlp = spacy.load("en_core_web_sm")
        logger.info("spaCy model loaded")
    except Exception:
        logger.error("spaCy model failed to load", exc_info=True)
        app.state.nlp = None

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# ---- Rate limiter state ----
app.state.limiter = limiter

# ---- Global Middleware ----
app.add_middleware(SlowAPIMiddleware)  # must be before other middleware
app.add_middleware(SecurityHeadersMiddleware, debug=settings.debug)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

# ---- Exception Handlers ----

app.add_exception_handler(PlatformError, handle_platform_exception)
app.add_exception_handler(RequestValidationError, handle_pydantic_validation_error)
app.add_exception_handler(HTTPException, handle_http_exception)
app.add_exception_handler(Exception, handle_generic_exception)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.api_route(
    "/health",
    methods=["GET", "HEAD"],
    tags=["system"],
)
async def health_check():
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
    }


# ---- Routers ----
app.include_router(ai_router, prefix="/api/v1/ai", tags=["ai"])
app.include_router(cv_parsing_router, prefix="/api/v1/cv-parsing", tags=["cv-parsing"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(jobs_router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(access_token_router, prefix="/api/v1", tags=["access-tokens"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(employer_router, prefix="/api/v1/employer", tags=["employer"])
app.include_router(candidates_router, prefix="/api/v1/candidates", tags=["candidates"])
app.include_router(app_router, prefix="/api/v1/applications", tags=["applications"])
app.include_router(contact_router, prefix="/api/v1/contact", tags=["contact"])
app.include_router(sitemap_router, prefix="", tags=["Sitemap"])
app.include_router(
    talent_pool_router, prefix="/api/v1/talent-pool", tags=["talent-pool"]
)
app.include_router(ingestion_router, prefix="/api/v1/ingestion", tags=["ingestion"])
app.include_router(
    testimonials_router, prefix="/api/v1/testimonials", tags=["testimonials"]
)
app.include_router(credits_router, prefix="/api/v1/credits", tags=["credits"])
app.include_router(intro_public_router, prefix="/api/v1/public", tags=["introductions"])
app.include_router(
    intro_mine_router, prefix="/api/v1/introductions", tags=["introductions"]
)
