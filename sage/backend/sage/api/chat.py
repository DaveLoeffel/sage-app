"""Chat API endpoints for ad-hoc AI queries.

This module implements Phase 3.9: Context-Aware Chat (RAG Integration).
Before sending user messages to Claude, we retrieve relevant context from the
database using SearchAgent, preventing hallucination of non-existent data.

Phase 3.9.3 adds intent-based context optimization:
- Detect query type (email, followup, meeting, contact, todo, general)
- Extract entity hints (names, email addresses, subjects)
- Prioritize relevant context based on detected intent
"""

import logging
import re
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from sage.services.database import get_db
from sage.schemas.chat import ChatRequest, ChatResponse
from sage.core.claude_agent import get_claude_agent
from sage.services.data_layer.service import DataLayerService
from sage.agents.foundational.search import SearchAgent
from sage.agents.base import SearchContext
from sage.api.auth import get_current_user
from sage.models.user import User
from sage.config import get_settings
from sage.agents.orchestrator import SageOrchestrator, PendingApproval

settings = get_settings()

# Timezone constants
EASTERN_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")


def format_datetime_eastern(dt_value: str | datetime | None) -> str | None:
    """
    Convert a datetime value to Eastern Time formatted string.

    Args:
        dt_value: A datetime object, ISO format string, or None

    Returns:
        Formatted string like "Jan 27, 2026 3:30 PM ET" or None if input is None
    """
    if dt_value is None:
        return None

    try:
        # Parse string to datetime if needed
        if isinstance(dt_value, str):
            # Handle various ISO formats
            dt_value = dt_value.replace("Z", "+00:00")
            if "+" not in dt_value and "T" in dt_value:
                # Assume UTC if no timezone specified
                dt_value = dt_value + "+00:00"
            dt = datetime.fromisoformat(dt_value)
        else:
            dt = dt_value

        # If datetime is naive (no timezone), assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC_TZ)

        # Convert to Eastern Time
        dt_eastern = dt.astimezone(EASTERN_TZ)

        # Format as readable string
        return dt_eastern.strftime("%b %d, %Y %I:%M %p ET")

    except (ValueError, TypeError) as e:
        # If parsing fails, return original value as string
        return str(dt_value) if dt_value else None


logger = logging.getLogger(__name__)


def get_calendar_events_for_chat(
    user: User,
    days_ahead: int = 1,
    days_behind: int = 0,
) -> list[dict]:
    """
    Fetch calendar events from Google Calendar for chat context.

    Args:
        user: The current user with Google credentials
        days_ahead: Number of days ahead to fetch (default: 1 for today)
        days_behind: Number of days behind to fetch (default: 0)

    Returns:
        List of formatted calendar event dicts for chat context
    """
    if not user or not user.google_access_token:
        logger.debug("No Google access token, skipping calendar fetch")
        return []

    try:
        credentials = Credentials(
            token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )

        service = build("calendar", "v3", credentials=credentials)

        # Calculate time range
        now = datetime.now(EASTERN_TZ)
        start_time = (now - timedelta(days=days_behind)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_time = (now + timedelta(days=days_ahead)).replace(
            hour=23, minute=59, second=59, microsecond=0
        )

        # Convert to UTC for API call
        start_utc = start_time.astimezone(UTC_TZ)
        end_utc = end_time.astimezone(UTC_TZ)

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_utc.isoformat(),
                timeMax=end_utc.isoformat(),
                maxResults=20,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        calendar_events = []

        for event in events:
            # Handle all-day events vs timed events
            start = event.get("start", {})
            end = event.get("end", {})

            if "dateTime" in start:
                start_dt = datetime.fromisoformat(
                    start["dateTime"].replace("Z", "+00:00")
                )
            else:
                # All-day event
                start_dt = datetime.fromisoformat(start.get("date", ""))
                start_dt = start_dt.replace(hour=0, minute=0, tzinfo=EASTERN_TZ)

            if "dateTime" in end:
                end_dt = datetime.fromisoformat(
                    end["dateTime"].replace("Z", "+00:00")
                )
            else:
                end_dt = datetime.fromisoformat(end.get("date", ""))
                end_dt = end_dt.replace(hour=23, minute=59, tzinfo=EASTERN_TZ)

            # Extract attendees
            attendees = []
            for attendee in event.get("attendees", []):
                email = attendee.get("email", "")
                name = attendee.get("displayName", email)
                attendees.append(name if name else email)

            # Extract meeting link
            meeting_link = None
            conference_data = event.get("conferenceData", {})
            entry_points = conference_data.get("entryPoints", [])
            for entry in entry_points:
                if entry.get("entryPointType") == "video":
                    meeting_link = entry.get("uri")
                    break
            if not meeting_link:
                meeting_link = event.get("hangoutLink")

            calendar_events.append({
                "id": event.get("id", ""),
                "title": event.get("summary", "No Title"),
                "start": format_datetime_eastern(start_dt),
                "end": format_datetime_eastern(end_dt),
                "location": event.get("location"),
                "attendees": attendees[:10] if attendees else None,
                "description": (event.get("description") or "")[:200],
                "meeting_link": meeting_link,
                "is_all_day": "date" in start and "dateTime" not in start,
            })

        logger.info(f"Fetched {len(calendar_events)} calendar events for chat")
        return calendar_events

    except HttpError as e:
        logger.error(f"Google Calendar API error in chat: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching calendar events for chat: {e}")
        return []
router = APIRouter()


async def get_orchestrator(db: AsyncSession, user: User | None = None) -> SageOrchestrator:
    """
    Create and configure a SageOrchestrator instance.

    Args:
        db: Database session
        user: Optional user (for future user-specific configuration)

    Returns:
        Configured SageOrchestrator instance
    """
    data_layer = DataLayerService(session=db)
    orchestrator = SageOrchestrator(data_layer=data_layer)
    return orchestrator


class ChatIntent(str, Enum):
    """Types of user intents detected from chat messages."""
    EMAIL = "email"           # Questions about emails
    FOLLOWUP = "followup"     # Questions about followups
    MEETING = "meeting"       # Questions about meetings/calendar
    CONTACT = "contact"       # Questions about contacts/people
    TODO = "todo"             # Questions about todos/tasks
    GENERAL = "general"       # General questions


def detect_chat_intent(message: str) -> ChatIntent:
    """
    Detect the primary intent from a user message.

    Uses keyword matching to classify the query type, which determines
    how context retrieval is prioritized.

    Args:
        message: The user's chat message

    Returns:
        ChatIntent enum indicating the detected intent type
    """
    message_lower = message.lower()

    # Email-related patterns
    email_patterns = [
        r"\bemail", r"\bmail\b", r"\binbox\b", r"\bunread\b",
        r"\bsent\b", r"message from", r"\bwrote\b", r"\breply\b",
        r"\bforward\b", r"from .+@", r"subject:",
    ]

    # Follow-up related patterns
    followup_patterns = [
        r"follow.?up", r"\bwaiting\b", r"\boverdue\b", r"\bpending\b",
        r"waiting for.*(response|reply)", r"haven.t heard",
        r"need.*(response|reply)", r"remind\b", r"heard back",
    ]

    # Meeting/calendar related patterns
    meeting_patterns = [
        r"\bmeeting", r"\bcalendar\b", r"\bschedule\b", r"\bevent\b",
        r"\bcall\b", r"\bzoom\b", r"\bappointment\b", r"today's",
        r"tomorrow", r"this week", r"next week", r"\btranscript\b",
    ]

    # Contact/people related patterns
    contact_patterns = [
        r"who is", r"tell me about .+ (person|contact)",
        r"what do (i|you) know about", r"relationship with",
        r"contact info", r"how do i reach",
    ]

    # Todo/task related patterns
    todo_patterns = [
        r"\btodo", r"\bto.?do\b", r"\btask", r"action item",
        r"need to do", r"what should i", r"my tasks",
        r"what's on my plate",
    ]

    # Score each intent by counting pattern matches
    def count_matches(patterns: list[str], text: str) -> int:
        return sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))

    scores = {
        ChatIntent.EMAIL: count_matches(email_patterns, message_lower),
        ChatIntent.FOLLOWUP: count_matches(followup_patterns, message_lower),
        ChatIntent.MEETING: count_matches(meeting_patterns, message_lower),
        ChatIntent.CONTACT: count_matches(contact_patterns, message_lower),
        ChatIntent.TODO: count_matches(todo_patterns, message_lower),
    }

    # Return highest scoring intent, or GENERAL if no strong match
    max_score = max(scores.values())
    if max_score == 0:
        return ChatIntent.GENERAL

    return max(scores, key=scores.get)


def extract_entity_hints(message: str) -> list[str]:
    """
    Extract potential entity hints from a user message.

    Looks for:
    - Email addresses
    - Names (capitalized words that look like names)
    - Quoted strings (likely subjects or exact phrases)

    Args:
        message: The user's chat message

    Returns:
        List of extracted entity hints for search
    """
    hints = []

    # Extract email addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, message)
    hints.extend(emails)

    # Extract quoted strings (potential subjects or exact phrases)
    quoted_pattern = r'"([^"]+)"'
    quoted = re.findall(quoted_pattern, message)
    hints.extend(quoted)

    # Also check for single-quoted strings
    single_quoted_pattern = r"'([^']+)'"
    single_quoted = re.findall(single_quoted_pattern, message)
    hints.extend(single_quoted)

    # Extract potential names (2-3 capitalized words together)
    # Skip common words that might be capitalized at start of sentences
    # Extended list to avoid false positives from common English words
    common_words = {
        # Articles, pronouns, basic verbs
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'what', 'when', 'where', 'who', 'how', 'why', 'which', 'that', 'this',
        'can', 'could', 'would', 'should', 'will', 'shall', 'may', 'might',
        'do', 'does', 'did', 'have', 'has', 'had', 'i', 'my', 'me', 'we', 'us',
        'you', 'your', 'he', 'she', 'it', 'they', 'them', 'their', 'our',
        # Common action words that start sentences
        'show', 'tell', 'find', 'get', 'give', 'list', 'help', 'please',
        'let', 'make', 'see', 'look', 'check', 'search', 'display', 'view',
        # Common words that might be capitalized
        'hello', 'hi', 'hey', 'thanks', 'thank', 'yes', 'no', 'ok', 'okay',
        'summarize', 'summary', 'detail', 'details', 'more', 'first', 'last',
        'next', 'previous', 'one', 'two', 'three', 'all', 'any', 'some',
        'recent', 'new', 'old', 'latest', 'earliest', 'important', 'urgent',
        # Time-related
        'today', 'tomorrow', 'yesterday', 'monday', 'tuesday', 'wednesday',
        'thursday', 'friday', 'saturday', 'sunday', 'week', 'month', 'year',
        'morning', 'afternoon', 'evening', 'night', 'day', 'days',
        # Common nouns that aren't names
        'email', 'emails', 'message', 'messages', 'meeting', 'meetings',
        'calendar', 'task', 'tasks', 'todo', 'todos', 'followup', 'followups',
        'contact', 'contacts', 'schedule', 'inbox', 'draft', 'drafts',
    }

    # Pattern for potential names: REQUIRE 2+ capitalized words (not just 1)
    # Single capitalized words are usually not names
    name_pattern = r'\b([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'
    potential_names = re.findall(name_pattern, message)

    for name in potential_names:
        # Skip if all words are common words
        words = name.lower().split()
        if not all(w in common_words for w in words):
            hints.append(name)

    # Extract "from X" patterns (e.g., "emails from John")
    from_pattern = r'from\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
    from_matches = re.findall(from_pattern, message)
    hints.extend(from_matches)

    # Extract "about X" patterns (e.g., "emails about the project")
    about_pattern = r'about\s+(?:the\s+)?([A-Za-z]+(?:\s+[A-Za-z]+){0,3})'
    about_matches = re.findall(about_pattern, message, re.IGNORECASE)
    for match in about_matches:
        if match.lower() not in common_words:
            hints.append(match)

    # Remove duplicates while preserving order
    seen = set()
    unique_hints = []
    for hint in hints:
        hint_lower = hint.lower()
        if hint_lower not in seen and len(hint) > 2:
            seen.add(hint_lower)
            unique_hints.append(hint)

    logger.debug(f"Extracted entity hints from message: {unique_hints}")
    return unique_hints

# In-memory conversation turn tracking (could be moved to Redis for production)
_conversation_turns: dict[str, int] = {}


def format_search_context(context: SearchContext) -> dict:
    """
    Format SearchContext into a structured dict for Claude.

    This creates a readable context that Claude can use to ground its responses
    in real data from the database, preventing hallucination.
    """
    # Use Eastern Time as the user's default timezone
    now_eastern = datetime.now(EASTERN_TZ)

    formatted = {
        "user_timezone": "America/New_York (Eastern Time)",
        "current_time": now_eastern.strftime("%Y-%m-%d %I:%M %p %Z"),
        "data_retrieved_at": now_eastern.isoformat(),
        "summary": context.temporal_summary or "No context retrieved",
    }

    # Format relevant emails
    if context.relevant_emails:
        formatted["emails"] = []
        for email in context.relevant_emails[:10]:  # Limit to prevent context overflow
            formatted["emails"].append({
                "id": email.get("id"),
                "subject": email.get("subject"),
                "sender": email.get("sender_name") or email.get("sender_email"),
                "sender_email": email.get("sender_email"),
                "date": format_datetime_eastern(email.get("received_at")),
                "snippet": (email.get("snippet") or email.get("body_text", ""))[:200],
                "category": email.get("category"),
                "priority": email.get("priority"),
                "is_unread": email.get("is_unread"),
            })

    # Format relevant contacts
    if context.relevant_contacts:
        formatted["contacts"] = []
        for contact in context.relevant_contacts[:10]:
            formatted["contacts"].append({
                "id": contact.get("id"),
                "name": contact.get("name"),
                "email": contact.get("email"),
                "role": contact.get("role"),
                "organization": contact.get("organization"),
                "category": contact.get("category"),
                "is_vip": contact.get("is_vip"),
            })

    # Format relevant follow-ups
    if context.relevant_followups:
        formatted["followups"] = []
        for followup in context.relevant_followups[:10]:
            formatted["followups"].append({
                "id": followup.get("id"),
                "subject": followup.get("subject"),
                "contact_name": followup.get("contact_name"),
                "contact_email": followup.get("contact_email"),
                "status": followup.get("status"),
                "due_date": format_datetime_eastern(followup.get("due_date")),
                "days_waiting": followup.get("days_waiting"),
            })

    # Format relevant meetings
    if context.relevant_meetings:
        formatted["meetings"] = []
        for meeting in context.relevant_meetings[:5]:
            meeting_date = meeting.get("start_time") or meeting.get("meeting_date")
            formatted["meetings"].append({
                "id": meeting.get("id"),
                "title": meeting.get("title") or meeting.get("subject"),
                "date": format_datetime_eastern(meeting_date),
                "attendees": meeting.get("attendees", [])[:5],  # Limit attendees
                "summary": meeting.get("summary"),
            })

    # Format relevant memories (past conversations)
    if context.relevant_memories:
        formatted["past_conversations"] = []
        for memory in context.relevant_memories[:5]:
            formatted["past_conversations"].append({
                "date": format_datetime_eastern(memory.get("created_at")),
                "user_message": memory.get("user_message"),
                "sage_response": (memory.get("sage_response") or "")[:300],
                "relevance": memory.get("relevance_score"),
            })

    return formatted


async def get_chat_context(
    db: AsyncSession,
    user_message: str,
    conversation_id: str | None = None,
    user: User | None = None,
) -> dict | None:
    """
    Retrieve relevant context for a chat message using SearchAgent.

    This is the core of Phase 3.9 - it calls SearchAgent.search_for_task()
    to get real data from the database before sending to Claude.

    Phase 3.9.3 adds:
    - Intent detection to prioritize relevant context types
    - Entity hints extraction to improve search accuracy

    Phase 3.9.4 adds:
    - Live Google Calendar integration for meeting queries

    Args:
        db: Database session
        user_message: The user's chat message
        conversation_id: Optional conversation ID for memory retrieval
        user: Optional user for Google Calendar access

    Returns:
        Formatted context dict, or None if retrieval fails
    """
    try:
        # Create DataLayerService and SearchAgent
        data_layer = DataLayerService(session=db)
        search_agent = SearchAgent(data_layer=data_layer)

        # Phase 3.9.3: Detect intent from user message
        intent = detect_chat_intent(user_message)
        logger.info(f"Detected chat intent: {intent.value}")

        # Phase 3.9.3: Extract entity hints (names, emails, subjects)
        entity_hints = extract_entity_hints(user_message)
        logger.info(f"Extracted {len(entity_hints)} entity hints: {entity_hints[:5]}")

        # Map intent to agent type for context prioritization
        # The SearchAgent will use this to enrich with the right data types
        intent_to_agent = {
            ChatIntent.EMAIL: "chat_email",
            ChatIntent.FOLLOWUP: "chat_followup",
            ChatIntent.MEETING: "chat_meeting",
            ChatIntent.CONTACT: "chat_contact",
            ChatIntent.TODO: "chat_todo",
            ChatIntent.GENERAL: "chat",
        }
        requesting_agent = intent_to_agent.get(intent, "chat")

        # Call SearchAgent to get context with intent-based prioritization
        context = await search_agent.search_for_task(
            requesting_agent=requesting_agent,
            task_description=user_message,
            entity_hints=entity_hints if entity_hints else None,
            max_results=15,  # Balance between context richness and token usage
        )

        # Also get relevant memories for conversation continuity
        if conversation_id:
            memory_context = await search_agent.get_relevant_memories(
                query=user_message,
                conversation_id=conversation_id,
                limit=5,
            )
            # Merge memories into main context
            context.relevant_memories.extend(memory_context.relevant_memories)

        # Format for Claude
        formatted = format_search_context(context)

        # Phase 3.9.4: Fetch live calendar data for meeting queries
        if intent == ChatIntent.MEETING and user:
            live_calendar = get_calendar_events_for_chat(
                user=user,
                days_ahead=7,  # Show a week of upcoming meetings
                days_behind=1,  # Also show yesterday for context
            )
            if live_calendar:
                # Replace indexed meetings with live calendar data
                formatted["live_calendar"] = live_calendar
                formatted["calendar_source"] = "Google Calendar (live)"
                logger.info(f"Added {len(live_calendar)} live calendar events to context")
        elif intent == ChatIntent.GENERAL and user:
            # For general queries, also include today's calendar
            live_calendar = get_calendar_events_for_chat(
                user=user,
                days_ahead=1,  # Just today
                days_behind=0,
            )
            if live_calendar:
                formatted["todays_calendar"] = live_calendar
                formatted["calendar_source"] = "Google Calendar (live)"

        # Add intent information for debugging/logging
        formatted["detected_intent"] = intent.value
        formatted["entity_hints_used"] = entity_hints[:10] if entity_hints else []

        # Add instructions for Claude - customize based on intent
        base_instructions = (
            "The above data is from the user's actual database. "
            "Use ONLY this data when answering questions about emails, contacts, "
            "follow-ups, meetings, or past conversations. "
            "If the requested information is not in the context above, "
            "say you don't have that information rather than making it up. "
            "Never hallucinate or invent data that isn't provided here. "
            "IMPORTANT: The user is in Eastern Time (America/New_York). "
            "Always display times in Eastern Time format (e.g., '3:30 PM ET')."
        )

        # Add intent-specific guidance
        intent_guidance = {
            ChatIntent.EMAIL: " Focus on the email data provided. Summarize emails clearly with sender, subject, and date.",
            ChatIntent.FOLLOWUP: " Focus on follow-up items. Highlight overdue items and how long they've been waiting.",
            ChatIntent.MEETING: " Focus on meeting/calendar data. Include meeting times, attendees, and any action items.",
            ChatIntent.CONTACT: " Focus on contact information and their interaction history.",
            ChatIntent.TODO: " Focus on todo items and tasks. Group by priority or due date if helpful.",
            ChatIntent.GENERAL: "",
        }

        formatted["instructions"] = base_instructions + intent_guidance.get(intent, "")

        calendar_count = len(formatted.get('live_calendar', [])) or len(formatted.get('todays_calendar', []))
        logger.info(
            f"Retrieved context for chat (intent={intent.value}): "
            f"{len(formatted.get('emails', []))} emails, "
            f"{len(formatted.get('contacts', []))} contacts, "
            f"{len(formatted.get('followups', []))} followups, "
            f"{len(formatted.get('meetings', []))} indexed meetings, "
            f"{calendar_count} live calendar events, "
            f"{len(formatted.get('past_conversations', []))} memories"
        )

        return formatted

    except Exception as e:
        logger.error(f"Error retrieving chat context: {e}", exc_info=True)
        # Return a minimal context that instructs Claude not to hallucinate
        return {
            "error": "Failed to retrieve context from database",
            "instructions": (
                "Context retrieval failed. If the user asks about specific emails, "
                "contacts, follow-ups, or other data, apologize and explain that "
                "you're unable to access the database right now. "
                "Do not make up or hallucinate any data."
            ),
        }


async def _persist_memory(
    db: AsyncSession,
    conversation_id: str,
    user_message: str,
    sage_response: str,
    turn_number: int,
) -> None:
    """Background task to persist conversation memory via IndexerAgent."""
    try:
        from sage.services.data_layer.service import DataLayerService
        from sage.agents.foundational.indexer import IndexerAgent

        # Create IndexerAgent with DataLayerService
        data_layer = DataLayerService(session=db)
        indexer = IndexerAgent(data_layer=data_layer)

        # Index the memory
        result = await indexer.execute(
            "index_memory",
            {
                "conversation_id": conversation_id,
                "user_message": user_message,
                "sage_response": sage_response,
                "turn_number": turn_number,
                "extract_facts": True,  # Enable fact extraction
            }
        )

        if result.success:
            logger.info(
                f"Persisted memory for conversation {conversation_id}, "
                f"turn {turn_number}, {result.data.get('facts_extracted', 0)} facts extracted"
            )
        else:
            logger.warning(f"Failed to persist memory: {result.errors}")

    except Exception as e:
        logger.error(f"Error persisting conversation memory: {e}", exc_info=True)


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(get_current_user)],
) -> ChatResponse:
    """Send a message to the AI assistant.

    This endpoint supports two modes:
    1. Orchestrator mode (use_orchestrator=True): Routes through SageOrchestrator
       which handles intent detection, agent coordination, and response formatting.
    2. Direct mode (use_orchestrator=False): Direct Claude integration with
       SearchAgent context retrieval (Phase 3.9 implementation).

    Conversation memory is automatically persisted in the background.
    """
    # Generate conversation ID if not provided
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # Check feature flag for orchestrator mode
    if settings.use_orchestrator:
        # Phase 4: Route through orchestrator
        logger.info(f"Processing via orchestrator: {request.message[:50]}...")

        orchestrator = await get_orchestrator(db, user)
        orchestrator.set_conversation_id(conversation_id)

        # Process through orchestrator
        response = await orchestrator.process_message(request.message)

        # Convert pending approvals to dict format for response
        pending_approvals = [
            {
                "id": approval.id,
                "agent": approval.agent,
                "action": approval.action,
                "description": approval.description,
            }
            for approval in response.pending_approvals
        ] if response.pending_approvals else None

        return ChatResponse(
            message=response.text,
            conversation_id=response.conversation_id or conversation_id,
            pending_approvals=pending_approvals,
        )

    # =========================================================================
    # Legacy flow (use_orchestrator=False) - preserved for rollback
    # =========================================================================
    logger.info("Processing via legacy direct Claude flow")

    agent = await get_claude_agent()

    # Track turn number for this conversation
    turn_number = _conversation_turns.get(conversation_id, 0) + 1
    _conversation_turns[conversation_id] = turn_number

    # Phase 3.9: Retrieve relevant context from database BEFORE calling Claude
    # This prevents hallucination by giving Claude real data to work with
    # Phase 3.9.4: Pass user for Google Calendar access
    context = await get_chat_context(
        db=db,
        user_message=request.message,
        conversation_id=conversation_id,
        user=user,
    )

    # Merge with any context provided in the request
    if request.context:
        context = {**(context or {}), **request.context}

    logger.info(f"Processing chat message with context: {bool(context)}")

    # Process the message with Claude (now with real context!)
    response = await agent.chat(
        message=request.message,
        conversation_id=conversation_id,
        context=context,
    )

    sage_response = response["message"]

    # Persist memory in background (non-blocking)
    background_tasks.add_task(
        _persist_memory,
        db,
        conversation_id,
        request.message,
        sage_response,
        turn_number,
    )

    return ChatResponse(
        message=sage_response,
        conversation_id=conversation_id,
        tool_calls=response.get("tool_calls"),
        suggestions=response.get("suggestions"),
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get conversation history."""
    # TODO: Implement conversation history storage
    # For now, conversations are not persisted
    return {
        "conversation_id": conversation_id,
        "messages": [],
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete a conversation."""
    # TODO: Implement conversation deletion
    return {"message": "Conversation deleted"}


@router.post("/quick-actions/summarize-thread")
async def summarize_thread(
    thread_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Quick action: Summarize an email thread."""
    agent = await get_claude_agent()
    summary = await agent.summarize_email_thread(thread_id, db)
    return {"thread_id": thread_id, "summary": summary}


@router.post("/quick-actions/find-action-items")
async def find_action_items(
    thread_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Quick action: Find action items in an email thread."""
    agent = await get_claude_agent()
    action_items = await agent.find_action_items(thread_id, db)
    return {"thread_id": thread_id, "action_items": action_items}


@router.post("/quick-actions/search-emails")
async def search_emails_semantic(
    query: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
) -> dict:
    """Quick action: Semantic search across emails."""
    agent = await get_claude_agent()
    results = await agent.semantic_search_emails(query, limit)
    return {"query": query, "results": results}
