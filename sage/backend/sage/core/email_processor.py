"""Email processing and sync logic."""

import logging
from datetime import datetime
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sage.config import get_settings
from sage.models.email import EmailCache
from sage.models.user import User
from sage.core.claude_agent import get_claude_agent

settings = get_settings()
logger = logging.getLogger(__name__)


class EmailProcessor:
    """Process and sync emails from Gmail."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_emails(self, max_results: int = 100, include_sent: bool = False) -> int:
        """Sync emails from Gmail.

        Args:
            max_results: Maximum number of emails to fetch
            include_sent: If True, sync all mail; if False, only inbox
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

            # Fetch emails - either inbox only or all mail
            list_params = {
                "userId": "me",
                "maxResults": min(max_results, 500),  # Gmail API max is 500
            }
            if not include_sent:
                list_params["labelIds"] = ["INBOX"]

            all_messages = []
            results = service.users().messages().list(**list_params).execute()
            all_messages.extend(results.get("messages", []))

            # Paginate if we need more and there are more pages
            while len(all_messages) < max_results and "nextPageToken" in results:
                list_params["pageToken"] = results["nextPageToken"]
                list_params["maxResults"] = min(max_results - len(all_messages), 500)
                results = service.users().messages().list(**list_params).execute()
                all_messages.extend(results.get("messages", []))

            logger.info(f"Found {len(all_messages)} messages to process")

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
            logger.error(f"Error syncing emails: {e}")
            raise

    async def _process_email(self, email_data: dict[str, Any]) -> bool:
        """Process a single email from Gmail."""
        from sqlalchemy.exc import IntegrityError

        gmail_id = email_data.get("id")
        if not gmail_id:
            return False

        # Check if email already exists
        existing = await self.db.execute(
            select(EmailCache).where(EmailCache.gmail_id == gmail_id)
        )
        if existing.scalar_one_or_none():
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
                received_at=email.received_at.isoformat(),
            )

            # Store the Qdrant ID in the email record
            email.qdrant_id = qdrant_id
            await self.db.commit()
            logger.debug(f"Indexed email {email.gmail_id} in vector database")
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
