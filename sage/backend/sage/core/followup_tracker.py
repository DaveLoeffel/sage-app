"""Follow-up tracking and reminder logic."""

from datetime import datetime, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from sage.config import get_settings
from sage.models.followup import Followup, FollowupStatus
from sage.models.email import EmailCache
from sage.core.claude_agent import get_claude_agent

settings = get_settings()


class FollowupTracker:
    """Track and manage follow-ups."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def auto_create_followup(self, email: EmailCache) -> Followup | None:
        """Auto-create a follow-up for an email that requires response."""
        if not email.requires_response:
            return None

        # Check if followup already exists for this email
        existing = await self.db.execute(
            select(Followup).where(Followup.gmail_id == email.gmail_id)
        )
        if existing.scalar_one_or_none():
            return None

        # Get user
        from sage.models.user import User
        user_result = await self.db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        if not user:
            return None

        # Calculate due date based on priority
        days_to_respond = settings.followup_reminder_days
        if email.priority:
            if email.priority.value == "urgent":
                days_to_respond = 1
            elif email.priority.value == "high":
                days_to_respond = 2

        due_date = datetime.utcnow() + timedelta(days=days_to_respond)

        followup = Followup(
            user_id=user.id,
            email_id=email.id,
            gmail_id=email.gmail_id,
            thread_id=email.thread_id,
            subject=email.subject,
            contact_email=email.sender_email,
            contact_name=email.sender_name,
            due_date=due_date,
            ai_summary=email.summary,
        )

        self.db.add(followup)
        await self.db.commit()
        await self.db.refresh(followup)

        return followup

    async def process_reminders(self) -> int:
        """Process Day 2 reminders for pending follow-ups."""
        now = datetime.utcnow()
        reminder_threshold = now - timedelta(days=settings.followup_reminder_days)

        # Get pending followups that are past the reminder threshold
        result = await self.db.execute(
            select(Followup).where(
                and_(
                    Followup.status == FollowupStatus.PENDING,
                    Followup.due_date <= now,
                    Followup.reminder_sent_at.is_(None),
                )
            )
        )
        followups = result.scalars().all()

        reminded_count = 0
        for followup in followups:
            await self._send_reminder(followup)
            followup.mark_reminded()
            reminded_count += 1

        if reminded_count > 0:
            await self.db.commit()

        return reminded_count

    async def process_escalations(self) -> int:
        """Process Day 7 escalations for reminded follow-ups."""
        now = datetime.utcnow()

        # Get reminded followups past the escalation threshold
        result = await self.db.execute(
            select(Followup).where(
                and_(
                    Followup.status == FollowupStatus.REMINDED,
                    Followup.escalated_at.is_(None),
                )
            )
        )
        followups = result.scalars().all()

        escalated_count = 0
        for followup in followups:
            # Check if enough time has passed since reminder
            if followup.reminder_sent_at:
                days_since_reminder = (now - followup.reminder_sent_at).days
                escalation_days = followup.escalation_days or settings.followup_escalation_days

                if days_since_reminder >= (escalation_days - settings.followup_reminder_days):
                    await self._send_escalation(followup)
                    followup.mark_escalated()
                    escalated_count += 1

        if escalated_count > 0:
            await self.db.commit()

        return escalated_count

    async def _send_reminder(self, followup: Followup) -> None:
        """Generate and send a reminder email draft."""
        agent = await get_claude_agent()

        # Get the original email
        email_result = await self.db.execute(
            select(EmailCache).where(EmailCache.gmail_id == followup.gmail_id)
        )
        original_email = email_result.scalar_one_or_none()

        if not original_email:
            return

        # Generate reminder draft
        prompt = f"""Generate a gentle follow-up reminder email for this unanswered email.

Original Email:
From: {original_email.sender_name} <{original_email.sender_email}>
Subject: {original_email.subject}
Date: {original_email.received_at}

{original_email.body_text or original_email.snippet or '[No content]'}

Create a brief, professional follow-up that:
1. Politely references the original email
2. Restates the key question or request
3. Maintains a friendly, non-pushy tone
4. Is 3-5 sentences maximum

Return just the email body, no subject line."""

        from anthropic import Anthropic
        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        reminder_body = response.content[0].text

        # TODO: Create Gmail draft via MCP
        # For now, just log that we would send the reminder
        print(f"Would send reminder for followup {followup.id}: {reminder_body[:100]}...")

    async def _send_escalation(self, followup: Followup) -> None:
        """Generate and send an escalation email draft."""
        agent = await get_claude_agent()

        # Get the original email
        email_result = await self.db.execute(
            select(EmailCache).where(EmailCache.gmail_id == followup.gmail_id)
        )
        original_email = email_result.scalar_one_or_none()

        if not original_email:
            return

        # Check if we have an escalation email (supervisor)
        cc_list = [followup.escalation_email] if followup.escalation_email else []

        # Generate escalation draft
        prompt = f"""Generate a firmer follow-up email for this repeatedly unanswered email.

Original Email:
From: {original_email.sender_name} <{original_email.sender_email}>
Subject: {original_email.subject}
Date: {original_email.received_at}

{original_email.body_text or original_email.snippet or '[No content]'}

Context:
- A reminder was already sent {settings.followup_escalation_days - settings.followup_reminder_days} days ago
- This is Day 7 follow-up
{'- Their supervisor (' + followup.escalation_email + ') will be CC\'d' if followup.escalation_email else ''}

Create a professional but firmer follow-up that:
1. Notes this is a second follow-up
2. Emphasizes the importance/urgency of a response
3. Sets a clear deadline if appropriate
4. Remains professional
5. Is 4-6 sentences

Return just the email body, no subject line."""

        from anthropic import Anthropic
        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        escalation_body = response.content[0].text

        # TODO: Create Gmail draft via MCP with CC
        # For now, just log that we would send the escalation
        print(f"Would send escalation for followup {followup.id} (CC: {cc_list}): {escalation_body[:100]}...")

    async def get_overdue_summary(self) -> dict:
        """Get a summary of overdue follow-ups."""
        now = datetime.utcnow()

        result = await self.db.execute(
            select(Followup).where(
                and_(
                    Followup.status.in_([
                        FollowupStatus.PENDING,
                        FollowupStatus.REMINDED,
                    ]),
                    Followup.due_date < now,
                )
            )
        )
        overdue = result.scalars().all()

        # Group by days overdue
        by_days = {
            "1_day": [],
            "2_3_days": [],
            "4_7_days": [],
            "over_week": [],
        }

        for f in overdue:
            days_overdue = (now - f.due_date).days
            if days_overdue <= 1:
                by_days["1_day"].append(f)
            elif days_overdue <= 3:
                by_days["2_3_days"].append(f)
            elif days_overdue <= 7:
                by_days["4_7_days"].append(f)
            else:
                by_days["over_week"].append(f)

        return {
            "total": len(overdue),
            "by_severity": {
                "critical": len(by_days["over_week"]),
                "high": len(by_days["4_7_days"]),
                "medium": len(by_days["2_3_days"]),
                "low": len(by_days["1_day"]),
            },
            "items": [
                {
                    "id": f.id,
                    "subject": f.subject,
                    "contact": f.contact_email,
                    "days_overdue": (now - f.due_date).days,
                }
                for f in overdue
            ],
        }
