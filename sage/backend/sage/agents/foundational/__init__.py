"""
Foundational Agents for the Sage Agent System.

Foundational agents bridge the Data Layer and Sub-Agent Layer:
- IndexerAgent: Ingests and optimizes data for retrieval
- SearchAgent: Retrieves relevant context for any sub-agent task

These agents are used by all task agents and the orchestrator.
"""

from .indexer import IndexerAgent
from .search import SearchAgent

__all__ = ["IndexerAgent", "SearchAgent"]
