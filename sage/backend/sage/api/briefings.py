"""Briefings API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from sage.services.database import get_db
from sage.schemas.briefing import MorningBriefing, WeeklyReview
from sage.core.briefing_generator import BriefingGenerator

router = APIRouter()


@router.post("/morning", response_model=MorningBriefing)
async def generate_morning_briefing(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MorningBriefing:
    """Generate the morning briefing."""
    generator = BriefingGenerator(db)
    briefing = await generator.generate_morning_briefing()
    return briefing


@router.post("/weekly", response_model=WeeklyReview)
async def generate_weekly_review(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WeeklyReview:
    """Generate the weekly review briefing."""
    generator = BriefingGenerator(db)
    review = await generator.generate_weekly_review()
    return review


@router.post("/morning/send")
async def send_morning_briefing(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Generate and send the morning briefing as an email draft."""
    generator = BriefingGenerator(db)
    briefing = await generator.generate_morning_briefing()

    # TODO: Create email draft via Gmail API
    # For now, just return the briefing
    return {
        "message": "Morning briefing generated",
        "briefing": briefing.model_dump(),
    }


@router.get("/history")
async def get_briefing_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 7,
) -> list[dict]:
    """Get history of past briefings."""
    # TODO: Implement briefing history storage and retrieval
    return []
