"""
Sage Multi-Agent System

This package implements the three-layer agent architecture:
- Layer 1 (Data Layer): IndexerAgent manages data ingestion and indexing
- Layer 2 (Sub-Agent Layer): Task agents + SearchAgent for context retrieval
- Layer 3 (Orchestrator Layer): SageOrchestrator coordinates agents

See sage-agent-architecture.md for detailed specifications.
"""

from .base import (
    BaseAgent,
    AgentResult,
    SearchContext,
    DataLayerInterface,
)

__all__ = [
    "BaseAgent",
    "AgentResult",
    "SearchContext",
    "DataLayerInterface",
]
