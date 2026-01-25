"""Sage - AI Executive Assistant FastAPI Application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis

from sage.config import get_settings
from sage.api import auth, emails, followups, todos, calendar, briefings, chat, dashboard, meetings
from sage.services.database import init_db, close_db
from sage.scheduler.jobs import start_scheduler, stop_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    await init_db()
    await start_scheduler()

    # Initialize Redis connection pool
    app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)

    yield

    # Shutdown
    await stop_scheduler()
    await app.state.redis.close()
    await close_db()


app = FastAPI(
    title=settings.app_name,
    description="AI Executive Assistant for intelligent email management and follow-up tracking",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://sage.yourdomain.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(emails.router, prefix="/api/v1/emails", tags=["Emails"])
app.include_router(followups.router, prefix="/api/v1/followups", tags=["Follow-ups"])
app.include_router(todos.router, prefix="/api/v1/todos", tags=["Todos"])
app.include_router(calendar.router, prefix="/api/v1/calendar", tags=["Calendar"])
app.include_router(briefings.router, prefix="/api/v1/briefings", tags=["Briefings"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(meetings.router, prefix="/api/v1/meetings", tags=["Meetings"])


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/docs",
        "health": "/health",
    }
