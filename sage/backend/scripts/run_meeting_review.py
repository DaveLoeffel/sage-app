#!/usr/bin/env python3
"""Run meeting review to extract action items from the last 30 days.

This script runs the MeetingReviewService to scan all meetings
and recordings from the last 30 days, extracting follow-ups and todos.

Usage:
    docker compose exec backend python scripts/run_meeting_review.py [--days 30]
"""

import asyncio
import argparse
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main(days_back: int = 30, dry_run: bool = False):
    """Run the meeting review."""
    from sqlalchemy import select

    from sage.services.database import async_session_maker
    from sage.services.meeting_reviewer import MeetingReviewService
    from sage.models.user import User

    logger.info(f"Starting meeting review for last {days_back} days (dry_run={dry_run})")

    async with async_session_maker() as db:
        # Get the user
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()

        if not user:
            logger.error("No user found in database. Please log in first.")
            return 1

        logger.info(f"Running review for user: {user.email}")

        # Initialize service
        service = MeetingReviewService(user_email=user.email)

        # Define progress callback
        def progress_callback(message: str, percent: int):
            logger.info(f"[{percent:3d}%] {message}")

        # Run the review
        progress = await service.review_all_meetings(
            db=db,
            user_id=user.id,
            days_back=days_back,
            create_entries=not dry_run,
            progress_callback=progress_callback,
        )

        # Print results
        print("\n" + "=" * 60)
        print("MEETING REVIEW COMPLETE")
        print("=" * 60)
        print(f"Total meetings found:     {progress.total_meetings}")
        print(f"  - Fireflies:            {progress.meetings_by_source.get('fireflies', 0)}")
        print(f"  - Plaud recordings:     {progress.meetings_by_source.get('plaud', 0)}")
        print(f"Meetings reviewed:        {progress.reviewed}")
        print(f"Errors:                   {progress.errors}")
        print("-" * 60)
        if not dry_run:
            print(f"Todos created:            {progress.todos_created}")
            print(f"Follow-ups created:       {progress.followups_created}")
        else:
            print("(DRY RUN - no entries created)")
        print("=" * 60)

        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Review meetings and extract action items"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back (default: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze meetings but don't create database entries",
    )

    args = parser.parse_args()

    exit_code = asyncio.run(main(days_back=args.days, dry_run=args.dry_run))
    sys.exit(exit_code)
