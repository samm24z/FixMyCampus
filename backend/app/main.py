"""FixMyCampus AI - Main FastAPI Application Entrypoint."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api import api_router
from app.api.v1.health import router as health_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import register_exception_handlers
from app.services import ticket_service

logger = logging.getLogger("app.auto_close")


async def _auto_close_loop(interval_minutes: int) -> None:
    while True:
        try:
            async with AsyncSessionLocal() as db:
                closed = await ticket_service.auto_close_resolved_tickets(db)
            if closed:
                logger.info("Auto-closed %d resolved ticket(s)", closed)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Auto-close pass failed")
        await asyncio.sleep(interval_minutes * 60)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle handler."""
    task = None
    if settings.AUTO_CLOSE_INTERVAL_MINUTES > 0:
        task = asyncio.create_task(_auto_close_loop(settings.AUTO_CLOSE_INTERVAL_MINUTES))
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "FixMyCampus AI: An Intelligent Campus Grievance Classification, "
        "Deduplication and Resolution Platform API"
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Configure CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include root health check
app.include_router(health_router, tags=["Health"])

# Include versioned API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)
register_exception_handlers(app)


@app.get("/", tags=["Root"])
async def root():
    """Root entrypoint returning API metadata."""
    return {
        "name": settings.PROJECT_NAME,
        "version": "0.1.0",
        "status": "running",
        "docs_url": "/docs",
        "api_v1": settings.API_V1_STR,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.BACKEND_HOST, port=settings.BACKEND_PORT, reload=True)
