"""API v1 Router registry."""

from fastapi import APIRouter
from app.api.v1 import auth, health, tickets

api_router = APIRouter()

# Register endpoint routers
api_router.include_router(health.router, tags=["Health & Diagnostics"])
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(tickets.router, tags=["Tickets"])
