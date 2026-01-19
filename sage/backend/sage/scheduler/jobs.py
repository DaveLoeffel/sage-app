"""Scheduled background jobs using APScheduler."""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from sage.config import get_settings
from sage.services.database import async_session_maker

settings = get_settings()
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def email_sync_job():
    """Sync emails from Gmail every 5 minutes."""
    logger.info("Starting email sync job")
    try:
        async with async_session_maker() as db:
            from sage.core.email_processor import EmailProcessor

            processor = EmailProcessor(db)
            count = await processor.sync_emails(max_results=settings.email_sync_max_results)
            logger.info(f"Email sync completed: {count} new emails")

            # Also check for replies to close follow-ups
            closed = await processor.detect_replies()
            if closed > 0:
                logger.info(f"Auto-closed {closed} follow-ups due to replies")
    except Exception as e:
        logger.error(f"Email sync job failed: {e}")


async def followup_reminder_job():
    """Process follow-up reminders (runs hourly)."""
    logger.info("Starting follow-up reminder job")
    try:
        async with async_session_maker() as db:
            from sage.core.followup_tracker import FollowupTracker

            tracker = FollowupTracker(db)

            # Process Day 2 reminders
            reminded = await tracker.process_reminders()
            if reminded > 0:
                logger.info(f"Sent {reminded} follow-up reminders")

            # Process Day 7 escalations
            escalated = await tracker.process_escalations()
            if escalated > 0:
                logger.info(f"Escalated {escalated} follow-ups")
    except Exception as e:
        logger.error(f"Follow-up reminder job failed: {e}")


async def morning_briefing_job():
    """Generate morning briefing at 6:30 AM ET."""
    logger.info("Starting morning briefing generation")
    try:
        async with async_session_maker() as db:
            from sage.core.briefing_generator import BriefingGenerator

            generator = BriefingGenerator(db)
            briefing = await generator.generate_morning_briefing()

            # TODO: Send briefing as email draft or notification
            logger.info(f"Morning briefing generated: {briefing.overnight_emails_count} overnight emails")
    except Exception as e:
        logger.error(f"Morning briefing job failed: {e}")


async def weekly_review_job():
    """Generate weekly review on Saturday at 8 AM ET."""
    logger.info("Starting weekly review generation")
    try:
        async with async_session_maker() as db:
            from sage.core.briefing_generator import BriefingGenerator

            generator = BriefingGenerator(db)
            review = await generator.generate_weekly_review()

            # TODO: Send review as email draft or notification
            logger.info(f"Weekly review generated for week of {review.week_of}")
    except Exception as e:
        logger.error(f"Weekly review job failed: {e}")


async def start_scheduler():
    """Start the scheduler with all jobs."""
    # Email sync every 5 minutes
    scheduler.add_job(
        email_sync_job,
        IntervalTrigger(minutes=settings.email_sync_interval_minutes),
        id="email_sync",
        name="Email Sync",
        replace_existing=True,
    )

    # Follow-up reminders every hour
    scheduler.add_job(
        followup_reminder_job,
        IntervalTrigger(hours=1),
        id="followup_reminders",
        name="Follow-up Reminders",
        replace_existing=True,
    )

    # Morning briefing at 6:30 AM ET (11:30 UTC during EST)
    scheduler.add_job(
        morning_briefing_job,
        CronTrigger(
            hour=settings.morning_briefing_hour + 5,  # Convert ET to UTC
            minute=settings.morning_briefing_minute,
            timezone="UTC",
        ),
        id="morning_briefing",
        name="Morning Briefing",
        replace_existing=True,
    )

    # Weekly review Saturday at 8 AM ET (13:00 UTC during EST)
    scheduler.add_job(
        weekly_review_job,
        CronTrigger(
            day_of_week="sat",
            hour=13,  # 8 AM ET in UTC
            minute=0,
            timezone="UTC",
        ),
        id="weekly_review",
        name="Weekly Review",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with all jobs")


async def stop_scheduler():
    """Stop the scheduler."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


def get_job_status() -> list[dict]:
    """Get status of all scheduled jobs."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return jobs
