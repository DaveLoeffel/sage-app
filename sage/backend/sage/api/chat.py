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
from datetime import datetime
from enum import Enum
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from sage.services.database import get_db
from sage.schemas.chat import ChatRequest, ChatResponse
from sage.core.claude_agent import get_claude_agent
from sage.services.data_layer.service import DataLayerService
from sage.agents.foundational.search import SearchAgent
from sage.agents.base import SearchContext

logger = logging.getLogger(__name__)
router = APIRouter()


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
    common_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'when',
        'where', 'who', 'how', 'why', 'can', 'could', 'would', 'should',
        'do', 'does', 'did', 'have', 'has', 'had', 'show', 'tell', 'find',
        'get', 'give', 'i', 'my', 'me', 'today', 'tomorrow', 'yesterday',
    }

    # Pattern for potential names: 2-3 capitalized words
    name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b'
    potential_names = re.findall(name_pattern, message)

    for name in potential_names:
        # Skip if it's just a common word at the start of a sentence
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
    eastern = ZoneInfo("America/New_York")
    now_eastern = datetime.now(eastern)

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
                "date": email.get("received_at"),
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
                "due_date": followup.get("due_date"),
                "days_waiting": followup.get("days_waiting"),
            })

    # Format relevant meetings
    if context.relevant_meetings:
        formatted["meetings"] = []
        for meeting in context.relevant_meetings[:5]:
            formatted["meetings"].append({
                "id": meeting.get("id"),
                "title": meeting.get("title") or meeting.get("subject"),
                "date": meeting.get("start_time") or meeting.get("meeting_date"),
                "attendees": meeting.get("attendees", [])[:5],  # Limit attendees
                "summary": meeting.get("summary"),
            })

    # Format relevant memories (past conversations)
    if context.relevant_memories:
        formatted["past_conversations"] = []
        for memory in context.relevant_memories[:5]:
            formatted["past_conversations"].append({
                "date": memory.get("created_at"),
                "user_message": memory.get("user_message"),
                "sage_response": (memory.get("sage_response") or "")[:300],
                "relevance": memory.get("relevance_score"),
            })

    return formatted


async def get_chat_context(
    db: AsyncSession,
    user_message: str,
    conversation_id: str | None = None,
) -> dict | None:
    """
    Retrieve relevant context for a chat message using SearchAgent.

    This is the core of Phase 3.9 - it calls SearchAgent.search_for_task()
    to get real data from the database before sending to Claude.

    Phase 3.9.3 adds:
    - Intent detection to prioritize relevant context types
    - Entity hints extraction to improve search accuracy

    Args:
        db: Database session
        user_message: The user's chat message
        conversation_id: Optional conversation ID for memory retrieval

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

        logger.info(
            f"Retrieved context for chat (intent={intent.value}): "
            f"{len(formatted.get('emails', []))} emails, "
            f"{len(formatted.get('contacts', []))} contacts, "
            f"{len(formatted.get('followups', []))} followups, "
            f"{len(formatted.get('meetings', []))} meetings, "
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
) -> ChatResponse:
    """Send a message to the AI assistant.

    This endpoint implements Phase 3.9: Context-Aware Chat (RAG Integration).
    Before sending the message to Claude, we retrieve relevant context from
    the database using SearchAgent to prevent hallucination.

    Conversation memory is automatically persisted in the background.
    """
    agent = await get_claude_agent()

    # Generate conversation ID if not provided
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # Track turn number for this conversation
    turn_number = _conversation_turns.get(conversation_id, 0) + 1
    _conversation_turns[conversation_id] = turn_number

    # Phase 3.9: Retrieve relevant context from database BEFORE calling Claude
    # This prevents hallucination by giving Claude real data to work with
    context = await get_chat_context(
        db=db,
        user_message=request.message,
        conversation_id=conversation_id,
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
