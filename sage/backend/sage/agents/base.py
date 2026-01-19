"""
Base classes for the Sage Agent System.

This module defines the core abstractions that all agents implement:
- AgentResult: Standard response from any agent
- SearchContext: Context package provided to agents by Search Agent
- DataLayerInterface: Abstract interface for Data Layer access
- BaseAgent: Abstract base class for all agents

See sage-agent-architecture.md Section 3.3 for specifications.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from .foundational.search import SearchAgent
    from .foundational.indexer import IndexerAgent


class AgentType(Enum):
    """Types of agents in the system."""
    FOUNDATIONAL = "foundational"
    TASK = "task"
    ORCHESTRATOR = "orchestrator"


@dataclass
class AgentResult:
    """
    Standard result from any agent.

    All agents return this structure to ensure consistent handling
    by the orchestrator.
    """
    success: bool
    data: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: float = 1.0

    # Data to persist (sent to Indexer Agent)
    entities_to_index: list[dict] = field(default_factory=list)

    # Human approval needed?
    requires_approval: bool = False
    approval_context: str | None = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.entities_to_index is None:
            self.entities_to_index = []


@dataclass
class SearchContext:
    """
    Context package provided to agents by Search Agent.

    When an agent needs context to perform a task, it requests this
    from the Search Agent. The Search Agent queries the Data Layer
    and returns a rich context package.
    """
    # Entity collections
    relevant_emails: list[dict] = field(default_factory=list)
    relevant_contacts: list[dict] = field(default_factory=list)
    relevant_followups: list[dict] = field(default_factory=list)
    relevant_meetings: list[dict] = field(default_factory=list)
    relevant_events: list[dict] = field(default_factory=list)
    relevant_memories: list[dict] = field(default_factory=list)

    # Relationship information
    relationship_graph: dict = field(default_factory=dict)

    # Temporal summary (natural language overview of time-based context)
    temporal_summary: str = ""

    # Metadata
    total_tokens: int = 0
    retrieval_metadata: dict = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Check if context contains any data."""
        return not any([
            self.relevant_emails,
            self.relevant_contacts,
            self.relevant_followups,
            self.relevant_meetings,
            self.relevant_events,
            self.relevant_memories,
        ])


@dataclass
class IndexedEntity:
    """
    Represents an entity stored in the Data Layer.

    Used by DataLayerInterface for storage operations.
    """
    id: str
    entity_type: str
    source: str
    structured: dict = field(default_factory=dict)
    analyzed: dict = field(default_factory=dict)
    relationships: dict = field(default_factory=dict)
    embeddings: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    """Result from a vector or structured search."""
    entity: IndexedEntity
    score: float
    match_type: str  # "semantic", "keyword", "structured"


@dataclass
class Relationship:
    """A relationship between two entities."""
    from_id: str
    to_id: str
    rel_type: str
    metadata: dict = field(default_factory=dict)


class DataLayerInterface(ABC):
    """
    Abstract interface for Data Layer access.

    This is implemented by the services layer and injected into agents.
    The Indexer Agent uses write operations; the Search Agent uses read operations.
    """

    # Write operations (used by Indexer Agent)
    @abstractmethod
    async def store_entity(self, entity: IndexedEntity) -> str:
        """Store an entity and return its ID."""
        pass

    @abstractmethod
    async def update_entity(self, entity_id: str, updates: dict) -> bool:
        """Update an existing entity."""
        pass

    @abstractmethod
    async def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity from all stores."""
        pass

    @abstractmethod
    async def create_relationship(
        self, from_id: str, to_id: str, rel_type: str, metadata: dict | None = None
    ) -> bool:
        """Create a relationship between two entities."""
        pass

    # Read operations (used by Search Agent)
    @abstractmethod
    async def get_entity(self, entity_id: str) -> IndexedEntity | None:
        """Retrieve a single entity by ID."""
        pass

    @abstractmethod
    async def vector_search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        limit: int = 10
    ) -> list[SearchResult]:
        """Perform semantic search across entity embeddings."""
        pass

    @abstractmethod
    async def structured_query(
        self,
        filters: dict,
        entity_type: str,
        limit: int = 100
    ) -> list[IndexedEntity]:
        """Query entities by structured fields."""
        pass

    @abstractmethod
    async def get_relationships(
        self,
        entity_id: str,
        rel_types: list[str] | None = None
    ) -> list[Relationship]:
        """Get relationships for an entity."""
        pass


class BaseAgent(ABC):
    """
    Base class for all Sage agents.

    All agents (foundational and task) inherit from this class.
    It provides:
    - Access to Search Agent for context retrieval
    - Access to Indexer Agent for data persistence
    - Standard execute() interface
    - Capability declaration

    Subclasses must implement:
    - name: str
    - description: str
    - capabilities: list[str]
    - execute(): The main entry point for agent actions
    """

    name: str
    description: str
    capabilities: list[str]
    agent_type: AgentType

    def __init__(
        self,
        search_agent: "SearchAgent | None" = None,
        indexer_agent: "IndexerAgent | None" = None
    ):
        """
        Initialize the agent with references to foundational agents.

        Args:
            search_agent: The Search Agent for context retrieval
            indexer_agent: The Indexer Agent for data persistence
        """
        self.search = search_agent
        self.indexer = indexer_agent
        self.claude_client = None  # Injected by orchestrator if needed

    @abstractmethod
    async def execute(
        self,
        capability: str,
        params: dict[str, Any],
        context: SearchContext | None = None
    ) -> AgentResult:
        """
        Execute a capability with given parameters.

        This is the main entry point for all agent actions. The orchestrator
        calls this method to invoke agent capabilities.

        Args:
            capability: The capability to invoke (must be in self.capabilities)
            params: Parameters for the capability
            context: Optional pre-fetched context. If not provided, agent
                     will request context from Search Agent.

        Returns:
            AgentResult with the outcome of the operation

        Raises:
            ValueError: If capability is not supported
        """
        pass

    def supports_capability(self, capability: str) -> bool:
        """Check if this agent supports a given capability."""
        return capability in self.capabilities

    async def get_context(
        self,
        task_description: str,
        hints: list[str] | None = None
    ) -> SearchContext:
        """
        Request context from Search Agent.

        Convenience method for agents to get the context they need.

        Args:
            task_description: Natural language description of what agent needs
            hints: Optional entity hints (IDs, names, etc.) to guide search

        Returns:
            SearchContext with relevant data for the task
        """
        if self.search is None:
            return SearchContext()  # Empty context if no search agent

        return await self.search.search_for_task(
            requesting_agent=self.name,
            task_description=task_description,
            entity_hints=hints
        )

    async def persist_data(self, entities: list[dict]) -> list[str]:
        """
        Send data to Indexer Agent for persistence.

        Convenience method for agents to persist new or updated data.

        Args:
            entities: List of entity dicts to index

        Returns:
            List of entity IDs that were indexed
        """
        if self.indexer is None:
            return []

        indexed_ids = []
        for entity in entities:
            entity_id = await self.indexer.index_entity(entity)
            indexed_ids.append(entity_id)

        return indexed_ids

    def _validate_capability(self, capability: str) -> None:
        """Raise ValueError if capability is not supported."""
        if not self.supports_capability(capability):
            raise ValueError(
                f"Agent '{self.name}' does not support capability '{capability}'. "
                f"Supported capabilities: {self.capabilities}"
            )
