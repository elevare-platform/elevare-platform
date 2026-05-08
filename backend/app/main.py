import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text

from app.core.config import settings
from app.core.logging import setup_logging

from app.core.database import engine


logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events.

    Performs initialization (logging, connection pings) on startup and
    cleanup (session disposal) on shutdown.

    Args:
        app: The current FastAPI instance.

    Yields:
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

# ---- Global Middleware ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server — tightened in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)    

@app.get("/health", tags=["system"])
async def health_check() -> dict:
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
    }
