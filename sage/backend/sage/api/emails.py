"""Email API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from sage.services.database import get_db
from sage.models.email import EmailCache, EmailCategory, EmailPriority
from sage.schemas.email import (
    EmailResponse,
    EmailListResponse,
    EmailAnalysis,
    DraftReplyRequest,
    DraftReplyResponse,
)
from sage.core.claude_agent import get_claude_agent

router = APIRouter()


@router.get("", response_model=EmailListResponse)
async def list_emails(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: EmailCategory | None = None,
    priority: EmailPriority | None = None,
    unread_only: bool = False,
    inbox_only: bool = False,
    needs_attention: bool = False,
    search: str | None = None,
) -> EmailListResponse:
    """List emails with filtering and pagination.

    - inbox_only: Only show emails in inbox (not archived/filed)
    - needs_attention: Only show unread emails in inbox
    - unread_only: Only show unread emails (regardless of inbox status)
    """
    query = select(EmailCache).order_by(desc(EmailCache.received_at))

    # Apply filters
    if category:
        query = query.where(EmailCache.category == category)
    if priority:
        query = query.where(EmailCache.priority == priority)
    if inbox_only:
        query = query.where(EmailCache.labels.any("INBOX"))
    if needs_attention:
        # Unread AND in inbox - this is the "needs attention" view
        query = query.where(EmailCache.is_unread == True)
        query = query.where(EmailCache.labels.any("INBOX"))
    elif unread_only:
        query = query.where(EmailCache.is_unread == True)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (EmailCache.subject.ilike(search_filter))
            | (EmailCache.sender_email.ilike(search_filter))
            | (EmailCache.sender_name.ilike(search_filter))
            | (EmailCache.body_text.ilike(search_filter))
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    emails = result.scalars().all()

    return EmailListResponse(
        emails=[EmailResponse.model_validate(e) for e in emails],
        total=total,
        page=page,
        page_size=page_size,
        has_next=offset + len(emails) < total,
    )


@router.get("/{email_id}", response_model=EmailResponse)
async def get_email(
    email_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmailResponse:
    """Get a specific email by ID."""
    result = await db.execute(select(EmailCache).where(EmailCache.id == email_id))
    email = result.scalar_one_or_none()

    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    return EmailResponse.model_validate(email)


@router.get("/gmail/{gmail_id}", response_model=EmailResponse)
async def get_email_by_gmail_id(
    gmail_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmailResponse:
    """Get a specific email by Gmail ID."""
    result = await db.execute(
        select(EmailCache).where(EmailCache.gmail_id == gmail_id)
    )
    email = result.scalar_one_or_none()

    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    return EmailResponse.model_validate(email)


@router.post("/{email_id}/analyze", response_model=EmailAnalysis)
async def analyze_email(
    email_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmailAnalysis:
    """Analyze an email using Claude AI."""
    result = await db.execute(select(EmailCache).where(EmailCache.id == email_id))
    email = result.scalar_one_or_none()

    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    agent = await get_claude_agent()
    analysis = await agent.analyze_email(email)

    # Update email with analysis
    email.category = analysis.category
    email.priority = analysis.priority
    email.summary = analysis.summary
    email.requires_response = analysis.requires_response
    from datetime import datetime
    email.analyzed_at = datetime.utcnow()

    await db.commit()

    return analysis


@router.post("/{email_id}/draft-reply", response_model=DraftReplyResponse)
async def draft_reply(
    email_id: int,
    request: DraftReplyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DraftReplyResponse:
    """Generate a draft reply for an email using Claude AI."""
    result = await db.execute(select(EmailCache).where(EmailCache.id == email_id))
    email = result.scalar_one_or_none()

    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    agent = await get_claude_agent()
    draft = await agent.generate_draft_reply(
        email=email,
        tone=request.tone,
        key_points=request.key_points,
        context=request.context,
    )

    return draft


@router.post("/sync")
async def sync_emails(
    db: Annotated[AsyncSession, Depends(get_db)],
    max_results: int = Query(100, ge=1, le=500),
    include_sent: bool = Query(False, description="Include sent mail, not just inbox"),
) -> dict:
    """Manually trigger email sync from Gmail."""
    from sage.core.email_processor import EmailProcessor

    processor = EmailProcessor(db)
    synced_count = await processor.sync_emails(max_results=max_results, include_sent=include_sent)

    return {"message": f"Synced {synced_count} emails", "count": synced_count}


@router.get("/thread/{thread_id}", response_model=list[EmailResponse])
async def get_thread(
    thread_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[EmailResponse]:
    """Get all emails in a thread."""
    result = await db.execute(
        select(EmailCache)
        .where(EmailCache.thread_id == thread_id)
        .order_by(EmailCache.received_at)
    )
    emails = result.scalars().all()

    return [EmailResponse.model_validate(e) for e in emails]


@router.get("/search/semantic")
async def semantic_search(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    """Perform semantic search across emails."""
    from sage.services.vector_search import get_vector_service

    vector_service = get_vector_service()
    results = vector_service.search(query=q, limit=limit)

    return {
        "query": q,
        "count": len(results),
        "results": results,
    }


@router.post("/index/rebuild")
async def rebuild_index(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Rebuild the vector search index from existing emails."""
    from sage.services.vector_search import get_vector_service

    vector_service = get_vector_service()

    # Get all emails
    result = await db.execute(select(EmailCache))
    emails = result.scalars().all()

    indexed = 0
    for email in emails:
        try:
            qdrant_id = vector_service.index_email(
                email_id=email.id,
                gmail_id=email.gmail_id,
                subject=email.subject,
                body=email.body_text,
                sender=f"{email.sender_name or ''} <{email.sender_email}>",
                received_at=email.received_at.isoformat(),
            )
            email.qdrant_id = qdrant_id
            indexed += 1
        except Exception:
            pass

    await db.commit()

    # Get collection info
    info = vector_service.get_collection_info()

    return {
        "message": f"Indexed {indexed} emails",
        "indexed": indexed,
        "total_emails": len(emails),
        "collection": info,
    }
