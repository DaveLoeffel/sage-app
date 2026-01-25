"""
Indexer Agent - Data Layer Manager.

The Indexer Agent is responsible for ingesting data from all sources
and preparing it for optimal retrieval. It handles:
- Email indexing with embeddings
- Meeting transcript processing
- Contact profile management
- Calendar event indexing
- Conversation memory capture
- Fact extraction and supersession

See sage-agent-architecture.md Section 2.2 for specifications.
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from ..base import (
    BaseAgent,
    AgentResult,
    AgentType,
    SearchContext,
    DataLayerInterface,
    IndexedEntity,
    Relationship,
)

logger = logging.getLogger(__name__)


class IndexerAgent(BaseAgent):
    """
    The Indexer Agent ingests and optimizes data for retrieval.

    This is a foundational agent that operates at the Data Layer.
    It transforms raw data from external sources (Gmail, Calendar,
    Fireflies, user conversations) into search-optimized formats.

    Capabilities:
        - index_email: Process and store email with embeddings
        - index_meeting: Process meeting transcript
        - index_contact: Create/update contact profile
        - index_document: Process document from Drive
        - index_event: Process calendar event
        - index_memory: Capture and index conversation exchanges
        - extract_facts: Pull facts, decisions, preferences from conversation
        - reindex_entity: Re-process existing entity
        - delete_entity: Remove from all indices
        - link_entities: Create relationship between entities
        - supersede_fact: Mark old fact as superseded by new one
    """

    name = "indexer"
    description = "Ingests and optimizes data for retrieval across all storage systems"
    agent_type = AgentType.FOUNDATIONAL
    capabilities = [
        "index_email",
        "index_meeting",
        "index_contact",
        "index_document",
        "index_event",
        "index_memory",
        "extract_facts",
        "reindex_entity",
        "delete_entity",
        "link_entities",
        "supersede_fact",
    ]

    # Fact extraction prompt for Claude
    FACT_EXTRACTION_PROMPT = """Analyze the following conversation exchange and extract any important information.

User message: {user_message}

Assistant response: {sage_response}

Extract the following types of information if present:

1. **Facts** - New information stated (e.g., "Luke's birthday is February 13", "The meeting is at 3pm")
2. **Fact Corrections** - Updates to existing information (e.g., "The deadline changed from Jan 31 to Feb 15")
3. **Decisions** - Choices or decisions made (e.g., "We'll use vendor A instead of B")
4. **Preferences** - User preferences expressed (e.g., "Don't schedule meetings before 9am")
5. **Tasks** - Action items or things to remember (e.g., "Call Steve on Monday")

For each extracted item, provide:
- type: fact | fact_correction | decision | preference | task
- content: The extracted information
- confidence: 0.0-1.0 (how certain you are this is meaningful information)
- entities_mentioned: List of people, projects, dates, or other entities mentioned

Return a JSON array. If nothing meaningful to extract, return an empty array [].

Example output:
[
  {{
    "type": "fact",
    "content": "Insurance renewal deadline is February 15, 2026",
    "confidence": 1.0,
    "entities_mentioned": ["insurance renewal", "February 15, 2026"]
  }},
  {{
    "type": "preference",
    "content": "Prefers email over phone calls for non-urgent matters",
    "confidence": 0.8,
    "entities_mentioned": []
  }}
]

Now analyze the conversation and extract information:"""

    def __init__(self, data_layer: DataLayerInterface):
        """
        Initialize the Indexer Agent.

        Args:
            data_layer: The data layer interface for storage operations
        """
        # Indexer doesn't use search/indexer refs - it IS the indexer
        super().__init__(search_agent=None, indexer_agent=None)
        self.data_layer = data_layer
        self._claude_client = None

    async def _get_claude(self):
        """Get or create Claude client for AI operations."""
        if self._claude_client is None:
            from anthropic import AsyncAnthropic
            from sage.config import get_settings

            settings = get_settings()
            self._claude_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._claude_client

    def _generate_entity_id(self, entity_type: str, source_id: str | None = None) -> str:
        """Generate a unique entity ID."""
        if source_id:
            return f"{entity_type}_{source_id}"
        return f"{entity_type}_{uuid.uuid4().hex[:12]}"

    def _now_iso(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.utcnow().isoformat()

    async def execute(
        self,
        capability: str,
        params: dict[str, Any],
        context: SearchContext | None = None
    ) -> AgentResult:
        """
        Execute an indexing capability.

        Args:
            capability: The capability to invoke
            params: Parameters for the capability
            context: Not typically used by Indexer Agent

        Returns:
            AgentResult with indexing outcome
        """
        self._validate_capability(capability)

        try:
            if capability == "index_email":
                return await self._index_email(params)
            elif capability == "index_meeting":
                return await self._index_meeting(params)
            elif capability == "index_contact":
                return await self._index_contact(params)
            elif capability == "index_document":
                return await self._index_document(params)
            elif capability == "index_event":
                return await self._index_event(params)
            elif capability == "index_memory":
                return await self._index_memory(params)
            elif capability == "extract_facts":
                return await self._extract_facts(params)
            elif capability == "reindex_entity":
                return await self._reindex_entity(params)
            elif capability == "delete_entity":
                return await self._delete_entity(params)
            elif capability == "link_entities":
                return await self._link_entities(params)
            elif capability == "supersede_fact":
                return await self._supersede_fact(params)
            else:
                return AgentResult(
                    success=False,
                    data={},
                    errors=[f"Unknown capability: {capability}"]
                )
        except Exception as e:
            logger.error(f"Indexing error in {capability}: {e}", exc_info=True)
            return AgentResult(
                success=False,
                data={},
                errors=[f"Indexing error: {str(e)}"]
            )

    async def index_entity(self, entity_data: dict) -> str:
        """
        High-level method to index any entity.

        This is the method called by other agents via persist_data().

        Args:
            entity_data: Entity data dict with entity_type field

        Returns:
            The entity ID
        """
        entity_type = entity_data.get("entity_type", "unknown")

        if entity_type == "email":
            result = await self._index_email(entity_data)
        elif entity_type == "meeting":
            result = await self._index_meeting(entity_data)
        elif entity_type == "contact":
            result = await self._index_contact(entity_data)
        elif entity_type == "document":
            result = await self._index_document(entity_data)
        elif entity_type == "event":
            result = await self._index_event(entity_data)
        elif entity_type == "memory":
            result = await self._index_memory(entity_data)
        else:
            # Generic indexing
            entity = IndexedEntity(
                id=entity_data.get("id", self._generate_entity_id(entity_type)),
                entity_type=entity_type,
                source=entity_data.get("source", "unknown"),
                structured=entity_data.get("structured", {}),
                analyzed=entity_data.get("analyzed", {}),
                relationships=entity_data.get("relationships", {}),
                embeddings=entity_data.get("embeddings", {}),
                metadata=entity_data.get("metadata", {}),
            )
            return await self.data_layer.store_entity(entity)

        return result.data.get("entity_id", "")

    # =========================================================================
    # Simple Capabilities
    # =========================================================================

    async def _delete_entity(self, params: dict) -> AgentResult:
        """
        Remove entity from all indices.

        Expected params:
            entity_id: str - The entity ID to delete
        """
        entity_id = params.get("entity_id")
        if not entity_id:
            return AgentResult(
                success=False,
                data={},
                errors=["entity_id is required"]
            )

        deleted = await self.data_layer.delete_entity(entity_id)

        return AgentResult(
            success=deleted,
            data={
                "entity_id": entity_id,
                "deleted": deleted
            },
            errors=[] if deleted else [f"Entity {entity_id} not found"]
        )

    async def _link_entities(self, params: dict) -> AgentResult:
        """
        Create relationship between two entities.

        Expected params:
            from_id: str - Source entity ID
            to_id: str - Target entity ID
            rel_type: str - Relationship type (e.g., "sent_to", "mentions", "related_to")
            metadata: dict (optional) - Additional relationship metadata
        """
        from_id = params.get("from_id")
        to_id = params.get("to_id")
        rel_type = params.get("rel_type")
        metadata = params.get("metadata", {})

        if not all([from_id, to_id, rel_type]):
            return AgentResult(
                success=False,
                data={},
                errors=["from_id, to_id, and rel_type are required"]
            )

        created = await self.data_layer.create_relationship(
            from_id=from_id,
            to_id=to_id,
            rel_type=rel_type,
            metadata=metadata
        )

        return AgentResult(
            success=True,
            data={
                "from_id": from_id,
                "to_id": to_id,
                "rel_type": rel_type,
                "created": created
            }
        )

    async def _reindex_entity(self, params: dict) -> AgentResult:
        """
        Re-process an existing entity.

        Retrieves the entity, optionally re-analyzes it, and re-stores it
        to update embeddings and any computed fields.

        Expected params:
            entity_id: str - The entity ID to reindex
            force_analyze: bool (optional) - Force re-analysis with AI
        """
        entity_id = params.get("entity_id")
        force_analyze = params.get("force_analyze", False)

        if not entity_id:
            return AgentResult(
                success=False,
                data={},
                errors=["entity_id is required"]
            )

        # Get existing entity
        entity = await self.data_layer.get_entity(entity_id)
        if not entity:
            return AgentResult(
                success=False,
                data={},
                errors=[f"Entity {entity_id} not found"]
            )

        # Update metadata
        entity.metadata["reindexed_at"] = self._now_iso()
        entity.metadata["reindex_count"] = entity.metadata.get("reindex_count", 0) + 1

        # Re-store (will regenerate embeddings)
        new_id = await self.data_layer.store_entity(entity)

        return AgentResult(
            success=True,
            data={
                "entity_id": new_id,
                "reindexed": True,
                "entity_type": entity.entity_type
            }
        )

    # =========================================================================
    # Email Indexing
    # =========================================================================

    async def _index_email(self, params: dict) -> AgentResult:
        """
        Process and store email with embeddings.

        Expected params (option 1 - raw Gmail data):
            email_data: dict - Gmail API response

        Expected params (option 2 - pre-parsed):
            gmail_id: str
            thread_id: str
            subject: str
            sender_email: str
            sender_name: str (optional)
            to_emails: list[str]
            cc_emails: list[str] (optional)
            body_text: str
            received_at: str (ISO format)
            labels: list[str] (optional)

        Optional params:
            analyze: bool - Whether to run AI analysis (default: False)
            category: str - Pre-determined category
            priority: str - Pre-determined priority
        """
        # Handle raw Gmail API data
        email_data = params.get("email_data")
        if email_data:
            parsed = self._parse_gmail_response(email_data)
        else:
            parsed = {
                "gmail_id": params.get("gmail_id"),
                "thread_id": params.get("thread_id"),
                "subject": params.get("subject", "(No Subject)"),
                "sender_email": params.get("sender_email"),
                "sender_name": params.get("sender_name"),
                "to_emails": params.get("to_emails", []),
                "cc_emails": params.get("cc_emails", []),
                "body_text": params.get("body_text"),
                "snippet": params.get("snippet"),
                "received_at": params.get("received_at"),
                "labels": params.get("labels", []),
                "has_attachments": params.get("has_attachments", False),
            }

        if not parsed.get("gmail_id"):
            return AgentResult(
                success=False,
                data={},
                errors=["gmail_id is required"]
            )

        entity_id = self._generate_entity_id("email", parsed["gmail_id"])

        # Build analyzed section
        analyzed = {}
        if params.get("category"):
            analyzed["category"] = params["category"]
        if params.get("priority"):
            analyzed["priority"] = params["priority"]
        if params.get("summary"):
            analyzed["summary"] = params["summary"]
        if params.get("requires_response") is not None:
            analyzed["requires_response"] = params["requires_response"]

        # Create entity
        entity = IndexedEntity(
            id=entity_id,
            entity_type="email",
            source="gmail",
            structured=parsed,
            analyzed=analyzed,
            relationships={},
            embeddings={},
            metadata={
                "indexed_at": self._now_iso(),
                "index_version": 1
            }
        )

        # Store entity (auto-creates embedding)
        stored_id = await self.data_layer.store_entity(entity)

        # Create relationship to sender contact if identifiable
        if parsed.get("sender_email"):
            contact_id = f"contact_{parsed['sender_email'].lower().replace('@', '_at_').replace('.', '_')}"
            await self.data_layer.create_relationship(
                from_id=stored_id,
                to_id=contact_id,
                rel_type="received_from",
                metadata={"sender_name": parsed.get("sender_name")}
            )

        logger.info(f"Indexed email {stored_id}")

        return AgentResult(
            success=True,
            data={
                "entity_id": stored_id,
                "gmail_id": parsed["gmail_id"],
                "subject": parsed.get("subject"),
                "indexed": True
            }
        )

    def _parse_gmail_response(self, email_data: dict) -> dict:
        """Parse Gmail API response into structured format."""
        import base64

        gmail_id = email_data.get("id")
        thread_id = email_data.get("threadId", "")

        # Parse headers
        headers = {}
        for header in email_data.get("payload", {}).get("headers", []):
            headers[header["name"].lower()] = header["value"]

        # Extract sender
        from_header = headers.get("from", "")
        sender_email, sender_name = self._parse_email_address(from_header)

        # Extract body
        body_text = self._extract_body(email_data.get("payload", {}))

        # Parse received date
        internal_date = int(email_data.get("internalDate", 0)) / 1000
        received_at = datetime.fromtimestamp(internal_date).isoformat() if internal_date else None

        return {
            "gmail_id": gmail_id,
            "thread_id": thread_id,
            "subject": headers.get("subject", "(No Subject)"),
            "sender_email": sender_email,
            "sender_name": sender_name,
            "to_emails": self._parse_email_list(headers.get("to", "")),
            "cc_emails": self._parse_email_list(headers.get("cc", "")),
            "body_text": body_text,
            "snippet": email_data.get("snippet"),
            "received_at": received_at,
            "labels": email_data.get("labelIds", []),
            "has_attachments": self._has_attachments(email_data.get("payload", {})),
            "history_id": email_data.get("historyId"),
        }

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

    # =========================================================================
    # Contact Indexing
    # =========================================================================

    async def _index_contact(self, params: dict) -> AgentResult:
        """
        Create/update contact profile.

        Expected params:
            email: str - Contact's email address (required)
            name: str - Contact's name
            company: str (optional)
            role: str (optional)
            phone: str (optional)
            category: str (optional) - team, external, vendor, family
            reports_to: str (optional) - Supervisor's email or contact ID
            notes: str (optional)
        """
        email = params.get("email")
        if not email:
            return AgentResult(
                success=False,
                data={},
                errors=["email is required for contact"]
            )

        # Generate consistent contact ID from email
        email_normalized = email.lower().replace("@", "_at_").replace(".", "_")
        entity_id = f"contact_{email_normalized}"

        structured = {
            "email": email.lower(),
            "name": params.get("name"),
            "company": params.get("company"),
            "role": params.get("role"),
            "phone": params.get("phone"),
            "category": params.get("category", "external"),
        }

        # Remove None values
        structured = {k: v for k, v in structured.items() if v is not None}

        entity = IndexedEntity(
            id=entity_id,
            entity_type="contact",
            source=params.get("source", "manual"),
            structured=structured,
            analyzed={
                "notes": params.get("notes")
            } if params.get("notes") else {},
            relationships={},
            embeddings={},
            metadata={
                "indexed_at": self._now_iso(),
                "index_version": 1
            }
        )

        stored_id = await self.data_layer.store_entity(entity)

        # Create reports_to relationship if specified
        if params.get("reports_to"):
            supervisor = params["reports_to"]
            if not supervisor.startswith("contact_"):
                supervisor = f"contact_{supervisor.lower().replace('@', '_at_').replace('.', '_')}"
            await self.data_layer.create_relationship(
                from_id=stored_id,
                to_id=supervisor,
                rel_type="reports_to"
            )

        logger.info(f"Indexed contact {stored_id}")

        return AgentResult(
            success=True,
            data={
                "entity_id": stored_id,
                "email": email,
                "name": params.get("name"),
                "indexed": True
            }
        )

    # =========================================================================
    # Memory Indexing
    # =========================================================================

    async def _index_memory(self, params: dict) -> AgentResult:
        """
        Capture and index conversation exchange.

        This creates a memory entry from a user-assistant exchange,
        optionally extracts facts/decisions/preferences, and stores them
        for future retrieval.

        Expected params:
            conversation_id: str
            user_message: str
            sage_response: str
            timestamp: str (optional, defaults to now)
            turn_number: int (optional)
            extract_facts: bool (optional, default True)
        """
        conversation_id = params.get("conversation_id")
        user_message = params.get("user_message")
        sage_response = params.get("sage_response")

        if not all([conversation_id, user_message, sage_response]):
            return AgentResult(
                success=False,
                data={},
                errors=["conversation_id, user_message, and sage_response are required"]
            )

        timestamp = params.get("timestamp", self._now_iso())
        turn_number = params.get("turn_number", 0)

        # Generate memory ID
        ts_suffix = timestamp.replace(":", "").replace("-", "").replace("T", "_")[:15]
        entity_id = f"memory_{conversation_id}_{ts_suffix}"

        structured = {
            "conversation_id": conversation_id,
            "timestamp": timestamp,
            "turn_number": turn_number,
            "user_message": user_message,
            "sage_response": sage_response,
        }

        analyzed = {
            "memory_type": "exchange",
            "importance": "normal",
            "facts_extracted": [],
            "entities_mentioned": [],
        }

        # Extract facts if requested
        if params.get("extract_facts", True):
            try:
                facts_result = await self._extract_facts({
                    "user_message": user_message,
                    "sage_response": sage_response,
                    "context": {"conversation_id": conversation_id}
                })
                if facts_result.success and facts_result.data.get("facts"):
                    analyzed["facts_extracted"] = facts_result.data["facts"]
                    analyzed["entities_mentioned"] = list(set(
                        entity
                        for fact in facts_result.data["facts"]
                        for entity in fact.get("entities_mentioned", [])
                    ))
                    # Upgrade importance if significant facts found
                    if any(f.get("confidence", 0) > 0.8 for f in facts_result.data["facts"]):
                        analyzed["importance"] = "high"
            except Exception as e:
                logger.warning(f"Fact extraction failed for memory: {e}")

        entity = IndexedEntity(
            id=entity_id,
            entity_type="memory",
            source="conversation",
            structured=structured,
            analyzed=analyzed,
            relationships={
                "conversation_id": conversation_id,
            },
            embeddings={},
            metadata={
                "indexed_at": self._now_iso(),
                "index_version": 1
            }
        )

        stored_id = await self.data_layer.store_entity(entity)

        logger.info(f"Indexed memory {stored_id} with {len(analyzed.get('facts_extracted', []))} facts")

        return AgentResult(
            success=True,
            data={
                "entity_id": stored_id,
                "conversation_id": conversation_id,
                "facts_extracted": len(analyzed.get("facts_extracted", [])),
                "importance": analyzed.get("importance"),
                "indexed": True
            }
        )

    # =========================================================================
    # Fact Extraction
    # =========================================================================

    async def _extract_facts(self, params: dict) -> AgentResult:
        """
        Extract facts, decisions, preferences from conversation.

        Uses Claude to analyze conversation text and extract structured information.

        Expected params:
            user_message: str - The user's message
            sage_response: str - Sage's response
            context: dict (optional) - Additional context
        """
        user_message = params.get("user_message", "")
        sage_response = params.get("sage_response", "")

        if not user_message and not sage_response:
            return AgentResult(
                success=False,
                data={},
                errors=["user_message or sage_response is required"]
            )

        # Skip extraction for very short exchanges
        if len(user_message) + len(sage_response) < 50:
            return AgentResult(
                success=True,
                data={"facts": [], "skipped": True, "reason": "too_short"}
            )

        try:
            claude = await self._get_claude()

            prompt = self.FACT_EXTRACTION_PROMPT.format(
                user_message=user_message,
                sage_response=sage_response
            )

            response = await claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse JSON response
            response_text = response.content[0].text.strip()

            # Handle markdown code blocks
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            import json
            facts = json.loads(response_text)

            # Validate and filter facts
            valid_facts = []
            for fact in facts:
                if isinstance(fact, dict) and fact.get("content"):
                    valid_facts.append({
                        "type": fact.get("type", "fact"),
                        "content": fact["content"],
                        "confidence": float(fact.get("confidence", 0.5)),
                        "entities_mentioned": fact.get("entities_mentioned", [])
                    })

            return AgentResult(
                success=True,
                data={
                    "facts": valid_facts,
                    "count": len(valid_facts)
                }
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse fact extraction response: {e}")
            return AgentResult(
                success=True,
                data={"facts": [], "parse_error": str(e)}
            )
        except Exception as e:
            logger.error(f"Fact extraction error: {e}")
            return AgentResult(
                success=False,
                data={},
                errors=[f"Fact extraction failed: {str(e)}"]
            )

    # =========================================================================
    # Fact Supersession
    # =========================================================================

    async def _supersede_fact(self, params: dict) -> AgentResult:
        """
        Mark an old fact as superseded by a new one.

        This is used when new information corrects or updates
        previously stored facts. Both facts are retained for audit trail.

        Expected params:
            old_fact_id: str - ID of the fact being superseded
            new_fact_id: str - ID of the new fact
            reason: str (optional) - Reason for supersession
        """
        old_fact_id = params.get("old_fact_id")
        new_fact_id = params.get("new_fact_id")
        reason = params.get("reason", "")

        if not old_fact_id or not new_fact_id:
            return AgentResult(
                success=False,
                data={},
                errors=["old_fact_id and new_fact_id are required"]
            )

        # Update old fact metadata
        old_update_success = await self.data_layer.update_entity(old_fact_id, {
            "metadata": {
                "superseded_by": new_fact_id,
                "superseded_at": self._now_iso(),
                "supersession_reason": reason,
                "is_current": False
            }
        })

        if not old_update_success:
            return AgentResult(
                success=False,
                data={},
                errors=[f"Old fact {old_fact_id} not found"]
            )

        # Update new fact metadata
        await self.data_layer.update_entity(new_fact_id, {
            "metadata": {
                "supersedes": old_fact_id,
                "is_current": True
            }
        })

        # Create supersession relationship
        await self.data_layer.create_relationship(
            from_id=new_fact_id,
            to_id=old_fact_id,
            rel_type="supersedes",
            metadata={"reason": reason, "superseded_at": self._now_iso()}
        )

        logger.info(f"Fact {old_fact_id} superseded by {new_fact_id}")

        return AgentResult(
            success=True,
            data={
                "old_fact_id": old_fact_id,
                "new_fact_id": new_fact_id,
                "reason": reason,
                "superseded": True
            }
        )

    # =========================================================================
    # Meeting Indexing
    # =========================================================================

    async def _index_meeting(self, params: dict) -> AgentResult:
        """
        Process meeting transcript.

        Expected params:
            meeting_id: str (optional) - Fireflies or custom ID
            title: str
            date: str (ISO format)
            participants: list[str] - Email addresses
            transcript: str (optional)
            summary: str (optional)
            action_items: list[dict] (optional)
            source: str (optional) - "fireflies", "plaud", "manual"
        """
        title = params.get("title")
        date = params.get("date")
        participants = params.get("participants", [])

        if not title:
            return AgentResult(
                success=False,
                data={},
                errors=["title is required for meeting"]
            )

        meeting_id = params.get("meeting_id", uuid.uuid4().hex[:12])
        entity_id = f"meeting_{meeting_id}"

        structured = {
            "meeting_id": meeting_id,
            "title": title,
            "date": date or self._now_iso(),
            "participants": participants,
            "transcript": params.get("transcript"),
            "duration_minutes": params.get("duration_minutes"),
        }

        analyzed = {}
        if params.get("summary"):
            analyzed["summary"] = params["summary"]
        if params.get("action_items"):
            analyzed["action_items"] = params["action_items"]

        entity = IndexedEntity(
            id=entity_id,
            entity_type="meeting",
            source=params.get("source", "manual"),
            structured=structured,
            analyzed=analyzed,
            relationships={},
            embeddings={},
            metadata={
                "indexed_at": self._now_iso(),
                "index_version": 1
            }
        )

        stored_id = await self.data_layer.store_entity(entity)

        # Create relationships to participant contacts
        for participant_email in participants:
            contact_id = f"contact_{participant_email.lower().replace('@', '_at_').replace('.', '_')}"
            await self.data_layer.create_relationship(
                from_id=stored_id,
                to_id=contact_id,
                rel_type="has_participant"
            )

        logger.info(f"Indexed meeting {stored_id}")

        return AgentResult(
            success=True,
            data={
                "entity_id": stored_id,
                "meeting_id": meeting_id,
                "title": title,
                "participants": len(participants),
                "indexed": True
            }
        )

    # =========================================================================
    # Event Indexing
    # =========================================================================

    async def _index_event(self, params: dict) -> AgentResult:
        """
        Process calendar event.

        Expected params:
            event_id: str (optional) - Google Calendar event ID
            title: str
            start_time: str (ISO format)
            end_time: str (ISO format)
            location: str (optional)
            description: str (optional)
            attendees: list[str] (optional) - Email addresses
            calendar_id: str (optional)
        """
        title = params.get("title")
        start_time = params.get("start_time")

        if not title or not start_time:
            return AgentResult(
                success=False,
                data={},
                errors=["title and start_time are required for event"]
            )

        event_id = params.get("event_id", uuid.uuid4().hex[:12])
        entity_id = f"event_{event_id}"

        structured = {
            "event_id": event_id,
            "title": title,
            "start_time": start_time,
            "end_time": params.get("end_time"),
            "location": params.get("location"),
            "description": params.get("description"),
            "attendees": params.get("attendees", []),
            "calendar_id": params.get("calendar_id", "primary"),
            "is_all_day": params.get("is_all_day", False),
        }

        entity = IndexedEntity(
            id=entity_id,
            entity_type="event",
            source="calendar",
            structured=structured,
            analyzed={},
            relationships={},
            embeddings={},
            metadata={
                "indexed_at": self._now_iso(),
                "index_version": 1
            }
        )

        stored_id = await self.data_layer.store_entity(entity)

        # Create relationships to attendee contacts
        for attendee_email in params.get("attendees", []):
            contact_id = f"contact_{attendee_email.lower().replace('@', '_at_').replace('.', '_')}"
            await self.data_layer.create_relationship(
                from_id=stored_id,
                to_id=contact_id,
                rel_type="has_attendee"
            )

        logger.info(f"Indexed event {stored_id}")

        return AgentResult(
            success=True,
            data={
                "entity_id": stored_id,
                "event_id": event_id,
                "title": title,
                "start_time": start_time,
                "indexed": True
            }
        )

    # =========================================================================
    # Document Indexing (Stub)
    # =========================================================================

    async def _index_document(self, params: dict) -> AgentResult:
        """
        Process document from Drive.

        This is a stub implementation - full Google Drive integration
        is planned for a future phase.

        Expected params:
            drive_file_id: str
            file_name: str
            mime_type: str (optional)
            content: str (optional) - Extracted text content
        """
        drive_file_id = params.get("drive_file_id")
        file_name = params.get("file_name")

        if not drive_file_id or not file_name:
            return AgentResult(
                success=False,
                data={},
                errors=["drive_file_id and file_name are required"]
            )

        entity_id = f"document_{drive_file_id}"

        structured = {
            "drive_file_id": drive_file_id,
            "file_name": file_name,
            "mime_type": params.get("mime_type"),
            "content": params.get("content"),
        }

        entity = IndexedEntity(
            id=entity_id,
            entity_type="document",
            source="drive",
            structured=structured,
            analyzed={},
            relationships={},
            embeddings={},
            metadata={
                "indexed_at": self._now_iso(),
                "index_version": 1
            }
        )

        stored_id = await self.data_layer.store_entity(entity)

        logger.info(f"Indexed document {stored_id}")

        return AgentResult(
            success=True,
            data={
                "entity_id": stored_id,
                "drive_file_id": drive_file_id,
                "file_name": file_name,
                "indexed": True
            }
        )
