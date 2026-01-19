"""
Task Agents for the Sage Agent System.

Task agents are specialized workers that perform discrete tasks:
- EmailAgent: Analyzes emails, identifies actions, prioritizes
- FollowUpAgent: Tracks and manages follow-up items
- MeetingAgent: Prepares meeting summaries and action items
- CalendarAgent: Manages calendar, detects conflicts, suggests times
- BriefingAgent: Generates daily briefings and weekly reviews
- DraftAgent: Writes content in Dave's voice
- PropertyAgent: Handles property-specific queries
- ResearchAgent: Gathers information from external sources

All task agents inherit from BaseAgent and receive context from SearchAgent.
"""

from .email import EmailAgent
from .followup import FollowUpAgent
from .meeting import MeetingAgent
from .calendar import CalendarAgent
from .briefing import BriefingAgent
from .draft import DraftAgent
from .property import PropertyAgent
from .research import ResearchAgent

__all__ = [
    "EmailAgent",
    "FollowUpAgent",
    "MeetingAgent",
    "CalendarAgent",
    "BriefingAgent",
    "DraftAgent",
    "PropertyAgent",
    "ResearchAgent",
]
