"""TodoList detection service.

Scans emails for action items that Dave needs to complete.
Uses hybrid heuristic + AI approach for classification.
"""

import re
import logging
from datetime import datetime, date, timedelta
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from sage.models.email import EmailCache
from sage.models.todo import TodoItem, TodoCategory, TodoPriority, TodoStatus
from sage.models.contact import Contact
from sage.services.database import async_session_maker

logger = logging.getLogger(__name__)


class DetectionResult(str, Enum):
    """Result of heuristic detection."""
    DETECTED = "detected"
    AMBIGUOUS = "ambiguous"
    SKIPPED = "skipped"


@dataclass
class TodoCandidate:
    """Candidate todo item before database insertion."""
    title: str
    description: Optional[str]
    category: TodoCategory
    priority: TodoPriority
    due_date: Optional[date]
    source_type: str
    source_id: str
    source_summary: str
    contact_name: Optional[str]
    contact_email: Optional[str]
    detection_confidence: float
    detected_deadline_text: Optional[str] = None


@dataclass
class ScanProgress:
    """Progress tracking for todo scanning."""
    total_emails: int = 0
    scanned: int = 0
    todos_created: int = 0
    duplicates_skipped: int = 0
    filtered_out: int = 0
    errors: int = 0
    by_category: dict = field(default_factory=lambda: {
        "self_reminder": 0,
        "request_received": 0,
        "commitment_made": 0,
    })


class TodoDetector:
    """Detects action items in emails and creates todo items."""

    # Self-reminder detection patterns
    SELF_REMINDER_SUBJECT_PREFIXES = [
        "reminder:", "todo:", "note to self", "remind me", "don't forget"
    ]

    SELF_REMINDER_BODY_PHRASES = [
        "remind myself", "don't forget", "need to remember",
        "follow up", "follow-up", "followup",
        "note to self", "remember to"
    ]

    # Request detection patterns
    REQUEST_PATTERNS = [
        (r"can you\s+\w+", 30),
        (r"could you\s+\w+", 30),
        (r"would you\s+\w+", 30),
        (r"please\s+(send|review|call|check|update|provide|confirm|schedule|forward|share|prepare|complete|submit|approve)", 25),
        (r"need you to\s+\w+", 25),
        (r"want you to\s+\w+", 20),
        (r"asking you to\s+\w+", 20),
        (r"let me know\s+(if|when|what|how|whether)", 20),
        (r"\?\s*$", 15),  # Ends with question mark
    ]

    # Directive verbs at sentence start (after period or newline)
    DIRECTIVE_PATTERNS = [
        (r"(?:^|[.\n])\s*(Send|Review|Call|Check|Update|Provide|Confirm|Schedule|Forward|Share|Prepare|Complete|Submit|Approve)\s+", 20),
    ]

    # Commitment detection patterns
    COMMITMENT_PATTERNS = [
        (r"I'll\s+\w+", 50),
        (r"I will\s+\w+", 50),
        (r"I can\s+\w+", 40),
        (r"I'm going to\s+\w+", 40),
        (r"I plan to\s+\w+", 35),
        (r"let me\s+(check|get back|look into|review|send|follow up)", 35),
        (r"I'll get back to you", 45),
        (r"I'll follow up", 45),
    ]

    # Soft commitment patterns (lower priority)
    SOFT_COMMITMENT_PATTERNS = [
        (r"I'll try to\s+\w+", 30),
        (r"I might\s+\w+", 25),
        (r"I'll see if", 25),
        (r"I'll attempt", 25),
    ]

    # Social pleasantries that should still be tracked (low priority)
    SOCIAL_PATTERNS = [
        (r"I'll keep you posted", 30),
        (r"let's catch up", 25),
        (r"let's connect", 25),
        (r"let's sync", 25),
        (r"we should (meet|talk|discuss|chat)", 25),
    ]

    # Negative signals for requests
    REQUEST_NEGATIVE_PATTERNS = [
        (r"unsubscribe", -30),
        (r"no action needed", -25),
        (r"fyi only", -25),
        (r"for your information", -20),
        (r"no response (needed|required|necessary)", -25),
    ]

    # Negative signals for commitments
    COMMITMENT_NEGATIVE_PATTERNS = [
        (r"if I\s+(were|could|would)", -40),
        (r"I already\s+\w+", -35),
        (r"I did\s+\w+", -30),
        (r"I won't", -40),
        (r"I can't", -40),
        (r"I cannot", -40),
    ]

    # Deadline extraction patterns
    DEADLINE_PATTERNS = [
        (r"by\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", "weekday"),
        (r"by\s+(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)", "date"),
        (r"by\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})", "month_day"),
        (r"before\s+(eod|end of day|cob|close of business)", "eod"),
        (r"(this|next)\s+(week|monday|tuesday|wednesday|thursday|friday)", "relative_week"),
        (r"(today|tonight)", "today"),
        (r"(tomorrow)", "tomorrow"),
        (r"within\s+(\d+)\s+(day|hour|week)s?", "within"),
        (r"\basap\b", "asap"),
        (r"as soon as possible", "asap"),
        (r"(urgent|urgently)", "urgent"),
    ]

    # Priority keywords
    URGENT_KEYWORDS = ["asap", "urgent", "urgently", "immediately", "right away", "today"]
    HIGH_PRIORITY_KEYWORDS = ["important", "critical", "priority", "deadline"]
    LOW_PRIORITY_KEYWORDS = ["when you get a chance", "no rush", "whenever", "eventually", "low priority"]

    # Filter patterns (skip these emails)
    SKIP_PATTERNS = [
        r"noreply@",
        r"no-reply@",
        r"notifications@",
        r"mailer-daemon@",
        r"calendar-notification@",
        r"Transcript Ready",  # Fireflies transcripts
        r"Meeting Recording",
        r"You have been invited to",  # Calendar invites
    ]

    def __init__(self, user_email: str, vip_contacts: set[str] = None):
        """
        Initialize the detector.

        Args:
            user_email: Dave's email address (to identify self-emails and sent emails)
            vip_contacts: Set of VIP contact email addresses (for priority boost)
        """
        self.user_email = user_email.lower()
        self.vip_contacts = {e.lower() for e in (vip_contacts or set())}

    def should_skip_email(self, email: EmailCache) -> tuple[bool, str]:
        """Check if email should be skipped entirely."""
        # Skip automated emails
        sender_lower = (email.sender_email or "").lower()
        for pattern in self.SKIP_PATTERNS:
            if re.search(pattern, sender_lower, re.IGNORECASE):
                return True, f"Automated sender: {pattern}"
            if email.subject and re.search(pattern, email.subject, re.IGNORECASE):
                return True, f"Automated subject: {pattern}"

        # Skip emails with unsubscribe links (newsletters)
        body = email.body_text or ""
        if re.search(r"unsubscribe", body, re.IGNORECASE) and len(body) > 1000:
            return True, "Newsletter (has unsubscribe)"

        return False, ""

    def detect_self_reminder(self, email: EmailCache) -> tuple[DetectionResult, int, str]:
        """
        Detect if email is a self-reminder.

        Returns: (result, score, reason)
        """
        score = 0
        reasons = []

        sender = (email.sender_email or "").lower()
        recipients = [r.lower() for r in (email.to_emails or [])]

        # Check if email is to self
        if sender == self.user_email and self.user_email in recipients:
            score += 100
            reasons.append("email to self")

        # Check subject prefixes
        subject_lower = (email.subject or "").lower()
        for prefix in self.SELF_REMINDER_SUBJECT_PREFIXES:
            if subject_lower.startswith(prefix):
                score += 50
                reasons.append(f"subject starts with '{prefix}'")
                break

        # Check subject contains reminder
        if "reminder" in subject_lower and score < 100:
            score += 20
            reasons.append("subject contains 'reminder'")

        # Check body phrases
        body_lower = (email.body_text or "").lower()
        for phrase in self.SELF_REMINDER_BODY_PHRASES:
            if phrase in body_lower:
                score += 30
                reasons.append(f"body contains '{phrase}'")
                break

        # Determine result
        if score >= 50:
            return DetectionResult.DETECTED, score, "; ".join(reasons)
        elif score >= 30:
            return DetectionResult.AMBIGUOUS, score, "; ".join(reasons)
        else:
            return DetectionResult.SKIPPED, score, "no self-reminder signals"

    def detect_request_received(self, email: EmailCache) -> tuple[DetectionResult, int, str]:
        """
        Detect if email contains a request for Dave.

        Returns: (result, score, reason)
        """
        score = 0
        reasons = []

        body = email.body_text or ""
        subject = email.subject or ""
        combined = f"{subject}\n{body}"

        # Check request patterns
        for pattern, points in self.REQUEST_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                score += points
                reasons.append(f"pattern: {pattern[:30]}")

        # Check directive patterns
        for pattern, points in self.DIRECTIVE_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                score += points
                reasons.append("directive verb")

        # Check for deadline language (bonus)
        for pattern, _ in self.DEADLINE_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                score += 15
                reasons.append("has deadline")
                break

        # VIP sender boost
        sender = (email.sender_email or "").lower()
        if sender in self.vip_contacts:
            score += 15
            reasons.append("VIP sender")

        # CC penalty (Dave is CC'd, not TO)
        recipients = [r.lower() for r in (email.to_emails or [])]
        cc_recipients = [r.lower() for r in (email.cc_emails or [])]
        if self.user_email in cc_recipients and self.user_email not in recipients:
            score -= 10
            reasons.append("CC'd not TO")

        # Multiple recipients penalty
        total_recipients = len(recipients) + len(cc_recipients)
        if total_recipients > 5:
            score -= 20
            reasons.append(f"{total_recipients} recipients")

        # Apply negative patterns
        for pattern, points in self.REQUEST_NEGATIVE_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                score += points  # points are negative
                reasons.append(f"negative: {pattern[:20]}")

        # Determine result
        if score >= 60:
            return DetectionResult.DETECTED, score, "; ".join(reasons)
        elif score >= 30:
            return DetectionResult.AMBIGUOUS, score, "; ".join(reasons)
        else:
            return DetectionResult.SKIPPED, score, "insufficient request signals"

    def detect_commitment_made(self, email: EmailCache) -> tuple[DetectionResult, int, str]:
        """
        Detect if Dave made a commitment in a sent email.

        Returns: (result, score, reason)
        """
        score = 0
        reasons = []
        is_soft = False
        is_social = False

        body = email.body_text or ""

        # Check commitment patterns
        for pattern, points in self.COMMITMENT_PATTERNS:
            if re.search(pattern, body, re.IGNORECASE):
                score += points
                reasons.append(f"commitment: {pattern[:30]}")

        # Check soft commitment patterns
        for pattern, points in self.SOFT_COMMITMENT_PATTERNS:
            if re.search(pattern, body, re.IGNORECASE):
                score += points
                reasons.append(f"soft commitment: {pattern[:30]}")
                is_soft = True

        # Check social patterns
        for pattern, points in self.SOCIAL_PATTERNS:
            if re.search(pattern, body, re.IGNORECASE):
                score += points
                reasons.append(f"social: {pattern[:30]}")
                is_social = True

        # Check for deadline language (bonus)
        for pattern, _ in self.DEADLINE_PATTERNS:
            if re.search(pattern, body, re.IGNORECASE):
                score += 15
                reasons.append("has deadline")
                break

        # VIP recipient boost
        recipients = [r.lower() for r in (email.to_emails or [])]
        if any(r in self.vip_contacts for r in recipients):
            score += 15
            reasons.append("VIP recipient")

        # Apply negative patterns
        for pattern, points in self.COMMITMENT_NEGATIVE_PATTERNS:
            if re.search(pattern, body, re.IGNORECASE):
                score += points  # points are negative
                reasons.append(f"negative: {pattern[:20]}")

        # Determine result
        if score >= 50:
            result = DetectionResult.DETECTED
        elif score >= 25:
            result = DetectionResult.AMBIGUOUS
        else:
            result = DetectionResult.SKIPPED

        # Return with soft/social flag in reasons
        if is_soft:
            reasons.append("SOFT_COMMITMENT")
        if is_social:
            reasons.append("SOCIAL_PLEASANTRY")

        return result, score, "; ".join(reasons)

    def extract_deadline(self, text: str, reference_date: Optional[date] = None) -> tuple[Optional[date], Optional[str]]:
        """
        Extract deadline from text.

        Args:
            text: Text to search for deadline patterns
            reference_date: Date to use as reference for relative dates (e.g., "tomorrow", "this Friday").
                           If None, uses today's date. For historical emails, pass the email's received date.

        Returns: (due_date, original_text)
        """
        text_lower = text.lower()
        today = reference_date or date.today()

        for pattern, pattern_type in self.DEADLINE_PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if not match:
                continue

            original_text = match.group(0)

            if pattern_type == "today":
                return today, original_text

            elif pattern_type == "tomorrow":
                return today + timedelta(days=1), original_text

            elif pattern_type == "asap" or pattern_type == "urgent":
                return today + timedelta(days=1), original_text

            elif pattern_type == "eod":
                return today, original_text

            elif pattern_type == "weekday":
                weekday_name = match.group(1).lower()
                weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                target_weekday = weekdays.index(weekday_name)
                current_weekday = today.weekday()
                days_ahead = target_weekday - current_weekday
                if days_ahead <= 0:
                    days_ahead += 7
                return today + timedelta(days=days_ahead), original_text

            elif pattern_type == "relative_week":
                modifier = match.group(1).lower()
                unit = match.group(2).lower()

                if unit == "week":
                    # This week = this Friday, next week = next Friday
                    days_to_friday = (4 - today.weekday()) % 7
                    if modifier == "next":
                        days_to_friday += 7
                    return today + timedelta(days=days_to_friday), original_text
                else:
                    # This/next specific day
                    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]
                    if unit in weekdays:
                        target_weekday = weekdays.index(unit)
                        current_weekday = today.weekday()
                        days_ahead = target_weekday - current_weekday
                        if modifier == "this":
                            if days_ahead < 0:
                                days_ahead += 7
                        else:  # next
                            if days_ahead <= 0:
                                days_ahead += 7
                            else:
                                days_ahead += 7
                        return today + timedelta(days=days_ahead), original_text

            elif pattern_type == "within":
                amount = int(match.group(1))
                unit = match.group(2).lower()
                if "day" in unit:
                    return today + timedelta(days=amount), original_text
                elif "week" in unit:
                    return today + timedelta(weeks=amount), original_text
                elif "hour" in unit:
                    return today + timedelta(days=1), original_text

        return None, None

    def determine_priority(
        self,
        email: EmailCache,
        category: TodoCategory,
        due_date: Optional[date],
        detection_reason: str
    ) -> TodoPriority:
        """Determine priority based on signals."""
        text = f"{email.subject or ''} {email.body_text or ''}".lower()
        today = date.today()

        # Check for soft commitment or social pleasantry
        if "SOFT_COMMITMENT" in detection_reason or "SOCIAL_PLEASANTRY" in detection_reason:
            return TodoPriority.LOW

        # Check urgent keywords
        for keyword in self.URGENT_KEYWORDS:
            if keyword in text:
                return TodoPriority.URGENT

        # Check deadline proximity
        if due_date:
            days_until = (due_date - today).days
            if days_until <= 1:
                return TodoPriority.URGENT
            elif days_until <= 7:
                return TodoPriority.HIGH

        # Check high priority keywords
        for keyword in self.HIGH_PRIORITY_KEYWORDS:
            if keyword in text:
                return TodoPriority.HIGH

        # Check low priority keywords
        for keyword in self.LOW_PRIORITY_KEYWORDS:
            if keyword in text:
                return TodoPriority.LOW

        # CC'd emails get lower priority
        if "CC'd not TO" in detection_reason:
            return TodoPriority.LOW

        # VIP sender gets boost to HIGH (if not already urgent)
        if "VIP sender" in detection_reason or "VIP recipient" in detection_reason:
            return TodoPriority.HIGH

        return TodoPriority.NORMAL

    def extract_title(self, email: EmailCache, category: TodoCategory) -> str:
        """Extract a concise title for the todo item."""
        subject = email.subject or "No subject"

        # Clean up subject
        subject = re.sub(r"^(re:|fwd?:|fw:)\s*", "", subject, flags=re.IGNORECASE).strip()

        # Truncate if too long
        if len(subject) > 100:
            subject = subject[:97] + "..."

        # Add category context if needed
        if category == TodoCategory.SELF_REMINDER:
            if not any(kw in subject.lower() for kw in ["remind", "todo", "follow"]):
                return f"Self-reminder: {subject}"
        elif category == TodoCategory.COMMITMENT_MADE:
            return f"Follow through: {subject}"

        return subject

    def create_source_summary(self, email: EmailCache, category: TodoCategory) -> str:
        """Create a human-readable source summary."""
        sender = email.sender_name or email.sender_email or "Unknown"
        email_date = email.received_at or email.synced_at
        date_str = email_date.strftime("%b %d") if email_date else "Unknown date"

        if category == TodoCategory.SELF_REMINDER:
            return f"Self-reminder, {date_str}"
        elif category == TodoCategory.REQUEST_RECEIVED:
            return f"Request from {sender}, {date_str}"
        elif category == TodoCategory.COMMITMENT_MADE:
            recipients = email.to_emails or []
            recipient = recipients[0] if recipients else "Unknown"
            # Get name if possible
            return f"Commitment to {recipient}, {date_str}"

        return f"From {sender}, {date_str}"

    async def process_email(self, email: EmailCache) -> Optional[TodoCandidate]:
        """
        Process a single email and return a todo candidate if detected.

        Returns: TodoCandidate or None
        """
        # Check if should skip
        should_skip, skip_reason = self.should_skip_email(email)
        if should_skip:
            logger.debug(f"Skipping email {email.gmail_id}: {skip_reason}")
            return None

        sender = (email.sender_email or "").lower()

        # Determine email type and run appropriate detection
        if sender == self.user_email:
            # Email from Dave
            recipients = [r.lower() for r in (email.to_emails or [])]

            if self.user_email in recipients:
                # Dave to Dave = self-reminder
                result, score, reason = self.detect_self_reminder(email)
                if result == DetectionResult.DETECTED:
                    category = TodoCategory.SELF_REMINDER
                else:
                    return None
            else:
                # Dave to others = commitment check
                result, score, reason = self.detect_commitment_made(email)
                if result == DetectionResult.DETECTED:
                    category = TodoCategory.COMMITMENT_MADE
                elif result == DetectionResult.AMBIGUOUS:
                    # For now, treat ambiguous as skip (can add AI later)
                    logger.debug(f"Ambiguous commitment in {email.gmail_id}: {reason}")
                    return None
                else:
                    return None
        else:
            # Email from others = request check
            result, score, reason = self.detect_request_received(email)
            if result == DetectionResult.DETECTED:
                category = TodoCategory.REQUEST_RECEIVED
            elif result == DetectionResult.AMBIGUOUS:
                # For now, treat ambiguous as skip (can add AI later)
                logger.debug(f"Ambiguous request in {email.gmail_id}: {reason}")
                return None
            else:
                return None

        # Extract deadline using email's received date as reference for relative dates
        text = f"{email.subject or ''} {email.body_text or ''}"
        email_date = email.received_at.date() if email.received_at else None
        due_date, deadline_text = self.extract_deadline(text, reference_date=email_date)

        # Determine priority based on current date (not email date)
        priority = self.determine_priority(email, category, due_date, reason)

        # Create candidate
        return TodoCandidate(
            title=self.extract_title(email, category),
            description=email.body_text[:500] if email.body_text else None,
            category=category,
            priority=priority,
            due_date=due_date,
            source_type="email",
            source_id=email.gmail_id,
            source_summary=self.create_source_summary(email, category),
            contact_name=email.sender_name if category == TodoCategory.REQUEST_RECEIVED else None,
            contact_email=email.sender_email if category == TodoCategory.REQUEST_RECEIVED else (
                email.to_emails[0] if email.to_emails and category == TodoCategory.COMMITMENT_MADE else None
            ),
            detection_confidence=min(score / 100.0, 1.0),
            detected_deadline_text=deadline_text,
        )

    async def scan_emails(
        self,
        db: AsyncSession,
        user_id: int,
        since_date: Optional[date] = None,
        limit: Optional[int] = None
    ) -> ScanProgress:
        """
        Scan emails for todo items.

        Args:
            db: Database session
            user_id: User ID
            since_date: Only scan emails after this date (default: 6 months ago)
            limit: Maximum emails to scan

        Returns: ScanProgress with results
        """
        progress = ScanProgress()

        # Default to 6 months ago
        if since_date is None:
            since_date = date.today() - timedelta(days=180)

        # Get existing todo source IDs to check for duplicates
        existing_query = select(TodoItem.source_id).where(
            and_(
                TodoItem.user_id == user_id,
                TodoItem.source_type == "email"
            )
        )
        result = await db.execute(existing_query)
        existing_source_ids = {row[0] for row in result.fetchall()}

        # Query emails (single-user system, no user_id filter needed)
        query = select(EmailCache).where(
            EmailCache.received_at >= datetime.combine(since_date, datetime.min.time())
        ).order_by(EmailCache.received_at.desc())

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        emails = result.scalars().all()
        progress.total_emails = len(emails)

        logger.info(f"Scanning {progress.total_emails} emails for todos since {since_date}")

        for email in emails:
            progress.scanned += 1

            try:
                # Check for duplicate
                if email.gmail_id in existing_source_ids:
                    progress.duplicates_skipped += 1
                    continue

                # Process email
                candidate = await self.process_email(email)

                if candidate is None:
                    progress.filtered_out += 1
                    continue

                # Create todo item
                todo = TodoItem(
                    user_id=user_id,
                    title=candidate.title,
                    description=candidate.description,
                    category=candidate.category,
                    priority=candidate.priority,
                    status=TodoStatus.PENDING,
                    due_date=candidate.due_date,
                    source_type=candidate.source_type,
                    source_id=candidate.source_id,
                    source_summary=candidate.source_summary,
                    contact_name=candidate.contact_name,
                    contact_email=candidate.contact_email,
                    detection_confidence=candidate.detection_confidence,
                    detected_deadline_text=candidate.detected_deadline_text,
                )
                db.add(todo)

                progress.todos_created += 1
                progress.by_category[candidate.category.value] += 1

                # Add to existing set to prevent duplicates within batch
                existing_source_ids.add(email.gmail_id)

                # Commit every 50 items
                if progress.todos_created % 50 == 0:
                    await db.commit()
                    logger.info(f"Progress: {progress.scanned}/{progress.total_emails} scanned, {progress.todos_created} todos created")

            except Exception as e:
                logger.error(f"Error processing email {email.gmail_id}: {e}")
                progress.errors += 1

        # Final commit
        await db.commit()

        logger.info(
            f"Scan complete: {progress.todos_created} todos created, "
            f"{progress.duplicates_skipped} duplicates, {progress.filtered_out} filtered, "
            f"{progress.errors} errors"
        )

        return progress


async def load_vip_contacts(db: AsyncSession, user_id: int) -> set[str]:
    """Load VIP contact emails from behavioral analysis."""
    # Query indexed_entities for VIP insights
    from sage.services.data_layer.models import IndexedEntityModel

    query = select(IndexedEntityModel).where(
        and_(
            IndexedEntityModel.entity_type == "insight",
            IndexedEntityModel.structured["insight_type"].astext == "vip_contacts"
        )
    )

    result = await db.execute(query)
    entity = result.scalar_one_or_none()

    if entity and entity.analyzed:
        vip_list = entity.analyzed.get("vip_emails", [])
        return set(vip_list)

    return set()
