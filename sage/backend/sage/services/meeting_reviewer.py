"""Meeting review service for extracting follow-ups and todos from meetings.

Scans Fireflies transcripts and Plaud recordings to extract action items.
Uses AI to articulate each follow-up and todo item.
"""

import logging
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from sage.models.meeting import MeetingNote
from sage.models.email import EmailCache
from sage.models.todo import TodoItem, TodoCategory, TodoPriority, TodoStatus
from sage.models.followup import Followup, FollowupStatus, FollowupPriority
from sage.models.contact import Contact
from sage.services.fireflies import get_fireflies_service

logger = logging.getLogger(__name__)


class ActionItemType(str, Enum):
    """Type of extracted action item."""
    TODO_FOR_DAVE = "todo_for_dave"  # Dave needs to do this
    FOLLOWUP_EXPECTED = "followup_expected"  # Dave is waiting on someone
    TODO_FOR_OTHER = "todo_for_other"  # Someone else needs to do (might become followup)
    INFO_ONLY = "info_only"  # Not actionable


@dataclass
class ExtractedActionItem:
    """An action item extracted from a meeting."""
    description: str
    item_type: ActionItemType
    assignee: Optional[str]  # Name of person responsible
    assignee_email: Optional[str]
    due_date: Optional[date]
    due_date_text: Optional[str]  # Original text like "by Friday"
    priority: str  # urgent, high, normal, low
    context: str  # Brief context about the meeting/discussion
    confidence: float  # 0.0-1.0


@dataclass
class MeetingReviewResult:
    """Result of reviewing a single meeting."""
    meeting_id: str
    meeting_title: str
    meeting_date: Optional[datetime]
    source: str  # "fireflies" or "plaud"
    action_items: list[ExtractedActionItem] = field(default_factory=list)
    todos_created: int = 0
    followups_created: int = 0
    error: Optional[str] = None


@dataclass
class ReviewProgress:
    """Progress tracking for meeting review."""
    total_meetings: int = 0
    reviewed: int = 0
    todos_created: int = 0
    followups_created: int = 0
    errors: int = 0
    meetings_by_source: dict = field(default_factory=lambda: {"fireflies": 0, "plaud": 0})


class MeetingReviewService:
    """
    Reviews meetings to extract follow-ups and todos.

    Uses AI to analyze meeting transcripts and Plaud recordings,
    extracting actionable items and creating database entries.
    """

    # Plaud email patterns (same as in meetings.py)
    PLAUD_SUBJECT_PATTERN = "Meeting Notes from Plaud"
    LEGACY_MEETING_NOTES_SENDER = "dloeffel@highlandsresidential.com"
    LEGACY_MEETING_NOTES_PREFIX = "Meeting Notes"
    LEGACY_MEETING_NOTES_CUTOFF = datetime(2026, 1, 16)

    # Dave's email for identifying action items assigned to him
    DAVE_IDENTIFIERS = [
        "dave", "david", "loeffel", "dloeffel",
        "dloeffel@highlandsresidential.com"
    ]

    def __init__(self, user_email: str):
        """Initialize the service."""
        self.user_email = user_email.lower()

    async def _get_claude_client(self):
        """Get Claude client for AI extraction."""
        from sage.core.claude_agent import get_claude_agent
        agent = await get_claude_agent()
        return agent.client

    async def extract_action_items_from_text(
        self,
        text: str,
        meeting_title: str,
        participants: list[str] = None,
        meeting_date: Optional[datetime] = None,
    ) -> list[ExtractedActionItem]:
        """
        Use AI to extract action items from meeting text.

        Args:
            text: Meeting transcript or notes text
            meeting_title: Title of the meeting
            participants: List of participant names/emails
            meeting_date: Date of the meeting (for relative date parsing)
        """
        if not text or len(text.strip()) < 50:
            return []

        client = await self._get_claude_client()

        # Build context about participants
        participant_context = ""
        if participants:
            participant_context = f"\nParticipants: {', '.join(participants)}"

        reference_date = meeting_date.strftime("%Y-%m-%d") if meeting_date else date.today().isoformat()

        prompt = f"""Analyze this meeting transcript/notes and extract ALL action items.

Meeting: {meeting_title}
Date: {reference_date}{participant_context}

--- MEETING CONTENT ---
{text[:8000]}
--- END CONTENT ---

For each action item found, determine:
1. DESCRIPTION: Clear, actionable description of what needs to be done
2. TYPE: One of:
   - TODO_FOR_DAVE: Dave Loeffel needs to do this himself
   - FOLLOWUP_EXPECTED: Dave is waiting for someone else to complete something (he should follow up)
   - TODO_FOR_OTHER: Someone else committed to do something (may need tracking)
   - INFO_ONLY: Mentioned but not actionable
3. ASSIGNEE: Who is responsible (name and email if available)
4. DUE_DATE: Any mentioned deadline (as YYYY-MM-DD or null)
5. DUE_DATE_TEXT: Original text mentioning deadline (e.g., "by Friday", "next week")
6. PRIORITY: urgent/high/normal/low based on language used
7. CONTEXT: Brief context about why this item exists (1-2 sentences)
8. CONFIDENCE: Your confidence this is a real action item (0.0-1.0)

Dave Loeffel is the user. Look for:
- Things Dave said he would do ("I'll", "I will", "let me")
- Things others agreed to do for Dave (potential follow-ups)
- Questions or requests that need answers
- Deadlines mentioned
- Commitments made

Respond in JSON format:
{{
  "action_items": [
    {{
      "description": "Send Q4 investor update to partners",
      "type": "TODO_FOR_DAVE",
      "assignee": "Dave Loeffel",
      "assignee_email": "dloeffel@highlandsresidential.com",
      "due_date": "2026-01-25",
      "due_date_text": "by end of week",
      "priority": "high",
      "context": "Discussed during investor relations segment, partners need update before board meeting",
      "confidence": 0.9
    }}
  ]
}}

If no action items found, return {{"action_items": []}}"""

        try:
            # Note: Anthropic client uses synchronous API
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text.strip()

            # Parse JSON response
            import json
            import re

            # Handle potential markdown code blocks
            if response_text.startswith("```"):
                # Find the JSON content between code blocks
                match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
                if match:
                    response_text = match.group(1).strip()
                else:
                    # Fallback: remove first and last lines
                    lines = response_text.split("\n")
                    response_text = "\n".join(lines[1:-1])

            # Try to find JSON object in response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                response_text = json_match.group(0)

            try:
                data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse failed for '{meeting_title}': {e}. Returning empty list.")
                return []
            items = []

            for item in data.get("action_items", []):
                # Parse item type (handle case variations)
                type_str = item.get("type", "info_only").lower()
                try:
                    item_type = ActionItemType(type_str)
                except ValueError:
                    # Map common variations
                    type_mapping = {
                        "todo_for_dave": ActionItemType.TODO_FOR_DAVE,
                        "followup_expected": ActionItemType.FOLLOWUP_EXPECTED,
                        "todo_for_other": ActionItemType.TODO_FOR_OTHER,
                        "info_only": ActionItemType.INFO_ONLY,
                    }
                    item_type = type_mapping.get(type_str, ActionItemType.INFO_ONLY)

                # Parse due date
                due_date = None
                if item.get("due_date"):
                    try:
                        due_date = date.fromisoformat(item["due_date"])
                    except ValueError:
                        pass

                items.append(ExtractedActionItem(
                    description=item.get("description", ""),
                    item_type=item_type,
                    assignee=item.get("assignee"),
                    assignee_email=item.get("assignee_email"),
                    due_date=due_date,
                    due_date_text=item.get("due_date_text"),
                    priority=item.get("priority", "normal"),
                    context=item.get("context", ""),
                    confidence=float(item.get("confidence", 0.5)),
                ))

            return items

        except Exception as e:
            logger.error(f"AI extraction failed for '{meeting_title}': {e}")
            return []

    async def review_fireflies_meeting(
        self,
        db: AsyncSession,
        meeting_id: str,
        user_id: int,
        create_entries: bool = True,
    ) -> MeetingReviewResult:
        """
        Review a Fireflies meeting and extract action items.

        Args:
            db: Database session
            meeting_id: Fireflies meeting ID
            user_id: User ID for created entries
            create_entries: Whether to create todo/followup entries
        """
        service = get_fireflies_service()

        if not service.is_configured:
            return MeetingReviewResult(
                meeting_id=meeting_id,
                meeting_title="Unknown",
                meeting_date=None,
                source="fireflies",
                error="Fireflies not configured",
            )

        try:
            # Fetch full meeting details
            meeting = await service.get_meeting_transcript(meeting_id)

            if not meeting or meeting.get("error"):
                return MeetingReviewResult(
                    meeting_id=meeting_id,
                    meeting_title="Unknown",
                    meeting_date=None,
                    source="fireflies",
                    error=meeting.get("error", "Meeting not found"),
                )

            # Parse meeting date
            meeting_date = None
            if meeting.get("date"):
                try:
                    meeting_date = datetime.fromisoformat(
                        meeting["date"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except ValueError:
                    pass

            # Build transcript text
            transcript_parts = []

            # Add summary if available
            if meeting.get("summary"):
                transcript_parts.append(f"Summary: {meeting['summary']}")

            # Add key points if available
            if meeting.get("key_points"):
                transcript_parts.append("Key Points:")
                for point in meeting["key_points"]:
                    transcript_parts.append(f"- {point}")

            # Add existing action items (Fireflies AI)
            if meeting.get("action_items"):
                transcript_parts.append("Fireflies Action Items:")
                for item in meeting["action_items"]:
                    transcript_parts.append(f"- {item}")

            # Add transcript
            if meeting.get("transcript"):
                transcript_parts.append("\nTranscript:")
                for entry in meeting["transcript"][:100]:  # Limit to first 100 entries
                    speaker = entry.get("speaker", "Unknown")
                    text = entry.get("text", "")
                    transcript_parts.append(f"{speaker}: {text}")

            full_text = "\n".join(transcript_parts)

            # Extract action items with AI
            action_items = await self.extract_action_items_from_text(
                text=full_text,
                meeting_title=meeting.get("title", "Unknown Meeting"),
                participants=meeting.get("participants", []),
                meeting_date=meeting_date,
            )

            result = MeetingReviewResult(
                meeting_id=meeting_id,
                meeting_title=meeting.get("title", "Unknown Meeting"),
                meeting_date=meeting_date,
                source="fireflies",
                action_items=action_items,
            )

            # Create database entries if requested
            if create_entries and action_items:
                todos, followups = await self._create_entries_from_items(
                    db=db,
                    user_id=user_id,
                    items=action_items,
                    source_type="meeting",
                    source_id=meeting_id,
                    source_summary=f"From meeting: {meeting.get('title', 'Unknown')}",
                    meeting_date=meeting_date,
                )
                result.todos_created = todos
                result.followups_created = followups

            return result

        except Exception as e:
            logger.error(f"Failed to review Fireflies meeting {meeting_id}: {e}")
            return MeetingReviewResult(
                meeting_id=meeting_id,
                meeting_title="Unknown",
                meeting_date=None,
                source="fireflies",
                error=str(e),
            )

    async def review_plaud_recording(
        self,
        db: AsyncSession,
        email: EmailCache,
        user_id: int,
        create_entries: bool = True,
    ) -> MeetingReviewResult:
        """
        Review a Plaud recording email and extract action items.

        Args:
            db: Database session
            email: EmailCache entry containing Plaud recording
            user_id: User ID for created entries
            create_entries: Whether to create todo/followup entries
        """
        # Extract title from subject
        title = self._extract_plaud_title(email.subject, email.received_at)

        result = MeetingReviewResult(
            meeting_id=f"plaud_{email.id}",
            meeting_title=title,
            meeting_date=email.received_at,
            source="plaud",
        )

        if not email.body_text or len(email.body_text.strip()) < 50:
            result.error = "No content to analyze"
            return result

        try:
            # Extract action items with AI
            action_items = await self.extract_action_items_from_text(
                text=email.body_text,
                meeting_title=title,
                participants=[],  # Plaud doesn't have structured participants
                meeting_date=email.received_at,
            )

            result.action_items = action_items

            # Create database entries if requested
            if create_entries and action_items:
                todos, followups = await self._create_entries_from_items(
                    db=db,
                    user_id=user_id,
                    items=action_items,
                    source_type="meeting",
                    source_id=email.gmail_id,
                    source_summary=f"From Plaud: {title}",
                    meeting_date=email.received_at,
                )
                result.todos_created = todos
                result.followups_created = followups

            return result

        except Exception as e:
            logger.error(f"Failed to review Plaud recording {email.id}: {e}")
            result.error = str(e)
            return result

    def _extract_plaud_title(self, subject: str, received_at: datetime) -> str:
        """Extract a clean title from a Plaud email subject."""
        title = subject or "Untitled Recording"

        if "Meeting Notes from Plaud" in title:
            title = title.replace("Meeting Notes from Plaud", "").strip()
            if title.startswith(":"):
                title = title[1:].strip()
            if title.startswith("-"):
                title = title[1:].strip()
            if not title:
                title = f"Plaud Recording - {received_at.strftime('%b %d, %Y')}"
        elif title.startswith(self.LEGACY_MEETING_NOTES_PREFIX):
            title = title[len(self.LEGACY_MEETING_NOTES_PREFIX):].strip()
            if title.startswith(":"):
                title = title[1:].strip()
            if title.startswith("-"):
                title = title[1:].strip()
            if not title:
                title = f"Meeting Notes - {received_at.strftime('%b %d, %Y')}"

        return title

    async def _create_entries_from_items(
        self,
        db: AsyncSession,
        user_id: int,
        items: list[ExtractedActionItem],
        source_type: str,
        source_id: str,
        source_summary: str,
        meeting_date: Optional[datetime],
    ) -> tuple[int, int]:
        """
        Create todo and followup entries from extracted items.

        Returns: (todos_created, followups_created)
        """
        todos_created = 0
        followups_created = 0

        for item in items:
            # Skip low confidence items
            if item.confidence < 0.6:
                continue

            # Skip items marked as info only
            if item.item_type == ActionItemType.INFO_ONLY:
                continue

            # Check for duplicates
            existing_todo = await db.execute(
                select(TodoItem).where(
                    and_(
                        TodoItem.source_id == source_id,
                        TodoItem.title.ilike(f"%{item.description[:50]}%"),
                    )
                )
            )
            if existing_todo.scalar_one_or_none():
                continue

            if item.item_type == ActionItemType.TODO_FOR_DAVE:
                # Create todo for Dave
                priority = self._map_priority_to_todo(item.priority)

                todo = TodoItem(
                    user_id=user_id,
                    title=item.description[:500],
                    description=f"{item.context}\n\nExtracted from: {source_summary}",
                    category=TodoCategory.MEETING_ACTION,
                    priority=priority,
                    status=TodoStatus.PENDING,
                    due_date=item.due_date,
                    source_type=source_type,
                    source_id=source_id,
                    source_summary=source_summary,
                    contact_name=item.assignee if item.assignee and "dave" not in item.assignee.lower() else None,
                    contact_email=item.assignee_email,
                    detection_confidence=item.confidence,
                    detected_deadline_text=item.due_date_text,
                )
                db.add(todo)
                todos_created += 1

            elif item.item_type in (ActionItemType.FOLLOWUP_EXPECTED, ActionItemType.TODO_FOR_OTHER):
                # Create followup (Dave waiting on someone)
                if not item.assignee_email and not item.assignee:
                    # Can't create followup without knowing who
                    continue

                # Check for existing followup
                existing = await db.execute(
                    select(Followup).where(
                        and_(
                            Followup.subject.ilike(f"%{item.description[:50]}%"),
                            Followup.status.in_([FollowupStatus.PENDING, FollowupStatus.REMINDED]),
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                priority = self._map_priority_to_followup(item.priority)

                # Calculate due date (default to 3 business days if not specified)
                due_date = item.due_date
                if not due_date:
                    due_date = self._add_business_days(
                        meeting_date or datetime.utcnow(),
                        3
                    )

                followup = Followup(
                    user_id=user_id,
                    gmail_id=None,  # No gmail_id for meeting-based followups
                    thread_id=None,
                    subject=item.description[:500],
                    contact_email=item.assignee_email or "",
                    contact_name=item.assignee,
                    status=FollowupStatus.PENDING,
                    priority=priority,
                    due_date=due_date,
                    notes=f"{item.context}\n\nExtracted from: {source_summary}",
                    ai_summary=f"Meeting action: {item.assignee or 'Someone'} to complete this. "
                              f"Confidence: {item.confidence:.0%}",
                    source_type=source_type,
                    source_id=source_id,
                )
                db.add(followup)
                followups_created += 1

        await db.flush()
        return todos_created, followups_created

    def _map_priority_to_todo(self, priority: str) -> TodoPriority:
        """Map extracted priority to TodoPriority."""
        priority = priority.lower()
        if priority == "urgent":
            return TodoPriority.URGENT
        elif priority == "high":
            return TodoPriority.HIGH
        elif priority == "low":
            return TodoPriority.LOW
        return TodoPriority.NORMAL

    def _map_priority_to_followup(self, priority: str) -> FollowupPriority:
        """Map extracted priority to FollowupPriority."""
        priority = priority.lower()
        if priority == "urgent":
            return FollowupPriority.URGENT
        elif priority == "high":
            return FollowupPriority.HIGH
        elif priority == "low":
            return FollowupPriority.LOW
        return FollowupPriority.NORMAL

    def _add_business_days(self, start_date: datetime, days: int) -> datetime:
        """Add business days to a date."""
        current = start_date
        added = 0
        while added < days:
            current += timedelta(days=1)
            if current.weekday() < 5:
                added += 1
        return current

    async def review_all_meetings(
        self,
        db: AsyncSession,
        user_id: int,
        days_back: int = 30,
        create_entries: bool = True,
        progress_callback=None,
    ) -> ReviewProgress:
        """
        Review all meetings from the last N days.

        Args:
            db: Database session
            user_id: User ID
            days_back: Number of days to look back
            create_entries: Whether to create todo/followup entries
            progress_callback: Optional callback(message, percent)
        """
        progress = ReviewProgress()
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        if progress_callback:
            progress_callback("Loading meetings", 0)

        # Get Fireflies meetings
        fireflies_meetings = []
        service = get_fireflies_service()
        if service.is_configured:
            try:
                # Fetch recent meetings from API
                meetings = await service.list_recent_meetings(limit=50)
                for m in meetings:
                    meeting_date = None
                    if m.get("date"):
                        try:
                            meeting_date = datetime.fromisoformat(
                                m["date"].replace("Z", "+00:00")
                            ).replace(tzinfo=None)
                        except ValueError:
                            pass

                    # Filter to cutoff date
                    if meeting_date and meeting_date >= cutoff_date:
                        fireflies_meetings.append({
                            "id": m["id"],
                            "title": m["title"],
                            "date": meeting_date,
                        })

                progress.meetings_by_source["fireflies"] = len(fireflies_meetings)
            except Exception as e:
                logger.error(f"Failed to fetch Fireflies meetings: {e}")

        # Get Plaud recordings from email cache
        plaud_label_id = await self._get_plaud_label_id(db)
        plaud_filter = self._build_plaud_filter(plaud_label_id)

        result = await db.execute(
            select(EmailCache)
            .where(
                and_(
                    plaud_filter,
                    EmailCache.received_at >= cutoff_date,
                )
            )
            .order_by(EmailCache.received_at.desc())
        )
        plaud_emails = result.scalars().all()
        progress.meetings_by_source["plaud"] = len(plaud_emails)

        progress.total_meetings = len(fireflies_meetings) + len(plaud_emails)

        if progress_callback:
            progress_callback(f"Found {progress.total_meetings} meetings", 10)

        # Review Fireflies meetings
        for i, meeting in enumerate(fireflies_meetings):
            if progress_callback:
                pct = 10 + int(40 * (i + 1) / max(len(fireflies_meetings), 1))
                progress_callback(f"Reviewing Fireflies: {meeting['title'][:30]}", pct)

            result = await self.review_fireflies_meeting(
                db=db,
                meeting_id=meeting["id"],
                user_id=user_id,
                create_entries=create_entries,
            )

            progress.reviewed += 1
            progress.todos_created += result.todos_created
            progress.followups_created += result.followups_created
            if result.error:
                progress.errors += 1

        # Review Plaud recordings
        for i, email in enumerate(plaud_emails):
            if progress_callback:
                title = self._extract_plaud_title(email.subject, email.received_at)
                pct = 50 + int(40 * (i + 1) / max(len(plaud_emails), 1))
                progress_callback(f"Reviewing Plaud: {title[:30]}", pct)

            result = await self.review_plaud_recording(
                db=db,
                email=email,
                user_id=user_id,
                create_entries=create_entries,
            )

            progress.reviewed += 1
            progress.todos_created += result.todos_created
            progress.followups_created += result.followups_created
            if result.error:
                progress.errors += 1

        await db.commit()

        if progress_callback:
            progress_callback("Complete", 100)

        logger.info(
            f"Meeting review complete: {progress.reviewed}/{progress.total_meetings} reviewed, "
            f"{progress.todos_created} todos, {progress.followups_created} followups created"
        )

        return progress

    async def _get_plaud_label_id(self, db: AsyncSession) -> Optional[str]:
        """Get the Gmail label ID for the 'Plaud' label."""
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from sage.config import get_settings
        from sage.models.user import User

        settings = get_settings()

        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()

        if not user or not user.google_access_token:
            return None

        try:
            credentials = Credentials(
                token=user.google_access_token,
                refresh_token=user.google_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
            )
            service = build("gmail", "v1", credentials=credentials)

            results = service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])

            for label in labels:
                if label.get("name") == "Plaud":
                    return label.get("id")

            return None
        except Exception:
            return None

    def _build_plaud_filter(self, plaud_label_id: Optional[str]):
        """Build SQLAlchemy filter for Plaud recordings."""
        conditions = [
            EmailCache.subject.ilike(f"%{self.PLAUD_SUBJECT_PATTERN}%"),
            and_(
                EmailCache.sender_email == self.LEGACY_MEETING_NOTES_SENDER,
                EmailCache.subject.like(f"{self.LEGACY_MEETING_NOTES_PREFIX}%"),
                EmailCache.received_at < self.LEGACY_MEETING_NOTES_CUTOFF,
            ),
        ]

        if plaud_label_id:
            conditions.append(EmailCache.labels.any(plaud_label_id))

        return or_(*conditions)
