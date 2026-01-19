"""Chat API endpoints for ad-hoc AI queries."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from sage.services.database import get_db
from sage.schemas.chat import ChatRequest, ChatResponse
from sage.core.claude_agent import get_claude_agent

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatResponse:
    """Send a message to the AI assistant."""
    agent = await get_claude_agent()

    # Generate conversation ID if not provided
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # Process the message with Claude
    response = await agent.chat(
        message=request.message,
        conversation_id=conversation_id,
        context=request.context,
    )

    return ChatResponse(
        message=response["message"],
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
