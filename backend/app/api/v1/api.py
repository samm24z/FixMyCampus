"""API v1 Router registry."""

from fastapi import APIRouter
from app.api.v1 import assistant, auth, campus, departments, health, media, notifications, tickets, uploads, users

api_router = APIRouter()

# Register endpoint routers
api_router.include_router(health.router, tags=["Health & Diagnostics"])
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(users.router, tags=["Users"])
api_router.include_router(departments.router, tags=["Departments"])
api_router.include_router(tickets.router, tags=["Tickets"])
api_router.include_router(notifications.router, tags=["Notifications"])
api_router.include_router(assistant.router, tags=["Assistant"])
api_router.include_router(campus.router, tags=["Campus"])
api_router.include_router(uploads.router, tags=["Uploads"])
api_router.include_router(uploads.ticket_router, tags=["Uploads"])
api_router.include_router(media.router, tags=["Uploads"])
