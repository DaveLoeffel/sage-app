"""Follow-up pattern detector for identifying threads awaiting response."""

import re
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from collections import defaultdict

from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from sage.models.email import EmailCache
from sage.models.followup import Followup, FollowupStatus, FollowupPriority
from sage.models.contact import Contact
from sage.models.user import User


logger = logging.getLogger(__name__)


@dataclass
class EmailClassification:
    """Classification result for whether an email expects a response."""

    expects_response: bool
    confidence: float  # 0.0 to 1.0
    method: str  # "heuristic" or "ai"
    heuristic_score: int
    reasons: list[str] = field(default_factory=list)


@dataclass
class WaitingThread:
    """A thread where user is waiting for a response."""

    thread_id: str
    last_sent_gmail_id: str
    last_sent_at: datetime
    subject: str
    recipient_email: str
    recipient_name: str | None
    body_preview: str
    classification: EmailClassification
    business_days_waiting: int
    suggested_action: str  # "draft_followup", "send_followup", "call"
    contact_phone: str | None = None


@dataclass
class FollowupDetectionResult:
    """Results from follow-up pattern detection."""

    user_email: str
    detection_timestamp: datetime
    threads_analyzed: int
    waiting_threads: list[WaitingThread] = field(default_factory=list)
    followups_created: int = 0
    contacts_created: int = 0

    # Classification stats
    heuristic_classifications: int = 0
    ai_classifications: int = 0


class FollowupPatternDetector:
    """
    Detect email threads where user is waiting for a response.

    Uses hybrid heuristics + AI to classify if sent emails expect responses,
    then applies business day timing rules:
    - 1 business day: draft follow-up email
    - 3 business days: send additional follow-up
    - Every 2 business days after: escalate

    Integrates with Contact model for phone numbers on daily review.
    """

    # Heuristic patterns for "expects response"
    EXPECTS_RESPONSE_PATTERNS = {
        # Questions (+20 each)
        "question_mark": (r"\?", 20),
        "ends_with_question": (r"\?\s*$", 15),

        # Request phrases (+25 each)
        "let_me_know": (r"\blet me know\b", 25),
        "please_advise": (r"\bplease advise\b", 25),
        "what_do_you_think": (r"\bwhat do you think\b", 25),
        "your_thoughts": (r"\byour thoughts\b", 20),
        "feedback": (r"\b(need|want|appreciate|await).{0,20}feedback\b", 20),

        # Action requests (+20 each)
        "can_you": (r"\bcan you\b", 20),
        "could_you": (r"\bcould you\b", 20),
        "would_you": (r"\bwould you\b", 15),
        "need_you_to": (r"\bneed you to\b", 25),
        "please_send": (r"\bplease (send|provide|share|confirm)\b", 20),

        # Deadline mentions (+15)
        "deadline": (r"\b(by|before|due|deadline).{0,15}(monday|tuesday|wednesday|thursday|friday|tomorrow|eod|eow|asap)\b", 15),

        # Waiting language (+15)
        "waiting": (r"\b(waiting|await|looking forward).{0,10}(response|reply|hear)\b", 15),
    }

    # Patterns indicating NO response expected (-points)
    NO_RESPONSE_PATTERNS = {
        # Closing phrases (-40 each) - match at start of message
        "thanks_closing": (r"^thanks[.!,]?\s*$", -40),
        "got_it": (r"^got it[.!,]?(\s|$)", -40),
        "sounds_good": (r"^sounds good[.!,]?(\s|$)", -40),
        "perfect": (r"^perfect[.!,]?\s*$", -40),
        "will_do": (r"^will do[.!,]?(\s|$)", -40),
        "acknowledged": (r"^(ok|okay|sure|great|done|confirmed)[.!,]?(\s|$)", -35),

        # Combined closing phrases
        "compound_closing": (r"^(got it|sounds good|perfect|will do|ok|okay)[,.]?\s*(thanks|thank you)?[.!]?\s*$", -45),

        # FYI patterns (-30)
        "fyi": (r"\bfyi\b|\bfor your (information|reference|records)\b", -30),

        # Confirmation only (-25)
        "just_confirming": (r"^(just )?(confirming|confirmed|acknowledged)", -25),

        # Forward without content (-35)
        "empty_forward": (r"^[-]+\s*forwarded message", -35),

        # "See attached" patterns - sending documents, no response expected (-40)
        "see_attached": (r"\bsee\s+(\w+\s+)?attached\b", -40),
        "attached_is": (r"\battached (is|are)\b", -40),
        "please_find_attached": (r"\bplease (find|see)\s+(\w+\s+)?attached\b", -40),
        "here_is_the": (r"^here (is|are) the\b", -35),
    }

    # Thresholds
    EXPECTS_RESPONSE_THRESHOLD = 60  # Score > 60 = expects response
    NO_RESPONSE_THRESHOLD = 30  # Score < 30 = no response expected
    MIN_BODY_LENGTH_FOR_RESPONSE = 20  # Very short = likely closing

    def __init__(self, user_email: str):
        """
        Initialize detector for a specific user.

        Args:
            user_email: The user's email address
        """
        self.user_email = user_email.lower()
        self.user_email_variants = {
            self.user_email,
            f"<{self.user_email}>",
        }

    def _is_user_email(self, email: str) -> bool:
        """Check if an email address belongs to the user."""
        return email.lower() in self.user_email_variants

    def classify_expects_response(
        self, subject: str, body: str, use_ai: bool = False
    ) -> EmailClassification:
        """
        Classify whether an email expects a response.

        Uses heuristics first, then AI for ambiguous cases.

        Args:
            subject: Email subject
            body: Email body text
            use_ai: Whether to use AI for ambiguous cases

        Returns:
            EmailClassification with result and confidence
        """
        # Clean body (remove signature, quotes)
        clean_body = self._clean_body_for_classification(body)
        text = f"{subject} {clean_body}".lower()

        score = 50  # Start neutral
        reasons = []

        # Check for very short emails (likely closing)
        if len(clean_body.strip()) < self.MIN_BODY_LENGTH_FOR_RESPONSE:
            score -= 20
            reasons.append("Very short email")

        # Apply "expects response" patterns
        for name, (pattern, points) in self.EXPECTS_RESPONSE_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                score += points
                reasons.append(f"+{points}: {name}")

        # Apply "no response" patterns
        for name, (pattern, points) in self.NO_RESPONSE_PATTERNS.items():
            if re.search(pattern, clean_body.strip(), re.IGNORECASE | re.MULTILINE):
                score += points  # points are negative
                reasons.append(f"{points}: {name}")

        # Determine classification
        if score >= self.EXPECTS_RESPONSE_THRESHOLD:
            return EmailClassification(
                expects_response=True,
                confidence=min(1.0, score / 100),
                method="heuristic",
                heuristic_score=score,
                reasons=reasons,
            )
        elif score <= self.NO_RESPONSE_THRESHOLD:
            return EmailClassification(
                expects_response=False,
                confidence=min(1.0, (100 - score) / 100),
                method="heuristic",
                heuristic_score=score,
                reasons=reasons,
            )
        else:
            # Ambiguous - use AI if enabled
            if use_ai:
                return self._classify_with_ai(subject, clean_body, score, reasons)
            else:
                # Default to expects response for ambiguous (safer)
                return EmailClassification(
                    expects_response=True,
                    confidence=0.5,
                    method="heuristic_ambiguous",
                    heuristic_score=score,
                    reasons=reasons + ["Ambiguous - defaulting to expects response"],
                )

    def _classify_with_ai(
        self, subject: str, body: str, heuristic_score: int, heuristic_reasons: list[str]
    ) -> EmailClassification:
        """Use AI to classify ambiguous emails."""
        # TODO: Implement AI classification with Claude
        # For now, return ambiguous result
        logger.info(f"AI classification needed for: {subject[:50]}")
        return EmailClassification(
            expects_response=True,  # Default to true for safety
            confidence=0.6,
            method="ai_pending",
            heuristic_score=heuristic_score,
            reasons=heuristic_reasons + ["AI classification pending"],
        )

    async def classify_with_ai_batch(
        self, session: AsyncSession, emails: list[tuple[str, str, str]]
    ) -> dict[str, EmailClassification]:
        """
        Batch classify emails using AI.

        Args:
            session: Database session
            emails: List of (gmail_id, subject, body) tuples

        Returns:
            Dict mapping gmail_id to classification
        """
        from sage.core.claude_agent import get_claude_agent

        results = {}
        agent = await get_claude_agent()

        for gmail_id, subject, body in emails:
            try:
                # Use Claude to classify
                prompt = f"""Analyze this email and determine if the sender expects a response from the recipient.

Subject: {subject}
Body: {body[:1000]}

Consider:
1. Is there a direct question being asked?
2. Is there a request for action or information?
3. Is this just a closing message (Thanks, Got it, etc.)?
4. Is this an FYI or informational message?

Respond with ONLY one of:
- EXPECTS_RESPONSE: The sender is waiting for a reply
- NO_RESPONSE_NEEDED: This is a closing, acknowledgment, or FYI message"""

                response = await agent.client.messages.create(
                    model="claude-3-haiku-20240307",  # Fast, cheap model
                    max_tokens=50,
                    messages=[{"role": "user", "content": prompt}],
                )

                answer = response.content[0].text.strip().upper()
                expects = "EXPECTS_RESPONSE" in answer

                results[gmail_id] = EmailClassification(
                    expects_response=expects,
                    confidence=0.85,
                    method="ai",
                    heuristic_score=50,
                    reasons=[f"AI classified as {'expects' if expects else 'no'} response"],
                )

            except Exception as e:
                logger.error(f"AI classification failed for {gmail_id}: {e}")
                # Fall back to expecting response
                results[gmail_id] = EmailClassification(
                    expects_response=True,
                    confidence=0.5,
                    method="ai_failed",
                    heuristic_score=50,
                    reasons=[f"AI classification failed: {str(e)}"],
                )

        return results

    def _clean_body_for_classification(self, body: str) -> str:
        """Remove signature and quoted content from body."""
        lines = []
        for line in body.split("\n"):
            # Skip quoted lines
            if line.strip().startswith(">"):
                continue
            # Skip "On ... wrote:" lines
            if re.match(r"^On .+ wrote:$", line.strip()):
                break
            # Stop at signature markers
            if line.strip() in ["--", "—"] or line.strip().lower().startswith("dave loeffel"):
                break
            lines.append(line)

        return "\n".join(lines)

    def calculate_business_days(self, from_date: datetime, to_date: datetime) -> int:
        """Calculate business days between two dates (excluding weekends)."""
        if from_date > to_date:
            return 0

        business_days = 0
        current = from_date

        while current <= to_date:
            # Monday = 0, Sunday = 6
            if current.weekday() < 5:  # Monday to Friday
                business_days += 1
            current += timedelta(days=1)

        return business_days

    def get_suggested_action(self, business_days_waiting: int) -> str:
        """
        Get suggested action based on business days waiting.

        - 1 day: draft follow-up
        - 3 days: send additional follow-up
        - 5+ days: call + follow-up
        """
        if business_days_waiting <= 1:
            return "draft_followup"
        elif business_days_waiting <= 3:
            return "send_followup"
        else:
            return "call_and_followup"

    async def detect(
        self,
        session: AsyncSession,
        months_back: int = 6,
        use_ai: bool = True,
        progress_callback=None,
    ) -> FollowupDetectionResult:
        """
        Detect threads where user is waiting for a response.

        Args:
            session: Database session
            months_back: How many months of history to analyze
            use_ai: Whether to use AI for ambiguous classifications
            progress_callback: Optional callback for progress updates

        Returns:
            FollowupDetectionResult with waiting threads and stats
        """
        result = FollowupDetectionResult(
            user_email=self.user_email,
            detection_timestamp=datetime.utcnow(),
            threads_analyzed=0,
        )

        cutoff_date = datetime.utcnow() - timedelta(days=months_back * 30)

        if progress_callback:
            progress_callback("Loading threads", 0)

        # Step 1: Find all threads with activity in the time window
        logger.info(f"Loading threads from last {months_back} months...")
        threads = await self._load_threads_with_activity(session, cutoff_date)
        result.threads_analyzed = len(threads)

        if progress_callback:
            progress_callback("Analyzing threads", 20)

        # Step 2: Find threads where user sent the last message
        logger.info("Finding threads awaiting response...")
        waiting_candidates = []

        for i, (thread_id, emails) in enumerate(threads.items()):
            if progress_callback and i % 500 == 0:
                pct = 20 + int(40 * i / len(threads))
                progress_callback("Analyzing threads", pct)

            # Sort by time
            emails = sorted(emails, key=lambda e: e.received_at)

            # Get the last email in the thread
            last_email = emails[-1]

            # Check if user sent the last message
            if not self._is_user_email(last_email.sender_email):
                continue  # Someone else sent last - no follow-up needed

            # Get the recipient (the person we're waiting on)
            recipient_email = None
            recipient_name = None

            if last_email.to_emails:
                recipient_email = last_email.to_emails[0]
                # Try to find name from earlier emails
                for e in reversed(emails[:-1]):
                    if e.sender_email.lower() == recipient_email.lower():
                        recipient_name = e.sender_name
                        break

            if not recipient_email:
                continue

            # Skip if recipient is also the user (self-emails)
            if self._is_user_email(recipient_email):
                continue

            # Skip calendar-related emails
            subject_lower = (last_email.subject or "").lower()
            if any(x in subject_lower for x in [
                "invitation:", "synced invitation:", "accepted:", "declined:",
                "updated invitation:", "canceled:", "cancelled:",
            ]):
                continue

            waiting_candidates.append({
                "thread_id": thread_id,
                "last_email": last_email,
                "recipient_email": recipient_email,
                "recipient_name": recipient_name,
            })

        if progress_callback:
            progress_callback("Classifying emails", 60)

        # Step 3: Classify each candidate
        logger.info(f"Classifying {len(waiting_candidates)} candidate threads...")

        # First pass: heuristics
        ambiguous_for_ai = []

        for candidate in waiting_candidates:
            email = candidate["last_email"]
            classification = self.classify_expects_response(
                email.subject or "",
                email.body_text or "",
                use_ai=False,  # First pass without AI
            )

            candidate["classification"] = classification

            if classification.method == "heuristic_ambiguous" and use_ai:
                ambiguous_for_ai.append((
                    email.gmail_id,
                    email.subject or "",
                    email.body_text or "",
                ))
                result.ai_classifications += 1
            else:
                result.heuristic_classifications += 1

        # Second pass: AI for ambiguous cases
        if ambiguous_for_ai and use_ai:
            if progress_callback:
                progress_callback("AI classification", 70)

            logger.info(f"Running AI classification on {len(ambiguous_for_ai)} ambiguous emails...")
            ai_results = await self.classify_with_ai_batch(session, ambiguous_for_ai)

            # Update classifications
            for candidate in waiting_candidates:
                gmail_id = candidate["last_email"].gmail_id
                if gmail_id in ai_results:
                    candidate["classification"] = ai_results[gmail_id]

        if progress_callback:
            progress_callback("Building results", 85)

        # Step 4: Build waiting threads list
        now = datetime.utcnow()

        for candidate in waiting_candidates:
            classification = candidate["classification"]

            if not classification.expects_response:
                continue

            email = candidate["last_email"]
            business_days = self.calculate_business_days(email.received_at, now)

            # Only include if at least 1 business day has passed
            if business_days < 1:
                continue

            # Skip if too old (>60 business days = ~3 months)
            # These are likely stale and not actionable
            if business_days > 60:
                continue

            waiting_thread = WaitingThread(
                thread_id=candidate["thread_id"],
                last_sent_gmail_id=email.gmail_id,
                last_sent_at=email.received_at,
                subject=email.subject or "(no subject)",
                recipient_email=candidate["recipient_email"],
                recipient_name=candidate["recipient_name"],
                body_preview=(email.body_text or "")[:200],
                classification=classification,
                business_days_waiting=business_days,
                suggested_action=self.get_suggested_action(business_days),
            )

            result.waiting_threads.append(waiting_thread)

        # Sort by business days waiting (most urgent first)
        result.waiting_threads.sort(key=lambda t: t.business_days_waiting, reverse=True)

        if progress_callback:
            progress_callback("Complete", 100)

        logger.info(
            f"Detection complete: {result.threads_analyzed} threads analyzed, "
            f"{len(result.waiting_threads)} waiting for response"
        )

        return result

    async def _load_threads_with_activity(
        self, session: AsyncSession, cutoff_date: datetime
    ) -> dict[str, list[EmailCache]]:
        """Load all threads with activity since cutoff date."""
        result = await session.execute(
            select(EmailCache)
            .where(EmailCache.received_at >= cutoff_date)
            .order_by(EmailCache.thread_id, EmailCache.received_at)
        )
        emails = result.scalars().all()

        threads: dict[str, list[EmailCache]] = defaultdict(list)
        for email in emails:
            threads[email.thread_id].append(email)

        return threads

    async def seed_followup_tracker(
        self,
        session: AsyncSession,
        result: FollowupDetectionResult,
        user_id: int,
        max_followups: int = 100,
    ) -> tuple[int, int]:
        """
        Seed the Followup tracker with detected waiting threads.

        Args:
            session: Database session
            result: Detection result
            user_id: User ID to associate followups with
            max_followups: Maximum number of followups to create

        Returns:
            Tuple of (followups_created, contacts_created)
        """
        followups_created = 0
        contacts_created = 0

        # Track contacts created in this batch to avoid duplicates
        created_emails = set()

        for thread in result.waiting_threads[:max_followups]:
            # Check if followup already exists for this thread
            existing = await session.execute(
                select(Followup).where(
                    Followup.thread_id == thread.thread_id,
                    Followup.status.in_([FollowupStatus.PENDING, FollowupStatus.REMINDED]),
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Clean the email address
            clean_email = self._extract_email(thread.recipient_email)

            # Get or create contact (checking batch set to avoid duplicates)
            if clean_email not in created_emails:
                contact = await self._get_or_create_contact(
                    session, thread.recipient_email, thread.recipient_name
                )
                if contact and not contact.id:
                    contacts_created += 1
                    created_emails.add(clean_email)

            # Determine priority based on days waiting
            if thread.business_days_waiting >= 5:
                priority = FollowupPriority.HIGH
            elif thread.business_days_waiting >= 3:
                priority = FollowupPriority.NORMAL
            else:
                priority = FollowupPriority.LOW

            # Calculate due date (1 business day from now for pending)
            due_date = self._add_business_days(datetime.utcnow(), 1)

            # Create followup
            followup = Followup(
                user_id=user_id,
                gmail_id=thread.last_sent_gmail_id,
                thread_id=thread.thread_id,
                subject=thread.subject,
                contact_email=clean_email,
                contact_name=thread.recipient_name,
                status=FollowupStatus.PENDING,
                priority=priority,
                due_date=due_date,
                notes=f"Auto-detected: {thread.business_days_waiting} business days waiting. "
                      f"Action: {thread.suggested_action}",
                ai_summary=f"Classification: {thread.classification.method} "
                          f"(confidence: {thread.classification.confidence:.0%})",
            )

            session.add(followup)
            followups_created += 1

        await session.flush()
        logger.info(f"Created {followups_created} followups, {contacts_created} contacts")

        return followups_created, contacts_created

    def _extract_email(self, email_string: str) -> str:
        """Extract just the email address from 'Name <email>' format."""
        email_lower = email_string.lower().strip()
        if "<" in email_lower:
            start = email_lower.find("<")
            end = email_lower.find(">", start)
            if end == -1:
                end = len(email_lower)
            email_lower = email_lower[start + 1:end].strip()
        return email_lower.strip("<>")

    async def _get_or_create_contact(
        self, session: AsyncSession, email: str, name: str | None
    ) -> Contact | None:
        """Get existing contact or create a new one."""
        email_lower = self._extract_email(email)

        result = await session.execute(
            select(Contact).where(Contact.email == email_lower)
        )
        contact = result.scalar_one_or_none()

        if not contact:
            contact = Contact(
                email=email_lower,
                name=name,
            )
            session.add(contact)

        return contact

    def _add_business_days(self, start_date: datetime, days: int) -> datetime:
        """Add business days to a date."""
        current = start_date
        added = 0

        while added < days:
            current += timedelta(days=1)
            if current.weekday() < 5:  # Monday to Friday
                added += 1

        return current

    async def get_daily_review_items(
        self, session: AsyncSession, user_id: int
    ) -> list[dict[str, Any]]:
        """
        Get followup items for daily review with phone numbers.

        Returns items sorted by urgency with contact phone numbers.
        """
        # Get pending/reminded followups
        result = await session.execute(
            select(Followup)
            .where(
                Followup.user_id == user_id,
                Followup.status.in_([FollowupStatus.PENDING, FollowupStatus.REMINDED]),
            )
            .order_by(Followup.due_date)
        )
        followups = result.scalars().all()

        items = []
        for followup in followups:
            # Get contact phone
            contact_result = await session.execute(
                select(Contact).where(Contact.email == followup.contact_email.lower())
            )
            contact = contact_result.scalar_one_or_none()

            item = {
                "id": followup.id,
                "subject": followup.subject,
                "contact_email": followup.contact_email,
                "contact_name": followup.contact_name,
                "contact_phone": contact.phone if contact else None,
                "status": followup.status.value,
                "priority": followup.priority.value,
                "due_date": followup.due_date.isoformat(),
                "days_overdue": self.calculate_business_days(followup.due_date, datetime.utcnow()),
                "suggested_action": self.get_suggested_action(
                    self.calculate_business_days(followup.created_at, datetime.utcnow())
                ),
                "notes": followup.notes,
            }
            items.append(item)

        return items
