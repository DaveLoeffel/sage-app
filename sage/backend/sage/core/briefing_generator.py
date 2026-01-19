"""Briefing generation logic."""

from datetime import datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from sage.config import get_settings
from sage.models.email import EmailCache, EmailCategory, EmailPriority
from sage.models.followup import Followup, FollowupStatus
from sage.schemas.briefing import MorningBriefing, WeeklyReview
from sage.core.claude_agent import get_claude_agent

settings = get_settings()


class BriefingGenerator:
    """Generate morning and weekly briefings."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_morning_briefing(self) -> MorningBriefing:
        """Generate the morning briefing."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today_start - timedelta(days=1)

        # Get overnight emails (since yesterday 6pm EST approximately)
        overnight_start = yesterday.replace(hour=22)  # ~6pm EST in UTC
        overnight_result = await self.db.execute(
            select(EmailCache).where(
                EmailCache.received_at >= overnight_start
            ).order_by(EmailCache.received_at.desc())
        )
        overnight_emails = overnight_result.scalars().all()

        # Filter urgent and action-required emails
        urgent_emails = [
            {
                "id": e.id,
                "subject": e.subject,
                "sender": e.sender_name or e.sender_email,
                "summary": e.summary,
                "received_at": e.received_at.isoformat(),
            }
            for e in overnight_emails
            if e.priority == EmailPriority.URGENT
        ]

        action_emails = [
            {
                "id": e.id,
                "subject": e.subject,
                "sender": e.sender_name or e.sender_email,
                "summary": e.summary,
                "received_at": e.received_at.isoformat(),
            }
            for e in overnight_emails
            if e.category == EmailCategory.ACTION_REQUIRED
        ]

        # Get overdue follow-ups
        overdue_result = await self.db.execute(
            select(Followup).where(
                and_(
                    Followup.status.in_([
                        FollowupStatus.PENDING,
                        FollowupStatus.REMINDED,
                    ]),
                    Followup.due_date < now,
                )
            ).order_by(Followup.due_date)
        )
        overdue_followups = [
            {
                "id": f.id,
                "subject": f.subject,
                "contact": f.contact_name or f.contact_email,
                "days_overdue": (now - f.due_date).days,
            }
            for f in overdue_result.scalars().all()
        ]

        # Get follow-ups due today
        today_end = today_start + timedelta(days=1)
        due_today_result = await self.db.execute(
            select(Followup).where(
                and_(
                    Followup.status.in_([
                        FollowupStatus.PENDING,
                        FollowupStatus.REMINDED,
                    ]),
                    Followup.due_date >= today_start,
                    Followup.due_date < today_end,
                )
            ).order_by(Followup.due_date)
        )
        due_today_followups = [
            {
                "id": f.id,
                "subject": f.subject,
                "contact": f.contact_name or f.contact_email,
            }
            for f in due_today_result.scalars().all()
        ]

        # TODO: Get today's calendar events from Google Calendar MCP
        todays_events: list[dict] = []

        # TODO: Get stock prices from Alpha Vantage MCP
        stock_summary = None

        # Generate AI insights
        agent = await get_claude_agent()
        insights = await self._generate_insights(
            urgent_emails=urgent_emails,
            action_emails=action_emails,
            overdue_followups=overdue_followups,
            todays_events=todays_events,
        )

        # Format greeting based on time
        hour = now.hour
        if hour < 12:
            greeting = "Good morning, Dave"
        elif hour < 17:
            greeting = "Good afternoon, Dave"
        else:
            greeting = "Good evening, Dave"

        return MorningBriefing(
            greeting=greeting,
            date=now.strftime("%A, %B %d, %Y"),
            weather=None,  # TODO: Integrate weather API
            overnight_emails_count=len(overnight_emails),
            urgent_emails=urgent_emails[:5],
            action_required_emails=action_emails[:5],
            overdue_followups=overdue_followups[:5],
            due_today_followups=due_today_followups[:5],
            todays_events=todays_events,
            next_meeting_in=None,  # TODO: Calculate from calendar
            stock_summary=stock_summary,
            property_metrics=None,  # TODO: From Entrata parser
            key_priorities=insights.get("priorities", []),
            suggested_actions=insights.get("actions", []),
            generated_at=now,
        )

    async def generate_weekly_review(self) -> WeeklyReview:
        """Generate the weekly review briefing."""
        now = datetime.utcnow()
        week_start = now - timedelta(days=7)

        # Email stats
        emails_received_result = await self.db.execute(
            select(func.count()).select_from(EmailCache).where(
                EmailCache.received_at >= week_start
            )
        )
        emails_received = emails_received_result.scalar() or 0

        # TODO: Track sent emails to calculate emails_sent
        emails_sent = 0

        # Follow-up stats
        followups_created_result = await self.db.execute(
            select(func.count()).select_from(Followup).where(
                Followup.created_at >= week_start
            )
        )
        followups_created = followups_created_result.scalar() or 0

        followups_completed_result = await self.db.execute(
            select(func.count()).select_from(Followup).where(
                and_(
                    Followup.status == FollowupStatus.COMPLETED,
                    Followup.completed_at >= week_start,
                )
            )
        )
        followups_completed = followups_completed_result.scalar() or 0

        followups_escalated_result = await self.db.execute(
            select(func.count()).select_from(Followup).where(
                and_(
                    Followup.status == FollowupStatus.ESCALATED,
                    Followup.escalated_at >= week_start,
                )
            )
        )
        followups_escalated = followups_escalated_result.scalar() or 0

        current_overdue_result = await self.db.execute(
            select(func.count()).select_from(Followup).where(
                and_(
                    Followup.status.in_([
                        FollowupStatus.PENDING,
                        FollowupStatus.REMINDED,
                    ]),
                    Followup.due_date < now,
                )
            )
        )
        current_overdue = current_overdue_result.scalar() or 0

        # TODO: Get meeting stats from Google Calendar MCP
        meetings_attended = 0
        total_meeting_hours = 0.0

        # Generate AI insights for the week
        agent = await get_claude_agent()
        weekly_insights = await self._generate_weekly_insights(
            emails_received=emails_received,
            followups_created=followups_created,
            followups_completed=followups_completed,
            followups_escalated=followups_escalated,
            current_overdue=current_overdue,
        )

        return WeeklyReview(
            week_of=week_start.strftime("%B %d, %Y"),
            emails_received=emails_received,
            emails_sent=emails_sent,
            avg_response_time=None,
            followups_created=followups_created,
            followups_completed=followups_completed,
            followups_escalated=followups_escalated,
            current_overdue=current_overdue,
            meetings_attended=meetings_attended,
            total_meeting_hours=total_meeting_hours,
            key_accomplishments=weekly_insights.get("accomplishments", []),
            areas_of_concern=weekly_insights.get("concerns", []),
            recommendations=weekly_insights.get("recommendations", []),
            generated_at=now,
        )

    async def _generate_insights(
        self,
        urgent_emails: list,
        action_emails: list,
        overdue_followups: list,
        todays_events: list,
    ) -> dict:
        """Generate AI insights for morning briefing."""
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key)

        prompt = f"""Based on this morning's data, provide key priorities and suggested actions for Dave Loeffel (CEO).

Urgent Emails: {len(urgent_emails)}
{chr(10).join(f"- {e['subject']} from {e['sender']}" for e in urgent_emails[:3]) if urgent_emails else "None"}

Action Required: {len(action_emails)}
{chr(10).join(f"- {e['subject']} from {e['sender']}" for e in action_emails[:3]) if action_emails else "None"}

Overdue Follow-ups: {len(overdue_followups)}
{chr(10).join(f"- {f['subject']} ({f['days_overdue']} days)" for f in overdue_followups[:3]) if overdue_followups else "None"}

Today's Events: {len(todays_events)}
{chr(10).join(f"- {e.get('title', 'Meeting')}" for e in todays_events[:3]) if todays_events else "No scheduled events"}

Respond in JSON format:
{{
    "priorities": ["top priority 1", "top priority 2", "top priority 3"],
    "actions": ["suggested action 1", "suggested action 2", "suggested action 3"]
}}"""

        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        try:
            import json
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
        except Exception:
            pass

        return {
            "priorities": ["Review urgent emails", "Address overdue follow-ups"],
            "actions": ["Check email inbox", "Review follow-up list"],
        }

    async def _generate_weekly_insights(
        self,
        emails_received: int,
        followups_created: int,
        followups_completed: int,
        followups_escalated: int,
        current_overdue: int,
    ) -> dict:
        """Generate AI insights for weekly review."""
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key)

        prompt = f"""Analyze this week's activity for Dave Loeffel (CEO) and provide insights.

Weekly Stats:
- Emails received: {emails_received}
- Follow-ups created: {followups_created}
- Follow-ups completed: {followups_completed}
- Follow-ups escalated: {followups_escalated}
- Currently overdue: {current_overdue}

Provide:
1. Key accomplishments (based on completion rate)
2. Areas of concern (if escalations or overdue items are high)
3. Recommendations for next week

Respond in JSON format:
{{
    "accomplishments": ["accomplishment 1", "accomplishment 2"],
    "concerns": ["concern 1"] or [],
    "recommendations": ["recommendation 1", "recommendation 2"]
}}"""

        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        try:
            import json
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
        except Exception:
            pass

        return {
            "accomplishments": [f"Completed {followups_completed} follow-ups"],
            "concerns": [f"{current_overdue} items currently overdue"] if current_overdue > 0 else [],
            "recommendations": ["Continue tracking follow-ups"],
        }
