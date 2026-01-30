"""Email processing and sync logic."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, TYPE_CHECKING

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sage.config import get_settings
from sage.models.email import EmailCache
from sage.models.user import User
from sage.core.claude_agent import get_claude_agent
from sage.schemas.email import BulkImportProgress, ImportTierStats

if TYPE_CHECKING:
    from sage.agents.foundational.indexer import IndexerAgent

settings = get_settings()
logger = logging.getLogger(__name__)

# In-memory storage for import progress (could be moved to Redis for production)
_import_progress: dict[str, BulkImportProgress] = {}


def get_import_progress(import_id: str) -> BulkImportProgress | None:
    """Get import progress by ID."""
    return _import_progress.get(import_id)


def list_import_jobs() -> list[BulkImportProgress]:
    """List all import jobs."""
    return list(_import_progress.values())


class EmailProcessor:
    """Process and sync emails from Gmail."""

    def __init__(
        self,
        db: AsyncSession,
        indexer_agent: "IndexerAgent | None" = None,
    ):
        """Initialize the EmailProcessor.

        Args:
            db: AsyncIO SQLAlchemy session for database operations
            indexer_agent: Optional IndexerAgent for unified indexing.
                          If provided, will use IndexerAgent for vector indexing.
                          If not provided, falls back to legacy VectorSearchService.
        """
        self.db = db
        self.indexer_agent = indexer_agent

    async def sync_emails(
        self,
        max_results: int = 100,
        labels: list[str] | None = None,
        custom_labels: list[str] | None = None,
    ) -> int:
        """Sync emails from Gmail.

        Args:
            max_results: Maximum number of emails to fetch per label
            labels: Gmail system labels to sync (e.g., ["INBOX", "SENT"])
            custom_labels: Custom Gmail labels to sync (e.g., ["Signal"])

        This method:
        1. Fetches emails from all specified labels (system and custom)
        2. Deduplicates emails that appear in multiple labels
        3. Handles archive detection for INBOX emails
        """
        from sqlalchemy import text

        # Default to INBOX only if no labels specified
        if labels is None:
            labels = ["INBOX"]
        if custom_labels is None:
            custom_labels = []

        # Get user with Google credentials
        result = await self.db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()

        if not user or not user.google_access_token:
            logger.warning("No user or Google access token found")
            return 0

        try:
            # Build Gmail service with user's credentials
            credentials = Credentials(
                token=user.google_access_token,
                refresh_token=user.google_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
            )
            service = build("gmail", "v1", credentials=credentials)

            # Before syncing, get all gmail_ids that currently have INBOX label in cache
            # We'll use this to detect emails that have been archived
            cached_inbox_ids: set[str] = set()
            if "INBOX" in labels:
                inbox_filter = text("labels @> ARRAY['INBOX']::varchar[]")
                cached_inbox_result = await self.db.execute(
                    select(EmailCache.gmail_id).where(inbox_filter)
                )
                cached_inbox_ids = {row[0] for row in cached_inbox_result.fetchall()}
                logger.debug(f"Found {len(cached_inbox_ids)} emails with INBOX label in cache")

            # Collect message IDs from all sources
            all_message_ids: set[str] = set()
            inbox_message_ids: set[str] = set()  # Track INBOX IDs separately for archive detection

            # Fetch from system labels (INBOX, SENT, etc.)
            for label in labels:
                label_ids = await self._fetch_message_ids_by_label(
                    service, label, max_results
                )
                all_message_ids.update(label_ids)
                if label == "INBOX":
                    inbox_message_ids = label_ids
                logger.info(f"Fetched {len(label_ids)} message IDs from {label}")

            # Fetch from custom labels using search query
            for custom_label in custom_labels:
                custom_ids = await self._fetch_message_ids_by_query(
                    service, f"label:{custom_label}", max_results
                )
                all_message_ids.update(custom_ids)
                logger.info(f"Fetched {len(custom_ids)} message IDs from label:{custom_label}")

            logger.info(f"Total unique message IDs to process: {len(all_message_ids)}")

            # Process all unique messages
            synced_count = 0
            for msg_id in all_message_ids:
                # Get full message details
                email_data = service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="full",
                ).execute()

                synced = await self._process_email(email_data)
                if synced:
                    synced_count += 1

            # Handle archive detection: emails that were in INBOX but are no longer
            if "INBOX" in labels and cached_inbox_ids:
                archived_ids = cached_inbox_ids - inbox_message_ids
                if archived_ids:
                    logger.info(f"Updating {len(archived_ids)} archived emails to remove INBOX label")
                    await self._remove_inbox_label_from_archived(archived_ids)

            return synced_count

        except Exception as e:
            logger.error(f"Error syncing emails: {e}")
            raise

    async def _fetch_message_ids_by_label(
        self,
        service,
        label: str,
        max_results: int,
    ) -> set[str]:
        """Fetch message IDs for a Gmail system label.

        Args:
            service: Gmail API service
            label: Gmail label ID (e.g., "INBOX", "SENT")
            max_results: Maximum number of IDs to fetch
        """
        message_ids: set[str] = set()

        list_params = {
            "userId": "me",
            "maxResults": min(max_results, 500),  # Gmail API max is 500
            "labelIds": [label],
        }

        results = service.users().messages().list(**list_params).execute()
        for msg in results.get("messages", []):
            message_ids.add(msg["id"])

        # Paginate if we need more and there are more pages
        while len(message_ids) < max_results and "nextPageToken" in results:
            list_params["pageToken"] = results["nextPageToken"]
            list_params["maxResults"] = min(max_results - len(message_ids), 500)
            results = service.users().messages().list(**list_params).execute()
            for msg in results.get("messages", []):
                message_ids.add(msg["id"])

        return message_ids

    async def _fetch_message_ids_by_query(
        self,
        service,
        query: str,
        max_results: int,
    ) -> set[str]:
        """Fetch message IDs using a Gmail search query.

        Args:
            service: Gmail API service
            query: Gmail search query (e.g., "label:Signal")
            max_results: Maximum number of IDs to fetch
        """
        message_ids: set[str] = set()

        list_params = {
            "userId": "me",
            "maxResults": min(max_results, 500),
            "q": query,
        }

        results = service.users().messages().list(**list_params).execute()
        for msg in results.get("messages", []):
            message_ids.add(msg["id"])

        # Paginate if we need more and there are more pages
        while len(message_ids) < max_results and "nextPageToken" in results:
            list_params["pageToken"] = results["nextPageToken"]
            list_params["maxResults"] = min(max_results - len(message_ids), 500)
            results = service.users().messages().list(**list_params).execute()
            for msg in results.get("messages", []):
                message_ids.add(msg["id"])

        return message_ids

    async def _remove_inbox_label_from_archived(self, gmail_ids: set[str]) -> None:
        """Remove INBOX label from emails that have been archived in Gmail.

        Args:
            gmail_ids: Set of gmail_ids for emails that are no longer in inbox
        """
        for gmail_id in gmail_ids:
            result = await self.db.execute(
                select(EmailCache).where(EmailCache.gmail_id == gmail_id)
            )
            email = result.scalar_one_or_none()
            if email and email.labels:
                new_labels = [label for label in email.labels if label != "INBOX"]
                if new_labels != email.labels:
                    email.labels = new_labels
                    email.synced_at = datetime.utcnow()
                    logger.debug(f"Removed INBOX label from archived email {gmail_id}")

        await self.db.commit()

    async def _process_email(self, email_data: dict[str, Any]) -> bool:
        """Process a single email from Gmail."""
        from sqlalchemy.exc import IntegrityError

        gmail_id = email_data.get("id")
        if not gmail_id:
            return False

        # Check if email already exists
        existing_result = await self.db.execute(
            select(EmailCache).where(EmailCache.gmail_id == gmail_id)
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            # Update is_unread and labels for existing emails
            new_labels = email_data.get("labelIds", [])
            new_is_unread = "UNREAD" in new_labels

            if existing.is_unread != new_is_unread or existing.labels != new_labels:
                existing.is_unread = new_is_unread
                existing.labels = new_labels
                existing.synced_at = datetime.utcnow()
                await self.db.commit()
                logger.debug(f"Updated email {gmail_id}: is_unread={new_is_unread}")
            return False

        try:
            return await self._insert_email(email_data, gmail_id)
        except IntegrityError:
            # Email was inserted by another process, rollback and continue
            await self.db.rollback()
            logger.debug(f"Email {gmail_id} already exists, skipping")
            return False

    async def _insert_email(self, email_data: dict[str, Any], gmail_id: str) -> bool:
        """Insert a new email into the database."""

        # Parse email data
        headers = {
            h["name"].lower(): h["value"]
            for h in email_data.get("payload", {}).get("headers", [])
        }

        # Extract sender info
        from_header = headers.get("from", "")
        sender_email, sender_name = self._parse_email_address(from_header)

        # Extract body
        body_text = self._extract_body(email_data.get("payload", {}))

        # Create email cache entry
        email = EmailCache(
            gmail_id=gmail_id,
            thread_id=email_data.get("threadId", ""),
            history_id=email_data.get("historyId"),
            subject=headers.get("subject", "(No Subject)"),
            sender_email=sender_email,
            sender_name=sender_name,
            to_emails=self._parse_email_list(headers.get("to", "")),
            cc_emails=self._parse_email_list(headers.get("cc", "")),
            body_text=body_text,
            snippet=email_data.get("snippet"),
            labels=email_data.get("labelIds", []),
            is_unread="UNREAD" in email_data.get("labelIds", []),
            has_attachments=self._has_attachments(email_data.get("payload", {})),
            received_at=datetime.fromtimestamp(
                int(email_data.get("internalDate", 0)) / 1000
            ),
        )

        self.db.add(email)
        await self.db.commit()

        # Trigger AI analysis
        await self._analyze_email(email)

        # Index in vector database for semantic search
        await self._index_email(email)

        return True

    async def _analyze_email(self, email: EmailCache) -> None:
        """Analyze email using Claude."""
        try:
            agent = await get_claude_agent()
            analysis = await agent.analyze_email(email)

            email.category = analysis.category
            email.priority = analysis.priority
            email.summary = analysis.summary
            email.requires_response = analysis.requires_response
            email.analyzed_at = datetime.utcnow()

            await self.db.commit()
        except Exception as e:
            logger.error(f"Error analyzing email {email.gmail_id}: {e}")

    async def _index_email(self, email: EmailCache) -> None:
        """Index email in vector database for semantic search.

        Uses IndexerAgent if available, otherwise falls back to legacy VectorSearchService.
        """
        try:
            if self.indexer_agent:
                # Use the unified IndexerAgent for indexing
                result = await self.indexer_agent.execute(
                    "index_email",
                    {
                        "gmail_id": email.gmail_id,
                        "thread_id": email.thread_id,
                        "subject": email.subject,
                        "sender_email": email.sender_email,
                        "sender_name": email.sender_name,
                        "to_emails": email.to_emails or [],
                        "cc_emails": email.cc_emails or [],
                        "body_text": email.body_text,
                        "snippet": email.snippet,
                        "received_at": email.received_at.isoformat() if email.received_at else None,
                        "labels": email.labels or [],
                        "has_attachments": email.has_attachments,
                        # Pass along any existing analysis
                        "category": email.category,
                        "priority": email.priority,
                        "summary": email.summary,
                        "requires_response": email.requires_response,
                    }
                )
                if result.success:
                    # Store the entity ID in the email record (can be used as qdrant_id reference)
                    email.qdrant_id = result.data.get("entity_id")
                    await self.db.commit()
                    logger.debug(f"Indexed email {email.gmail_id} via IndexerAgent")
                else:
                    logger.warning(f"IndexerAgent failed for {email.gmail_id}: {result.errors}")
            else:
                # Legacy: Use VectorSearchService directly
                from sage.services.vector_search import get_vector_service

                vector_service = get_vector_service()
                qdrant_id = vector_service.index_email(
                    email_id=email.id,
                    gmail_id=email.gmail_id,
                    subject=email.subject,
                    body=email.body_text,
                    sender=f"{email.sender_name or ''} <{email.sender_email}>",
                    received_at=email.received_at.isoformat() if email.received_at else None,
                )

                # Store the Qdrant ID in the email record
                email.qdrant_id = qdrant_id
                await self.db.commit()
                logger.debug(f"Indexed email {email.gmail_id} in vector database (legacy)")
        except Exception as e:
            logger.error(f"Error indexing email {email.gmail_id}: {e}")

    def _parse_email_address(self, header: str) -> tuple[str, str | None]:
        """Parse email address from header like 'Name <email@example.com>'."""
        import re

        match = re.match(r"^(.+?)\s*<(.+?)>$", header.strip())
        if match:
            return match.group(2), match.group(1).strip('"')
        return header.strip(), None

    def _parse_email_list(self, header: str) -> list[str]:
        """Parse comma-separated email addresses."""
        if not header:
            return []
        return [e.strip() for e in header.split(",") if e.strip()]

    def _extract_body(self, payload: dict) -> str | None:
        """Extract plain text body from email payload."""
        import base64

        mime_type = payload.get("mimeType", "")

        if mime_type == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

        # Check parts for multipart messages
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            # Recursively check nested parts
            body = self._extract_body(part)
            if body:
                return body

        return None

    def _has_attachments(self, payload: dict) -> bool:
        """Check if email has attachments."""
        for part in payload.get("parts", []):
            if part.get("filename"):
                return True
            if self._has_attachments(part):
                return True
        return False

    async def sync_emails_by_query(self, query: str, max_results: int = 100) -> int:
        """Sync emails from Gmail matching a search query.

        Args:
            query: Gmail search query (e.g., "from:user@example.com subject:Meeting Notes")
            max_results: Maximum number of emails to fetch
        """
        # Get user with Google credentials
        result = await self.db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()

        if not user or not user.google_access_token:
            logger.warning("No user or Google access token found")
            return 0

        try:
            # Build Gmail service with user's credentials
            credentials = Credentials(
                token=user.google_access_token,
                refresh_token=user.google_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
            )
            service = build("gmail", "v1", credentials=credentials)

            # Fetch emails using search query (searches all mail by default)
            list_params = {
                "userId": "me",
                "maxResults": min(max_results, 500),
                "q": query,
            }

            all_messages = []
            results = service.users().messages().list(**list_params).execute()
            all_messages.extend(results.get("messages", []))

            # Paginate if we need more and there are more pages
            while len(all_messages) < max_results and "nextPageToken" in results:
                list_params["pageToken"] = results["nextPageToken"]
                list_params["maxResults"] = min(max_results - len(all_messages), 500)
                results = service.users().messages().list(**list_params).execute()
                all_messages.extend(results.get("messages", []))

            logger.info(f"Found {len(all_messages)} messages matching query: {query}")

            synced_count = 0
            for msg in all_messages[:max_results]:
                # Get full message details
                email_data = service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="full",
                ).execute()

                synced = await self._process_email(email_data)
                if synced:
                    synced_count += 1

            return synced_count

        except Exception as e:
            logger.error(f"Error syncing emails by query: {e}")
            raise

    async def detect_replies(self) -> int:
        """Detect new replies to tracked follow-ups."""
        from sage.models.followup import Followup, FollowupStatus

        # Get active followups
        result = await self.db.execute(
            select(Followup).where(
                Followup.status.in_([
                    FollowupStatus.PENDING,
                    FollowupStatus.REMINDED,
                    FollowupStatus.ESCALATED,
                ])
            )
        )
        followups = result.scalars().all()

        closed_count = 0
        for followup in followups:
            # Check if there's a newer email in the thread
            email_result = await self.db.execute(
                select(EmailCache).where(
                    EmailCache.thread_id == followup.thread_id,
                    EmailCache.sender_email == followup.contact_email,
                    EmailCache.received_at > followup.created_at,
                ).limit(1)
            )
            reply = email_result.scalar_one_or_none()

            if reply:
                followup.mark_completed("Response received")
                closed_count += 1

        if closed_count > 0:
            await self.db.commit()

        return closed_count


class BulkEmailImporter:
    """
    Bulk email importer with tiered indexing strategy.

    Tier 1 - Full Corpus: All emails get metadata + vector embeddings (no AI analysis)
    Tier 2 - Active Window: Recent emails (default 90 days) get full AI analysis
    Tier 3 - Voice Corpus: Sent emails are flagged for voice profile training
    """

    # Cost estimates (rough, for user feedback)
    EMBEDDING_COST_PER_1K = 0.0001  # ~$0.0001 per 1K tokens for embeddings
    AI_ANALYSIS_COST_PER_EMAIL = 0.003  # ~$0.003 per email for Claude analysis

    def __init__(self, db: AsyncSession):
        self.db = db
        self.service = None
        self.progress: BulkImportProgress | None = None

    async def _get_gmail_service(self):
        """Get authenticated Gmail service."""
        if self.service:
            return self.service

        result = await self.db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()

        if not user or not user.google_access_token:
            raise ValueError("No user or Google access token found")

        credentials = Credentials(
            token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )
        self.service = build("gmail", "v1", credentials=credentials)
        return self.service

    async def start_import(
        self,
        include_inbox: bool = True,
        include_sent: bool = True,
        include_labels: list[str] | None = None,
        max_emails: int | None = None,
        active_window_days: int = 90,
    ) -> str:
        """
        Start a bulk email import.

        Args:
            include_inbox: Include INBOX emails
            include_sent: Include SENT emails
            include_labels: Additional labels to include (e.g., ["Signal"])
            max_emails: Maximum emails to import (None = no limit)
            active_window_days: Emails within this window get full AI analysis

        Returns:
            Import ID for tracking progress
        """
        import_id = str(uuid.uuid4())[:8]

        self.progress = BulkImportProgress(
            import_id=import_id,
            status="pending",
            started_at=datetime.utcnow(),
            current_phase="initializing",
        )
        _import_progress[import_id] = self.progress

        try:
            await self._run_import(
                include_inbox=include_inbox,
                include_sent=include_sent,
                include_labels=include_labels or [],
                max_emails=max_emails,
                active_window_days=active_window_days,
            )
        except Exception as e:
            self.progress.status = "failed"
            self.progress.error_message = str(e)
            self.progress.completed_at = datetime.utcnow()
            logger.error(f"Bulk import {import_id} failed: {e}")
            raise

        return import_id

    async def _run_import(
        self,
        include_inbox: bool,
        include_sent: bool,
        include_labels: list[str],
        max_emails: int | None,
        active_window_days: int,
    ):
        """Execute the bulk import process."""
        service = await self._get_gmail_service()

        # Phase 1: Fetch all message IDs
        self.progress.status = "fetching_ids"
        self.progress.current_phase = "Fetching message IDs from Gmail"

        all_message_ids = set()

        # Build list of label queries
        label_queries = []
        if include_inbox:
            label_queries.append(("INBOX", None))
        if include_sent:
            label_queries.append(("SENT", None))
        for label in include_labels:
            label_queries.append((None, f"label:{label}"))

        for label_id, query in label_queries:
            self.progress.current_phase = f"Fetching IDs for {label_id or query}"
            # Fetch ALL IDs (no limit) - we apply max_emails limit later during processing
            ids = await self._fetch_message_ids(service, label_id, query, max_ids=None)
            all_message_ids.update(ids)
            self.progress.message_ids_fetched = len(all_message_ids)
            logger.info(f"Fetched {len(ids)} IDs for {label_id or query}, total unique: {len(all_message_ids)}")

        self.progress.total_message_ids = len(all_message_ids)
        logger.info(f"Total unique message IDs to process: {len(all_message_ids)}")

        # Apply max_emails limit if specified
        message_ids = list(all_message_ids)
        if max_emails and len(message_ids) > max_emails:
            message_ids = message_ids[:max_emails]
            self.progress.total_message_ids = max_emails

        # Phase 2: Process emails in tiers
        self.progress.status = "processing"
        self.progress.current_phase = "Processing emails"

        active_window_cutoff = datetime.utcnow() - timedelta(days=active_window_days)

        # Estimate costs
        self.progress.estimated_embedding_cost = len(message_ids) * self.EMBEDDING_COST_PER_1K * 0.5  # ~500 tokens avg
        # AI analysis only for active window - estimate 20% of corpus
        estimated_active_emails = int(len(message_ids) * 0.2)
        self.progress.estimated_ai_cost = estimated_active_emails * self.AI_ANALYSIS_COST_PER_EMAIL

        for i, msg_id in enumerate(message_ids):
            try:
                self.progress.current_email = f"Processing {i+1}/{len(message_ids)}"
                await self._process_single_email(
                    service, msg_id, active_window_cutoff
                )

            except Exception as e:
                logger.error(f"Error processing email {msg_id}: {e}")
                self.progress.tier1_full_corpus.errors += 1
                # Rollback any pending changes and continue with next email
                try:
                    await self.db.rollback()
                except Exception:
                    pass

            # Commit every 50 emails to avoid large transactions
            if (i + 1) % 50 == 0:
                try:
                    await self.db.commit()
                except Exception as e:
                    logger.error(f"Commit failed at {i+1}: {e}")
                    await self.db.rollback()
                logger.info(f"Processed {i+1}/{len(message_ids)} emails")

        # Final commit
        await self.db.commit()

        # Mark complete
        self.progress.status = "completed"
        self.progress.completed_at = datetime.utcnow()
        self.progress.current_phase = "Import completed"
        self.progress.current_email = None

        logger.info(
            f"Bulk import completed: {self.progress.emails_processed} processed, "
            f"{self.progress.emails_skipped} skipped, "
            f"{self.progress.embeddings_generated} embeddings, "
            f"{self.progress.ai_analyses_performed} AI analyses"
        )

    async def _fetch_message_ids(
        self,
        service,
        label_id: str | None,
        query: str | None,
        max_ids: int | None = None,
    ) -> set[str]:
        """Fetch all message IDs for a given label or query.

        Args:
            service: Gmail API service
            label_id: Gmail label ID (e.g., "INBOX", "SENT")
            query: Gmail search query (e.g., "label:Signal")
            max_ids: Optional limit on IDs to fetch (None = fetch all)
        """
        message_ids = set()

        list_params = {
            "userId": "me",
            "maxResults": 500,  # Gmail API max per page
        }
        if label_id:
            list_params["labelIds"] = [label_id]
        if query:
            list_params["q"] = query

        page_count = 0
        while True:
            results = service.users().messages().list(**list_params).execute()
            messages = results.get("messages", [])
            page_count += 1

            for msg in messages:
                message_ids.add(msg["id"])

            # Log progress for large fetches
            if page_count % 10 == 0:
                logger.info(f"Fetched {page_count} pages, {len(message_ids)} IDs so far...")

            # Check if we have enough (if limit specified) or if there are more pages
            if max_ids and len(message_ids) >= max_ids:
                break
            if "nextPageToken" not in results:
                break

            list_params["pageToken"] = results["nextPageToken"]

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.05)

        return message_ids

    async def _process_single_email(
        self,
        service,
        gmail_id: str,
        active_window_cutoff: datetime,
    ):
        """
        Process a single email with tiered indexing.

        Tier 1: All emails get metadata + embeddings
        Tier 2: Emails after active_window_cutoff get AI analysis
        Tier 3: Sent emails are flagged for voice training
        """
        from sqlalchemy.exc import IntegrityError

        # Check if email already exists
        existing_result = await self.db.execute(
            select(EmailCache).where(EmailCache.gmail_id == gmail_id)
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            self.progress.emails_skipped += 1
            self.progress.tier1_full_corpus.skipped += 1

            # Even if it exists, ensure it has embeddings
            if not existing.qdrant_id:
                await self._index_email_embedding(existing)
            return

        # Fetch full email data
        email_data = service.users().messages().get(
            userId="me",
            id=gmail_id,
            format="full",
        ).execute()

        # Parse email
        email = await self._parse_and_store_email(email_data)
        if not email:
            return

        self.progress.emails_processed += 1
        self.progress.tier1_full_corpus.processed += 1

        # Determine tier membership
        is_in_active_window = email.received_at >= active_window_cutoff
        is_sent = "SENT" in (email.labels or [])

        # Tier 1: Generate embedding (all emails)
        await self._index_email_embedding(email)
        self.progress.embeddings_generated += 1

        # Tier 2: AI analysis for active window
        if is_in_active_window:
            self.progress.tier2_active_window.total += 1
            try:
                await self._analyze_email(email)
                self.progress.tier2_active_window.processed += 1
                self.progress.ai_analyses_performed += 1
            except Exception as e:
                logger.warning(f"AI analysis failed for {gmail_id}: {e}")
                self.progress.tier2_active_window.errors += 1

        # Tier 3: Flag for voice corpus
        if is_sent:
            self.progress.tier3_voice_corpus.total += 1
            self.progress.tier3_voice_corpus.processed += 1
            # For now, just track it. Later we'll add voice_corpus column
            # email.in_voice_corpus = True

    async def _parse_and_store_email(self, email_data: dict[str, Any]) -> EmailCache | None:
        """Parse Gmail API response and store in database."""
        from sqlalchemy.exc import IntegrityError, SQLAlchemyError

        gmail_id = email_data.get("id")
        if not gmail_id:
            return None

        # Parse headers
        headers = {
            h["name"].lower(): h["value"]
            for h in email_data.get("payload", {}).get("headers", [])
        }

        # Extract sender info
        from_header = headers.get("from", "")
        sender_email, sender_name = self._parse_email_address(from_header)

        # Extract body
        body_text = self._extract_body(email_data.get("payload", {}))

        # Parse received date
        internal_date = int(email_data.get("internalDate", 0)) / 1000
        received_at = datetime.fromtimestamp(internal_date) if internal_date else datetime.utcnow()

        # Truncate fields to match database constraints
        subject = headers.get("subject", "(No Subject)")
        if len(subject) > 500:
            subject = subject[:497] + "..."

        if sender_name and len(sender_name) > 255:
            sender_name = sender_name[:252] + "..."

        if sender_email and len(sender_email) > 255:
            sender_email = sender_email[:255]

        # Truncate email lists to fit varchar(255)[] constraint
        to_emails = [e[:255] for e in self._parse_email_list(headers.get("to", ""))]
        cc_emails = [e[:255] for e in self._parse_email_list(headers.get("cc", ""))]

        email = EmailCache(
            gmail_id=gmail_id,
            thread_id=email_data.get("threadId", "")[:500] if email_data.get("threadId") else "",
            history_id=email_data.get("historyId"),
            subject=subject,
            sender_email=sender_email,
            sender_name=sender_name,
            to_emails=to_emails,
            cc_emails=cc_emails,
            body_text=body_text,
            snippet=email_data.get("snippet"),
            labels=email_data.get("labelIds", []),
            is_unread="UNREAD" in email_data.get("labelIds", []),
            has_attachments=self._has_attachments(email_data.get("payload", {})),
            received_at=received_at,
        )

        try:
            self.db.add(email)
            await self.db.flush()  # Get the ID without committing
            return email
        except IntegrityError:
            await self.db.rollback()
            return None
        except SQLAlchemyError as e:
            # Handle any other database errors gracefully
            logger.warning(f"Database error storing email {gmail_id}: {e}")
            await self.db.rollback()
            return None

    async def _index_email_embedding(self, email: EmailCache) -> None:
        """Index email in vector database for semantic search."""
        try:
            from sage.services.vector_search import get_vector_service

            vector_service = get_vector_service()
            qdrant_id = vector_service.index_email(
                email_id=email.id,
                gmail_id=email.gmail_id,
                subject=email.subject,
                body=email.body_text,
                sender=f"{email.sender_name or ''} <{email.sender_email}>",
                received_at=email.received_at.isoformat() if email.received_at else None,
            )

            email.qdrant_id = qdrant_id
        except Exception as e:
            logger.error(f"Error indexing email {email.gmail_id}: {e}")

    async def _analyze_email(self, email: EmailCache) -> None:
        """Analyze email using Claude AI."""
        agent = await get_claude_agent()
        analysis = await agent.analyze_email(email)

        email.category = analysis.category
        email.priority = analysis.priority
        email.summary = analysis.summary
        email.requires_response = analysis.requires_response
        email.analyzed_at = datetime.utcnow()

    # Helper methods (same as EmailProcessor)
    def _parse_email_address(self, header: str) -> tuple[str, str | None]:
        """Parse email address from header like 'Name <email@example.com>'."""
        import re
        match = re.match(r"^(.+?)\s*<(.+?)>$", header.strip())
        if match:
            return match.group(2), match.group(1).strip('"')
        return header.strip(), None

    def _parse_email_list(self, header: str) -> list[str]:
        """Parse comma-separated email addresses."""
        if not header:
            return []
        return [e.strip() for e in header.split(",") if e.strip()]

    def _extract_body(self, payload: dict) -> str | None:
        """Extract plain text body from email payload."""
        import base64

        mime_type = payload.get("mimeType", "")

        if mime_type == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            body = self._extract_body(part)
            if body:
                return body

        return None

    def _has_attachments(self, payload: dict) -> bool:
        """Check if email has attachments."""
        for part in payload.get("parts", []):
            if part.get("filename"):
                return True
            if self._has_attachments(part):
                return True
        return False
