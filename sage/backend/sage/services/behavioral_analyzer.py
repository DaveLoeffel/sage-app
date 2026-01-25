"""Behavioral analyzer service for learning from email patterns."""

import re
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, and_, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from sage.models.email import EmailCache
from sage.services.data_layer.models.indexed_entity import IndexedEntityModel


logger = logging.getLogger(__name__)


@dataclass
class SenderStats:
    """Statistics for a single sender."""

    email: str
    name: str | None = None
    total_received: int = 0
    total_responded: int = 0
    avg_response_time_hours: float | None = None
    response_times_hours: list[float] = field(default_factory=list)
    labels_used: list[str] = field(default_factory=list)

    @property
    def response_rate(self) -> float:
        """Calculate response rate as percentage."""
        if self.total_received == 0:
            return 0.0
        return (self.total_responded / self.total_received) * 100

    def calculate_avg_response_time(self) -> None:
        """Calculate average response time from collected times."""
        if self.response_times_hours:
            self.avg_response_time_hours = sum(self.response_times_hours) / len(self.response_times_hours)


@dataclass
class BehavioralInsights:
    """Container for all behavioral analysis results."""

    user_email: str
    analysis_timestamp: datetime

    # VIP contacts (sorted by response rate and frequency)
    vip_contacts: list[SenderStats] = field(default_factory=list)

    # Response patterns
    avg_response_time_hours: float = 0.0
    quick_response_threshold_hours: float = 4.0  # Emails responded to in < 4 hours

    # Priority keywords (words common in quickly-responded emails)
    priority_keywords: list[tuple[str, int]] = field(default_factory=list)  # (word, count)

    # Label patterns
    starred_senders: list[str] = field(default_factory=list)
    important_senders: list[str] = field(default_factory=list)

    # Summary stats
    total_threads_analyzed: int = 0
    threads_with_response: int = 0
    total_senders: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "user_email": self.user_email,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "vip_contacts": [
                {
                    "email": s.email,
                    "name": s.name,
                    "total_received": s.total_received,
                    "total_responded": s.total_responded,
                    "response_rate": s.response_rate,
                    "avg_response_time_hours": s.avg_response_time_hours,
                }
                for s in self.vip_contacts
            ],
            "avg_response_time_hours": self.avg_response_time_hours,
            "quick_response_threshold_hours": self.quick_response_threshold_hours,
            "priority_keywords": [{"word": w, "count": c} for w, c in self.priority_keywords],
            "starred_senders": self.starred_senders,
            "important_senders": self.important_senders,
            "total_threads_analyzed": self.total_threads_analyzed,
            "threads_with_response": self.threads_with_response,
            "total_senders": self.total_senders,
        }


class BehavioralAnalyzer:
    """
    Analyze email patterns to learn user behavior.

    Discovers:
    - VIP contacts (people user always responds to)
    - Response time patterns (quick vs slow responses)
    - Priority keywords (words in emails user responds quickly to)
    - Label patterns (what gets starred/labeled)
    """

    # Words to exclude from keyword analysis
    STOP_WORDS = {
        # Standard stop words
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "up", "about", "into", "through", "during",
        "before", "after", "above", "below", "between", "under", "again",
        "further", "then", "once", "here", "there", "when", "where", "why",
        "how", "all", "each", "few", "more", "most", "other", "some", "such",
        "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
        "can", "will", "just", "should", "now", "also", "like", "get", "got",
        "this", "that", "these", "those", "it", "its", "is", "are", "was",
        "were", "be", "been", "being", "have", "has", "had", "having", "do",
        "does", "did", "doing", "would", "could", "might", "must", "shall",
        "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you",
        "your", "yours", "yourself", "yourselves", "he", "him", "his",
        "himself", "she", "her", "hers", "herself", "they", "them", "their",
        "theirs", "themselves", "what", "which", "who", "whom", "if", "as",
        # Email-specific
        "hi", "hello", "thanks", "thank", "please", "regards", "best",
        "sent", "from", "subject", "re", "fwd", "fw", "email", "message",
        "wrote", "sender", "reply", "original", "forwarded",
        # Signature/contact patterns
        "cell", "phone", "office", "mobile", "fax", "tel", "ext",
        "www", "com", "net", "org", "edu", "gov", "http", "https",
        "llc", "inc", "corp", "ltd", "suite", "floor", "street", "ave",
        "confidential", "confidentiality", "privilege", "privileged",
        "disclaimer", "notice", "intended", "recipient", "authorized",
        # Common names and company words (will be personalized per user)
        "dave", "david", "loeffel", "highlands", "residential", "highlandsresidential",
        # Common business words
        "attached", "attachment", "see", "below", "above", "following",
        "information", "any", "may", "let", "know", "questions", "feel", "free",
        "forward", "contact", "reach", "call", "discuss", "time", "day",
        "week", "month", "year", "today", "tomorrow", "yesterday",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "january", "february", "march", "april", "june", "july", "august",
        "september", "october", "november", "december",
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "first", "second", "third", "last", "next", "new", "old",
        # More noise
        "place", "way", "make", "made", "take", "took", "give", "gave",
        "come", "came", "going", "goes", "went", "work", "works", "working",
        "good", "great", "nice", "well", "much", "many", "lot", "lots",
        "back", "still", "already", "yet", "even", "really", "actually",
        "think", "thought", "want", "wanted", "need", "needed", "hope",
    }

    # Minimum counts for various thresholds
    MIN_EMAILS_FOR_VIP = 3  # Need at least 3 emails to consider someone a VIP
    MIN_RESPONSE_RATE_FOR_VIP = 50  # 50% response rate to be VIP
    MIN_KEYWORD_COUNT = 5  # Keyword must appear at least 5 times

    def __init__(self, user_email: str):
        """
        Initialize analyzer for a specific user.

        Args:
            user_email: The user's email address (to identify sent vs received)
        """
        self.user_email = user_email.lower()
        # Also match variant with angle brackets
        self.user_email_variants = {
            self.user_email,
            f"<{self.user_email}>",
        }

    def _is_user_email(self, email: str) -> bool:
        """Check if an email address belongs to the user."""
        return email.lower() in self.user_email_variants

    async def analyze(self, session: AsyncSession, progress_callback=None) -> BehavioralInsights:
        """
        Run full behavioral analysis on email corpus.

        Args:
            session: Database session
            progress_callback: Optional callback for progress updates (phase, percent)

        Returns:
            BehavioralInsights with all discovered patterns
        """
        insights = BehavioralInsights(
            user_email=self.user_email,
            analysis_timestamp=datetime.utcnow(),
        )

        if progress_callback:
            progress_callback("Loading threads", 0)

        # Phase 1: Load all emails grouped by thread
        logger.info("Loading emails by thread...")
        thread_emails = await self._load_emails_by_thread(session)
        insights.total_threads_analyzed = len(thread_emails)

        if progress_callback:
            progress_callback("Analyzing response patterns", 20)

        # Phase 2: Analyze response patterns
        logger.info("Analyzing response patterns...")
        sender_stats = await self._analyze_response_patterns(thread_emails, progress_callback)
        insights.total_senders = len(sender_stats)

        if progress_callback:
            progress_callback("Building VIP list", 50)

        # Phase 3: Build VIP list
        logger.info("Building VIP contact list...")
        insights.vip_contacts = self._build_vip_list(sender_stats)

        # Calculate overall response stats
        all_response_times = []
        for stats in sender_stats.values():
            all_response_times.extend(stats.response_times_hours)
            if stats.total_responded > 0:
                insights.threads_with_response += stats.total_responded

        if all_response_times:
            insights.avg_response_time_hours = sum(all_response_times) / len(all_response_times)

        if progress_callback:
            progress_callback("Extracting keywords", 60)

        # Phase 4: Extract priority keywords from quickly-responded emails
        logger.info("Extracting priority keywords...")
        insights.priority_keywords = await self._extract_priority_keywords(
            session, thread_emails, insights.quick_response_threshold_hours
        )

        if progress_callback:
            progress_callback("Analyzing labels", 80)

        # Phase 5: Analyze label patterns
        logger.info("Analyzing label patterns...")
        starred, important = await self._analyze_label_patterns(session)
        insights.starred_senders = starred
        insights.important_senders = important

        if progress_callback:
            progress_callback("Complete", 100)

        logger.info(
            f"Analysis complete: {insights.total_threads_analyzed} threads, "
            f"{len(insights.vip_contacts)} VIP contacts, "
            f"{len(insights.priority_keywords)} priority keywords"
        )

        return insights

    async def _load_emails_by_thread(
        self, session: AsyncSession
    ) -> dict[str, list[EmailCache]]:
        """Load all emails grouped by thread_id."""
        result = await session.execute(
            select(EmailCache)
            .order_by(EmailCache.thread_id, EmailCache.received_at)
        )
        emails = result.scalars().all()

        thread_emails: dict[str, list[EmailCache]] = defaultdict(list)
        for email in emails:
            thread_emails[email.thread_id].append(email)

        return thread_emails

    async def _analyze_response_patterns(
        self,
        thread_emails: dict[str, list[EmailCache]],
        progress_callback=None,
    ) -> dict[str, SenderStats]:
        """
        Analyze response patterns from threaded emails.

        For each thread:
        1. Find emails received from external senders
        2. Check if user sent a reply after
        3. Calculate response time
        """
        sender_stats: dict[str, SenderStats] = {}

        total_threads = len(thread_emails)
        processed = 0

        for thread_id, emails in thread_emails.items():
            processed += 1
            if progress_callback and processed % 1000 == 0:
                pct = 20 + int(30 * processed / total_threads)
                progress_callback("Analyzing response patterns", pct)

            # Sort by time
            emails = sorted(emails, key=lambda e: e.received_at)

            # Find received -> sent pairs
            for i, received in enumerate(emails):
                # Skip if this is a sent email (from user)
                if self._is_user_email(received.sender_email):
                    continue

                sender = received.sender_email.lower()

                # Initialize sender stats if needed
                if sender not in sender_stats:
                    sender_stats[sender] = SenderStats(
                        email=sender,
                        name=received.sender_name,
                    )

                sender_stats[sender].total_received += 1

                # Track labels
                if received.labels:
                    for label in received.labels:
                        if label not in sender_stats[sender].labels_used:
                            sender_stats[sender].labels_used.append(label)

                # Look for user's response after this email
                for j in range(i + 1, len(emails)):
                    potential_reply = emails[j]
                    if self._is_user_email(potential_reply.sender_email):
                        # Found a reply from user
                        sender_stats[sender].total_responded += 1

                        # Calculate response time
                        response_time = potential_reply.received_at - received.received_at
                        response_hours = response_time.total_seconds() / 3600

                        # Cap at 7 days (168 hours) to avoid outliers
                        if response_hours <= 168:
                            sender_stats[sender].response_times_hours.append(response_hours)

                        break  # Only count first reply

        # Calculate averages
        for stats in sender_stats.values():
            stats.calculate_avg_response_time()

        return sender_stats

    def _build_vip_list(self, sender_stats: dict[str, SenderStats]) -> list[SenderStats]:
        """
        Build VIP contact list based on response patterns.

        VIP criteria:
        - At least MIN_EMAILS_FOR_VIP emails received
        - At least MIN_RESPONSE_RATE_FOR_VIP% response rate

        Sorted by: response rate (desc), then total responded (desc)
        """
        vips = []

        for stats in sender_stats.values():
            if (stats.total_received >= self.MIN_EMAILS_FOR_VIP and
                stats.response_rate >= self.MIN_RESPONSE_RATE_FOR_VIP):
                vips.append(stats)

        # Sort by response rate, then by total responded
        vips.sort(key=lambda s: (s.response_rate, s.total_responded), reverse=True)

        return vips

    async def _extract_priority_keywords(
        self,
        session: AsyncSession,
        thread_emails: dict[str, list[EmailCache]],
        quick_threshold_hours: float,
    ) -> list[tuple[str, int]]:
        """
        Extract keywords from emails that received quick responses.

        Looks at subject and body text of emails that user responded to
        within quick_threshold_hours.
        """
        word_counts: dict[str, int] = defaultdict(int)

        for thread_id, emails in thread_emails.items():
            emails = sorted(emails, key=lambda e: e.received_at)

            for i, received in enumerate(emails):
                # Skip sent emails
                if self._is_user_email(received.sender_email):
                    continue

                # Look for quick response
                for j in range(i + 1, len(emails)):
                    potential_reply = emails[j]
                    if self._is_user_email(potential_reply.sender_email):
                        response_time = potential_reply.received_at - received.received_at
                        response_hours = response_time.total_seconds() / 3600

                        if response_hours <= quick_threshold_hours:
                            # This email got a quick response - extract keywords
                            text = f"{received.subject or ''} {received.body_text or ''}"
                            words = self._extract_words(text)
                            for word in words:
                                word_counts[word] += 1

                        break

        # Filter and sort by count
        keywords = [
            (word, count)
            for word, count in word_counts.items()
            if count >= self.MIN_KEYWORD_COUNT
        ]
        keywords.sort(key=lambda x: x[1], reverse=True)

        # Return top 100
        return keywords[:100]

    def _extract_words(self, text: str) -> list[str]:
        """Extract meaningful words from text."""
        # Lowercase and split
        text = text.lower()

        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)

        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)

        # Extract words (alphanumeric only, 3+ chars)
        words = re.findall(r'\b[a-z]{3,}\b', text)

        # Filter stop words
        words = [w for w in words if w not in self.STOP_WORDS]

        return words

    async def _analyze_label_patterns(
        self, session: AsyncSession
    ) -> tuple[list[str], list[str]]:
        """
        Analyze which senders tend to get starred/important labels.

        Returns:
            (starred_senders, important_senders)
        """
        # Find emails with STARRED label
        result = await session.execute(
            select(EmailCache.sender_email, func.count(EmailCache.id))
            .where(EmailCache.labels.contains(["STARRED"]))
            .group_by(EmailCache.sender_email)
            .order_by(func.count(EmailCache.id).desc())
            .limit(50)
        )
        starred = [row[0].lower() for row in result.all() if not self._is_user_email(row[0])]

        # Find emails with IMPORTANT label
        result = await session.execute(
            select(EmailCache.sender_email, func.count(EmailCache.id))
            .where(EmailCache.labels.contains(["IMPORTANT"]))
            .group_by(EmailCache.sender_email)
            .order_by(func.count(EmailCache.id).desc())
            .limit(50)
        )
        important = [row[0].lower() for row in result.all() if not self._is_user_email(row[0])]

        return starred, important

    async def save_insights(
        self, session: AsyncSession, insights: BehavioralInsights
    ) -> str:
        """
        Save behavioral insights to indexed_entities table.

        Args:
            session: Database session
            insights: The insights to save

        Returns:
            Entity ID of the saved insight
        """
        entity_id = f"insight_behavioral_{self.user_email.replace('@', '_at_')}"

        # Check if exists
        result = await session.execute(
            select(IndexedEntityModel).where(IndexedEntityModel.id == entity_id)
        )
        existing = result.scalar_one_or_none()

        data = insights.to_dict()

        if existing:
            existing.structured = data
            existing.analyzed = {
                "summary": f"Behavioral analysis for {self.user_email}: "
                          f"{len(insights.vip_contacts)} VIP contacts, "
                          f"{insights.avg_response_time_hours:.1f}h avg response time",
                "vip_count": len(insights.vip_contacts),
                "keyword_count": len(insights.priority_keywords),
            }
            existing.updated_at = datetime.utcnow()
            existing.deleted_at = None
        else:
            model = IndexedEntityModel(
                id=entity_id,
                entity_type="insight",
                source="behavioral_analyzer",
                structured=data,
                analyzed={
                    "summary": f"Behavioral analysis for {self.user_email}: "
                              f"{len(insights.vip_contacts)} VIP contacts, "
                              f"{insights.avg_response_time_hours:.1f}h avg response time",
                    "vip_count": len(insights.vip_contacts),
                    "keyword_count": len(insights.priority_keywords),
                },
            )
            session.add(model)

        await session.flush()
        logger.info(f"Saved behavioral insights as {entity_id}")
        return entity_id

    async def save_vip_contacts(
        self, session: AsyncSession, insights: BehavioralInsights
    ) -> list[str]:
        """
        Save each VIP contact as a separate insight entity.

        This makes them searchable via the Search Agent.

        Returns:
            List of entity IDs created
        """
        entity_ids = []

        for vip in insights.vip_contacts:
            entity_id = f"insight_vip_{vip.email.replace('@', '_at_')}"

            # Check if exists
            result = await session.execute(
                select(IndexedEntityModel).where(IndexedEntityModel.id == entity_id)
            )
            existing = result.scalar_one_or_none()

            data = {
                "email": vip.email,
                "name": vip.name,
                "total_received": vip.total_received,
                "total_responded": vip.total_responded,
                "response_rate": vip.response_rate,
                "avg_response_time_hours": vip.avg_response_time_hours,
                "labels_used": vip.labels_used,
                "analysis_timestamp": insights.analysis_timestamp.isoformat(),
            }

            if existing:
                existing.structured = data
                existing.analyzed = {
                    "summary": f"VIP contact: {vip.name or vip.email} - "
                              f"{vip.response_rate:.0f}% response rate, "
                              f"{vip.total_received} emails",
                }
                existing.updated_at = datetime.utcnow()
                existing.deleted_at = None
            else:
                model = IndexedEntityModel(
                    id=entity_id,
                    entity_type="insight",
                    source="behavioral_analyzer",
                    structured=data,
                    analyzed={
                        "summary": f"VIP contact: {vip.name or vip.email} - "
                                  f"{vip.response_rate:.0f}% response rate, "
                                  f"{vip.total_received} emails",
                    },
                    metadata_={"insight_type": "vip_contact"},
                )
                session.add(model)

            entity_ids.append(entity_id)

        await session.flush()
        logger.info(f"Saved {len(entity_ids)} VIP contact insights")
        return entity_ids
