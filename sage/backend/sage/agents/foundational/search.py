"""
Search Agent - Context Retrieval for All Agents.

The Search Agent is the bridge between the Data Layer and Sub-Agents.
It retrieves relevant context for any task:
- Semantic search across embeddings
- Task-based context retrieval
- Agent-specific context enrichment
- Memory retrieval for conversation continuity
- Relationship traversal

See sage-agent-architecture.md Section 3.1 for specifications.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ..base import (
    BaseAgent,
    AgentResult,
    AgentType,
    SearchContext,
    DataLayerInterface,
    SearchResult,
    IndexedEntity,
)

logger = logging.getLogger(__name__)


class SearchAgent(BaseAgent):
    """
    The Search Agent retrieves relevant context for any sub-agent task.

    This is the single point of data access for all sub-agents. When an
    agent needs context to perform a task, it requests it through the
    Search Agent rather than accessing databases directly.

    Capabilities:
        - search_for_task: Get context package for an agent task
        - semantic_search: Vector similarity search
        - entity_lookup: Find specific entities by ID or attributes
        - relationship_traverse: Follow entity relationships
        - temporal_search: Find entities by time range
        - get_relevant_memories: Retrieve conversation memories
    """

    name = "search"
    description = "Retrieves relevant context from the Data Layer for agent tasks"
    agent_type = AgentType.FOUNDATIONAL
    capabilities = [
        "search_for_task",
        "semantic_search",
        "entity_lookup",
        "relationship_traverse",
        "temporal_search",
        "get_relevant_memories",
    ]

    def __init__(self, data_layer: DataLayerInterface):
        """
        Initialize the Search Agent.

        Args:
            data_layer: The data layer interface for read operations
        """
        # Search agent doesn't need search/indexer refs - it IS the search agent
        super().__init__(search_agent=None, indexer_agent=None)
        self.search = self  # Self-reference for compatibility
        self.data_layer = data_layer

    async def execute(
        self,
        capability: str,
        params: dict[str, Any],
        context: SearchContext | None = None
    ) -> AgentResult:
        """
        Execute a search capability.

        Args:
            capability: The capability to invoke
            params: Parameters for the capability
            context: Not typically used by Search Agent

        Returns:
            AgentResult with search results
        """
        self._validate_capability(capability)

        try:
            if capability == "search_for_task":
                ctx = await self.search_for_task(**params)
                return AgentResult(success=True, data={"context": ctx})

            elif capability == "semantic_search":
                results = await self.semantic_search(**params)
                return AgentResult(success=True, data={"results": results})

            elif capability == "entity_lookup":
                entity = await self.entity_lookup(**params)
                return AgentResult(success=True, data={"entity": entity})

            elif capability == "relationship_traverse":
                related = await self.relationship_traverse(**params)
                return AgentResult(success=True, data={"related": related})

            elif capability == "temporal_search":
                results = await self.temporal_search(**params)
                return AgentResult(success=True, data={"results": results})

            elif capability == "get_relevant_memories":
                ctx = await self.get_relevant_memories(**params)
                return AgentResult(success=True, data={"context": ctx})

            else:
                return AgentResult(
                    success=False,
                    data={},
                    errors=[f"Unknown capability: {capability}"]
                )
        except Exception as e:
            logger.exception(f"Search error in capability '{capability}'")
            return AgentResult(
                success=False,
                data={},
                errors=[f"Search error: {str(e)}"]
            )

    async def search_for_task(
        self,
        requesting_agent: str,
        task_description: str,
        entity_hints: list[str] | None = None,
        max_results: int = 20
    ) -> SearchContext:
        """
        Get a context package tailored for an agent's task.

        This is the primary method agents use to get context. The Search
        Agent analyzes the task, determines what data would be relevant,
        and assembles a SearchContext package.

        Args:
            requesting_agent: Name of the agent requesting context
            task_description: Natural language description of the task
            entity_hints: Optional hints about relevant entities (IDs or keywords)
            max_results: Maximum results per entity type

        Returns:
            SearchContext with relevant data for the task
        """
        logger.info(
            f"Building context for agent '{requesting_agent}': {task_description[:100]}..."
        )

        context = SearchContext(
            retrieval_metadata={
                "requesting_agent": requesting_agent,
                "task_description": task_description,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # 1. Semantic search based on task description
        semantic_results = await self.semantic_search(
            query=task_description,
            entity_types=None,  # Search all types
            limit=max_results,
            score_threshold=0.3
        )

        # Categorize semantic results by type
        for result in semantic_results:
            entity = result.entity
            entity_dict = self._entity_to_dict(entity, result.score)

            if entity.entity_type == "email":
                context.relevant_emails.append(entity_dict)
            elif entity.entity_type == "contact":
                context.relevant_contacts.append(entity_dict)
            elif entity.entity_type == "followup":
                context.relevant_followups.append(entity_dict)
            elif entity.entity_type == "meeting":
                context.relevant_meetings.append(entity_dict)
            elif entity.entity_type == "memory":
                context.relevant_memories.append(entity_dict)

        # 2. If entity hints provided, fetch those directly
        if entity_hints:
            for hint in entity_hints:
                # Try to fetch as entity ID first
                entity = await self.data_layer.get_entity(hint)
                if entity:
                    entity_dict = self._entity_to_dict(entity)
                    self._add_entity_to_context(context, entity, entity_dict)

                    # Traverse relationships for this entity
                    relationships = await self.data_layer.get_relationships(hint)
                    for rel in relationships:
                        # Add to relationship graph
                        if hint not in context.relationship_graph:
                            context.relationship_graph[hint] = []
                        context.relationship_graph[hint].append({
                            "to": rel.to_id if rel.from_id == hint else rel.from_id,
                            "type": rel.rel_type,
                            "metadata": rel.metadata
                        })

        # 3. Agent-specific context enrichment
        await self._enrich_for_agent(context, requesting_agent, max_results)

        # 4. Generate temporal summary
        context.temporal_summary = await self._generate_temporal_summary(context)

        # Update metadata
        context.retrieval_metadata["entities_retrieved"] = (
            len(context.relevant_emails) +
            len(context.relevant_contacts) +
            len(context.relevant_followups) +
            len(context.relevant_meetings) +
            len(context.relevant_memories)
        )

        logger.info(
            f"Built context with {context.retrieval_metadata['entities_retrieved']} entities"
        )

        return context

    async def _enrich_for_agent(
        self,
        context: SearchContext,
        requesting_agent: str,
        max_results: int
    ) -> None:
        """Add agent-specific context enrichment."""

        if requesting_agent == "chat":
            # Chat gets comprehensive context - emails, followups, contacts
            # This is the main interface for user interaction

            # Get recent/unread emails
            try:
                emails = await self.data_layer.structured_query(
                    filters={"is_unread": True},
                    entity_type="email",
                    limit=max_results
                )
                for entity in emails:
                    if not self._entity_in_list(entity.id, context.relevant_emails):
                        context.relevant_emails.append(self._entity_to_dict(entity))
            except Exception as e:
                logger.warning(f"Error fetching emails for chat: {e}")

            # Get active/overdue follow-ups
            try:
                followups = await self.data_layer.structured_query(
                    filters={"status": ["pending", "reminded", "escalated"]},
                    entity_type="followup",
                    limit=max_results
                )
                for entity in followups:
                    if not self._entity_in_list(entity.id, context.relevant_followups):
                        context.relevant_followups.append(self._entity_to_dict(entity))
            except Exception as e:
                logger.warning(f"Error fetching followups for chat: {e}")

            # Get recent contacts (contacts are populated via semantic search results)
            # No additional contact fetch needed here as they come from semantic search

        elif requesting_agent == "followup":
            # Get active follow-ups
            followups = await self.data_layer.structured_query(
                filters={"status": ["pending", "reminded", "escalated"]},
                entity_type="followup",
                limit=max_results
            )
            for entity in followups:
                if not self._entity_in_list(entity.id, context.relevant_followups):
                    context.relevant_followups.append(self._entity_to_dict(entity))

        elif requesting_agent == "email":
            # Get recent unread emails
            emails = await self.data_layer.structured_query(
                filters={"is_unread": True},
                entity_type="email",
                limit=max_results
            )
            for entity in emails:
                if not self._entity_in_list(entity.id, context.relevant_emails):
                    context.relevant_emails.append(self._entity_to_dict(entity))

        elif requesting_agent == "briefing":
            # Get comprehensive briefing context
            # Recent high-priority emails
            emails = await self.data_layer.structured_query(
                filters={"priority": ["urgent", "high"]},
                entity_type="email",
                limit=10
            )
            for entity in emails:
                if not self._entity_in_list(entity.id, context.relevant_emails):
                    context.relevant_emails.append(self._entity_to_dict(entity))

            # Overdue follow-ups
            followups = await self.data_layer.structured_query(
                filters={"status": ["pending", "reminded", "escalated"]},
                entity_type="followup",
                limit=10
            )
            for entity in followups:
                if not self._entity_in_list(entity.id, context.relevant_followups):
                    context.relevant_followups.append(self._entity_to_dict(entity))

        elif requesting_agent == "meeting":
            # Get recent meetings
            meetings = await self.data_layer.structured_query(
                filters={},
                entity_type="meeting",
                limit=max_results
            )
            for entity in meetings:
                if not self._entity_in_list(entity.id, context.relevant_meetings):
                    context.relevant_meetings.append(self._entity_to_dict(entity))

    async def _generate_temporal_summary(self, context: SearchContext) -> str:
        """Generate a natural language summary of temporal context."""
        parts = []

        if context.relevant_emails:
            parts.append(f"{len(context.relevant_emails)} relevant emails")

        if context.relevant_followups:
            parts.append(f"{len(context.relevant_followups)} follow-ups")

        if context.relevant_meetings:
            parts.append(f"{len(context.relevant_meetings)} meetings")

        if context.relevant_contacts:
            parts.append(f"{len(context.relevant_contacts)} contacts")

        if parts:
            return f"Context includes: {', '.join(parts)}"
        return "No temporal context available"

    def _entity_to_dict(
        self,
        entity: IndexedEntity,
        score: float | None = None
    ) -> dict:
        """Convert an IndexedEntity to a dict for context."""
        result = {
            "id": entity.id,
            "entity_type": entity.entity_type,
            "source": entity.source,
            **entity.structured,
            **entity.analyzed,
        }
        if score is not None:
            result["relevance_score"] = score
        return result

    def _add_entity_to_context(
        self,
        context: SearchContext,
        entity: IndexedEntity,
        entity_dict: dict
    ) -> None:
        """Add an entity to the appropriate context list."""
        if entity.entity_type == "email":
            if not self._entity_in_list(entity.id, context.relevant_emails):
                context.relevant_emails.append(entity_dict)
        elif entity.entity_type == "contact":
            if not self._entity_in_list(entity.id, context.relevant_contacts):
                context.relevant_contacts.append(entity_dict)
        elif entity.entity_type == "followup":
            if not self._entity_in_list(entity.id, context.relevant_followups):
                context.relevant_followups.append(entity_dict)
        elif entity.entity_type == "meeting":
            if not self._entity_in_list(entity.id, context.relevant_meetings):
                context.relevant_meetings.append(entity_dict)
        elif entity.entity_type == "memory":
            if not self._entity_in_list(entity.id, context.relevant_memories):
                context.relevant_memories.append(entity_dict)

    def _entity_in_list(self, entity_id: str, entity_list: list[dict]) -> bool:
        """Check if an entity is already in a list."""
        return any(e.get("id") == entity_id for e in entity_list)

    async def semantic_search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        limit: int = 10,
        score_threshold: float = 0.3
    ) -> list[SearchResult]:
        """
        Perform semantic similarity search.

        Args:
            query: Natural language query
            entity_types: Filter by entity types (email, contact, etc.)
            limit: Maximum number of results
            score_threshold: Minimum similarity score

        Returns:
            List of SearchResult ordered by relevance
        """
        results = await self.data_layer.vector_search(
            query=query,
            entity_types=entity_types,
            limit=limit
        )

        # Filter by score threshold
        return [r for r in results if r.score >= score_threshold]

    async def entity_lookup(
        self,
        entity_id: str | None = None,
        entity_type: str | None = None,
        filters: dict | None = None
    ) -> dict | list[dict] | None:
        """
        Look up specific entities by ID or attributes.

        Args:
            entity_id: Specific entity ID to retrieve
            entity_type: Type of entity to search
            filters: Attribute filters for structured query

        Returns:
            Single entity dict, list of entities, or None
        """
        if entity_id:
            entity = await self.data_layer.get_entity(entity_id)
            if entity:
                return self._entity_to_dict(entity)
            return None

        if entity_type and filters:
            entities = await self.data_layer.structured_query(
                filters=filters,
                entity_type=entity_type
            )
            return [self._entity_to_dict(e) for e in entities]

        return None

    async def relationship_traverse(
        self,
        entity_id: str,
        rel_types: list[str] | None = None,
        depth: int = 1
    ) -> list[dict]:
        """
        Traverse relationships from an entity.

        Args:
            entity_id: Starting entity
            rel_types: Filter by relationship types
            depth: How many levels to traverse (currently only supports depth=1)

        Returns:
            List of related entity dicts with relationship info
        """
        relationships = await self.data_layer.get_relationships(
            entity_id=entity_id,
            rel_types=rel_types
        )

        related = []
        for rel in relationships:
            # Get the related entity
            related_id = rel.to_id if rel.from_id == entity_id else rel.from_id
            entity = await self.data_layer.get_entity(related_id)

            if entity:
                entity_dict = self._entity_to_dict(entity)
                entity_dict["relationship"] = {
                    "type": rel.rel_type,
                    "direction": "outgoing" if rel.from_id == entity_id else "incoming",
                    "metadata": rel.metadata
                }
                related.append(entity_dict)

        return related

    async def temporal_search(
        self,
        start_time: str | datetime,
        end_time: str | datetime,
        entity_types: list[str] | None = None,
        limit: int = 50
    ) -> list[dict]:
        """
        Find entities within a time range.

        Args:
            start_time: Start of time range (ISO format string or datetime)
            end_time: End of time range (ISO format string or datetime)
            entity_types: Filter by entity types

        Returns:
            List of entities in the time range
        """
        # Parse times if strings
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        results = []

        # Search each entity type
        types_to_search = entity_types or ["email", "meeting", "followup"]

        for entity_type in types_to_search:
            # Build time-based filter
            filters = {
                "date_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                }
            }

            entities = await self.data_layer.structured_query(
                filters=filters,
                entity_type=entity_type,
                limit=limit
            )

            for entity in entities:
                results.append(self._entity_to_dict(entity))

        return results

    async def get_relevant_memories(
        self,
        query: str,
        conversation_id: str | None = None,
        limit: int = 10
    ) -> SearchContext:
        """
        Retrieve relevant conversation memories.

        This is used by the orchestrator to provide conversation
        continuity and recall of past discussions.

        Args:
            query: Current query to find relevant memories for
            conversation_id: Optional - filter to specific conversation
            limit: Maximum memories to retrieve

        Returns:
            SearchContext with relevant_memories populated
        """
        context = SearchContext(
            retrieval_metadata={
                "query": query,
                "conversation_id": conversation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Search for relevant memories using semantic search
        results = await self.data_layer.vector_search(
            query=query,
            entity_types=["memory"],
            limit=limit
        )

        for result in results:
            context.relevant_memories.append(
                self._entity_to_dict(result.entity, result.score)
            )

        # If conversation_id provided, also get recent memories from that conversation
        if conversation_id:
            conversation_memories = await self.data_layer.structured_query(
                filters={"conversation_id": conversation_id},
                entity_type="memory",
                limit=limit
            )

            for entity in conversation_memories:
                if not self._entity_in_list(entity.id, context.relevant_memories):
                    context.relevant_memories.append(self._entity_to_dict(entity))

        return context

    async def get_contact_context(self, email: str) -> dict:
        """
        Get comprehensive context about a contact.

        Combines entity lookup and relationship traversal to build
        a full picture of a contact and their interactions.

        Args:
            email: Contact's email address

        Returns:
            Dict with contact info, recent emails, meetings, follow-ups
        """
        result = {
            "contact": None,
            "recent_emails": [],
            "meetings": [],
            "followups": [],
            "total_interactions": 0,
        }

        # Look up the contact
        contacts = await self.data_layer.structured_query(
            filters={"email": email},
            entity_type="contact",
            limit=1
        )

        if contacts:
            contact = contacts[0]
            result["contact"] = self._entity_to_dict(contact)

            # Get related entities via relationships
            related = await self.relationship_traverse(
                entity_id=contact.id,
                depth=1
            )

            for entity_dict in related:
                entity_type = entity_dict.get("entity_type")
                if entity_type == "email":
                    result["recent_emails"].append(entity_dict)
                elif entity_type == "meeting":
                    result["meetings"].append(entity_dict)
                elif entity_type == "followup":
                    result["followups"].append(entity_dict)

        # Also search for emails from this sender
        emails = await self.data_layer.structured_query(
            filters={"sender_email": email},
            entity_type="email",
            limit=20
        )

        for entity in emails:
            entity_dict = self._entity_to_dict(entity)
            if not self._entity_in_list(entity.id, result["recent_emails"]):
                result["recent_emails"].append(entity_dict)

        result["total_interactions"] = (
            len(result["recent_emails"]) +
            len(result["meetings"]) +
            len(result["followups"])
        )

        return result

    async def get_thread_context(self, thread_id: str) -> dict:
        """
        Get full context for an email thread.

        Args:
            thread_id: Gmail thread ID

        Returns:
            Dict with thread emails, participants, related follow-ups
        """
        result = {
            "thread_id": thread_id,
            "emails": [],
            "participants": [],
            "followups": [],
            "summary": "",
        }

        # Get all emails in thread
        emails = await self.data_layer.structured_query(
            filters={"thread_id": thread_id},
            entity_type="email",
            limit=100
        )

        participant_emails = set()

        for entity in emails:
            entity_dict = self._entity_to_dict(entity)
            result["emails"].append(entity_dict)

            # Collect participants
            sender = entity.structured.get("sender_email")
            if sender:
                participant_emails.add(sender)

            to_emails = entity.structured.get("to_emails", [])
            if to_emails:
                participant_emails.update(to_emails)

        # Sort emails by date
        result["emails"].sort(
            key=lambda e: e.get("received_at", ""),
            reverse=False
        )

        # Get participant contact info
        for email_addr in participant_emails:
            contacts = await self.data_layer.structured_query(
                filters={"email": email_addr},
                entity_type="contact",
                limit=1
            )
            if contacts:
                result["participants"].append(self._entity_to_dict(contacts[0]))
            else:
                result["participants"].append({"email": email_addr})

        # Check for related follow-ups
        followups = await self.data_layer.structured_query(
            filters={"thread_id": thread_id},
            entity_type="followup",
            limit=10
        )

        for entity in followups:
            result["followups"].append(self._entity_to_dict(entity))

        # Generate summary
        if result["emails"]:
            first_email = result["emails"][0]
            last_email = result["emails"][-1]
            result["summary"] = (
                f"Thread with {len(result['emails'])} emails, "
                f"{len(result['participants'])} participants. "
                f"Subject: {first_email.get('subject', 'No subject')}"
            )

        return result
