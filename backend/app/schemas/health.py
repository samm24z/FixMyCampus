"""Health check schema."""

from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response payload."""
    status: str = Field("ok", description="Overall application status")
    environment: str = Field(..., description="Active environment name")
    version: str = Field("0.1.0", description="API version")
    database: str = Field("unknown", description="Database connectivity status: 'connected' or 'disconnected'")
    ai_subsystem: str = Field("ready", description="AI subsystem status")
    timestamp: str = Field(..., description="Server ISO timestamp")
