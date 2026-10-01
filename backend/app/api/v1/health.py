"""Health check endpoint."""

from datetime import datetime, timezone
from fastapi import APIRouter
from app.core.config import settings
from app.core.database import check_db_health
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health Check",
    description="Returns the operational status of the API, database connectivity, and AI module.",
)
async def health_check() -> HealthResponse:
    """Check health of the backend application and its dependencies."""
    db_ok = await check_db_health()
    
    return HealthResponse(
        status="ok",
        environment=settings.ENVIRONMENT,
        version="0.1.0",
        database="connected" if db_ok else "disconnected",
        ai_subsystem="not_configured",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
