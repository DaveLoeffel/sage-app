"""Email API endpoints."""

from datetime import datetime
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
    BulkImportRequest,
    BulkImportResponse,
    BulkImportProgress,
    BehavioralInsightsResponse,
    BehavioralAnalysisProgress,
    VIPContactResponse,
    VoiceProfileResponse,
    VoiceProfileProgress,
    GreetingPatternResponse,
    SignoffPatternResponse,
)
from sage.core.claude_agent import get_claude_agent

router = APIRouter()


# =============================================================================
# BULK IMPORT ENDPOINTS (must come before parametric routes like /{email_id})
# =============================================================================

@router.post("/bulk-import", response_model=BulkImportResponse)
async def start_bulk_import(
    request: BulkImportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkImportResponse:
    """
    Start a bulk email import from Gmail.

    This imports emails from INBOX, SENT, and any additional labels specified.
    Uses tiered indexing:
    - Tier 1 (Full Corpus): All emails get metadata + vector embeddings
    - Tier 2 (Active Window): Recent emails (default 90 days) get full AI analysis
    - Tier 3 (Voice Corpus): Sent emails are flagged for voice profile training

    Returns immediately with an import_id to track progress.
    """
    from sage.core.email_processor import BulkEmailImporter

    importer = BulkEmailImporter(db)

    try:
        import_id = await importer.start_import(
            include_inbox=request.include_inbox,
            include_sent=request.include_sent,
            include_labels=request.include_labels,
            max_emails=request.max_emails,
            active_window_days=request.active_window_days,
        )

        return BulkImportResponse(
            import_id=import_id,
            message="Bulk import started",
            status="processing",
            progress_url=f"/api/v1/emails/bulk-import/{import_id}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bulk-import", response_model=list[BulkImportProgress])
async def list_bulk_imports() -> list[BulkImportProgress]:
    """List all bulk import operations."""
    from sage.core.email_processor import list_import_jobs

    return list_import_jobs()


@router.get("/bulk-import/{import_id}", response_model=BulkImportProgress)
async def get_bulk_import_progress(
    import_id: str,
) -> BulkImportProgress:
    """Get the progress of a bulk import operation."""
    from sage.core.email_processor import get_import_progress

    progress = get_import_progress(import_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Import not found")

    return progress


# =============================================================================
# BEHAVIORAL ANALYSIS ENDPOINTS
# =============================================================================

# In-memory storage for analysis progress
_analysis_progress: dict[str, BehavioralAnalysisProgress] = {}


@router.post("/behavioral-analysis", response_model=dict)
async def run_behavioral_analysis(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_email: str = Query(..., description="User's email address for analysis"),
) -> dict:
    """
    Run behavioral analysis on the email corpus.

    Analyzes:
    - Response patterns (who user responds to and how quickly)
    - VIP contacts (senders with high response rates)
    - Priority keywords (words in emails that get quick responses)
    - Label patterns (starred/important emails)

    Saves results to indexed_entities for use by Search Agent.
    """
    import asyncio
    from sage.services.behavioral_analyzer import BehavioralAnalyzer

    # Start analysis
    analysis_id = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _analysis_progress[analysis_id] = BehavioralAnalysisProgress(
        status="running",
        phase="initializing",
        percent_complete=0,
    )

    async def run_analysis():
        try:
            def progress_callback(phase: str, percent: int):
                _analysis_progress[analysis_id] = BehavioralAnalysisProgress(
                    status="running",
                    phase=phase,
                    percent_complete=percent,
                )

            analyzer = BehavioralAnalyzer(user_email)
            insights = await analyzer.analyze(db, progress_callback)

            # Save insights
            await analyzer.save_insights(db, insights)
            await analyzer.save_vip_contacts(db, insights)
            await db.commit()

            _analysis_progress[analysis_id] = BehavioralAnalysisProgress(
                status="completed",
                phase="complete",
                percent_complete=100,
                message=f"Analysis complete: {len(insights.vip_contacts)} VIP contacts, "
                       f"{len(insights.priority_keywords)} keywords",
            )

        except Exception as e:
            _analysis_progress[analysis_id] = BehavioralAnalysisProgress(
                status="failed",
                phase="error",
                percent_complete=0,
                error=str(e),
            )
            raise

    # Run in background
    asyncio.create_task(run_analysis())

    return {
        "analysis_id": analysis_id,
        "message": "Behavioral analysis started",
        "status": "running",
        "progress_url": f"/api/v1/emails/behavioral-analysis/{analysis_id}",
    }


@router.get("/behavioral-analysis/{analysis_id}", response_model=BehavioralAnalysisProgress)
async def get_behavioral_analysis_progress(
    analysis_id: str,
) -> BehavioralAnalysisProgress:
    """Get the progress of a behavioral analysis operation."""
    if analysis_id not in _analysis_progress:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return _analysis_progress[analysis_id]


@router.get("/behavioral-analysis", response_model=BehavioralInsightsResponse | None)
async def get_behavioral_insights(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_email: str = Query(..., description="User's email address"),
) -> BehavioralInsightsResponse | None:
    """
    Get the latest behavioral insights for a user.

    Returns the most recent analysis results stored in indexed_entities.
    """
    from sage.services.data_layer.models.indexed_entity import IndexedEntityModel

    entity_id = f"insight_behavioral_{user_email.lower().replace('@', '_at_')}"

    result = await db.execute(
        select(IndexedEntityModel).where(
            IndexedEntityModel.id == entity_id,
            IndexedEntityModel.deleted_at.is_(None),
        )
    )
    entity = result.scalar_one_or_none()

    if not entity:
        return None

    data = entity.structured

    return BehavioralInsightsResponse(
        user_email=data["user_email"],
        analysis_timestamp=datetime.fromisoformat(data["analysis_timestamp"]),
        vip_contacts=[
            VIPContactResponse(
                email=v["email"],
                name=v.get("name"),
                total_received=v["total_received"],
                total_responded=v["total_responded"],
                response_rate=v["response_rate"],
                avg_response_time_hours=v.get("avg_response_time_hours"),
            )
            for v in data.get("vip_contacts", [])[:50]  # Top 50 VIPs
        ],
        vip_count=len(data.get("vip_contacts", [])),
        avg_response_time_hours=data.get("avg_response_time_hours", 0),
        quick_response_threshold_hours=data.get("quick_response_threshold_hours", 4),
        priority_keywords=data.get("priority_keywords", [])[:20],  # Top 20
        starred_senders=data.get("starred_senders", []),
        important_senders=data.get("important_senders", []),
        total_threads_analyzed=data.get("total_threads_analyzed", 0),
        threads_with_response=data.get("threads_with_response", 0),
        total_senders=data.get("total_senders", 0),
    )


@router.get("/vip-contacts", response_model=list[VIPContactResponse])
async def list_vip_contacts(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
) -> list[VIPContactResponse]:
    """
    List VIP contacts discovered by behavioral analysis.

    Returns contacts sorted by response rate.
    """
    from sage.services.data_layer.models.indexed_entity import IndexedEntityModel

    result = await db.execute(
        select(IndexedEntityModel).where(
            IndexedEntityModel.entity_type == "insight",
            IndexedEntityModel.metadata_["insight_type"].astext == "vip_contact",
            IndexedEntityModel.deleted_at.is_(None),
        ).limit(limit)
    )
    entities = result.scalars().all()

    vips = []
    for entity in entities:
        data = entity.structured
        vips.append(VIPContactResponse(
            email=data["email"],
            name=data.get("name"),
            total_received=data["total_received"],
            total_responded=data["total_responded"],
            response_rate=data["response_rate"],
            avg_response_time_hours=data.get("avg_response_time_hours"),
        ))

    # Sort by response rate
    vips.sort(key=lambda v: v.response_rate, reverse=True)

    return vips


# =============================================================================
# VOICE PROFILE ENDPOINTS
# =============================================================================

# In-memory storage for voice profile extraction progress
_voice_profile_progress: dict[str, VoiceProfileProgress] = {}


@router.post("/voice-profile", response_model=dict)
async def extract_voice_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_email: str = Query(..., description="User's email address"),
    sample_size: int | None = Query(None, description="Limit emails to analyze (None = all)"),
) -> dict:
    """
    Extract voice profile from sent emails.

    Analyzes the user's sent emails to learn their writing style:
    - Greeting patterns (Hi, Hello, Hey, etc.)
    - Sign-off patterns (Thanks, Best, Regards, etc.)
    - Email length and structure
    - Formality level
    - Common phrases and vocabulary

    The profile is stored and used by the Draft Agent to generate
    emails that match the user's voice.
    """
    import asyncio
    from sage.services.voice_profile_extractor import VoiceProfileExtractor

    extraction_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _voice_profile_progress[extraction_id] = VoiceProfileProgress(
        status="running",
        phase="initializing",
        percent_complete=0,
    )

    async def run_extraction():
        try:
            def progress_callback(phase: str, percent: int):
                _voice_profile_progress[extraction_id] = VoiceProfileProgress(
                    status="running",
                    phase=phase,
                    percent_complete=percent,
                )

            extractor = VoiceProfileExtractor(user_email)
            profile = await extractor.extract(db, progress_callback, sample_size)

            # Save profile
            await extractor.save_profile(db, profile)
            await db.commit()

            _voice_profile_progress[extraction_id] = VoiceProfileProgress(
                status="completed",
                phase="complete",
                percent_complete=100,
                message=f"Profile extracted from {profile.emails_analyzed} emails. "
                       f"Avg length: {profile.avg_email_length_words:.0f} words, "
                       f"Formality: {profile.formality_score:.2f}",
            )

        except Exception as e:
            _voice_profile_progress[extraction_id] = VoiceProfileProgress(
                status="failed",
                phase="error",
                percent_complete=0,
                error=str(e),
            )
            raise

    asyncio.create_task(run_extraction())

    return {
        "extraction_id": extraction_id,
        "message": "Voice profile extraction started",
        "status": "running",
        "progress_url": f"/api/v1/emails/voice-profile/{extraction_id}",
    }


@router.get("/voice-profile/{extraction_id}", response_model=VoiceProfileProgress)
async def get_voice_profile_progress(
    extraction_id: str,
) -> VoiceProfileProgress:
    """Get the progress of a voice profile extraction."""
    if extraction_id not in _voice_profile_progress:
        raise HTTPException(status_code=404, detail="Extraction not found")

    return _voice_profile_progress[extraction_id]


@router.get("/voice-profile", response_model=VoiceProfileResponse | None)
async def get_voice_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_email: str = Query(..., description="User's email address"),
) -> VoiceProfileResponse | None:
    """
    Get the voice profile for a user.

    Returns the extracted writing style profile including:
    - Greeting and sign-off patterns
    - Style metrics (length, formality, structure)
    - Common phrases
    - Prompt guidance for the Draft Agent
    """
    from sage.services.data_layer.models.indexed_entity import IndexedEntityModel

    entity_id = f"voice_profile_{user_email.lower().replace('@', '_at_')}"

    result = await db.execute(
        select(IndexedEntityModel).where(
            IndexedEntityModel.id == entity_id,
            IndexedEntityModel.deleted_at.is_(None),
        )
    )
    entity = result.scalar_one_or_none()

    if not entity:
        return None

    data = entity.structured
    analyzed = entity.analyzed or {}

    return VoiceProfileResponse(
        user_email=data["user_email"],
        extraction_timestamp=datetime.fromisoformat(data["extraction_timestamp"]),
        primary_signature=data.get("primary_signature"),
        signature_variants=data.get("signature_variants", []),
        greeting_patterns=[
            GreetingPatternResponse(
                pattern=g["pattern"],
                count=g["count"],
                examples=g.get("examples", []),
            )
            for g in data.get("greeting_patterns", [])
        ],
        greeting_usage_rate=data.get("greeting_usage_rate", 0),
        preferred_greeting_formal=data.get("preferred_greeting_formal"),
        preferred_greeting_casual=data.get("preferred_greeting_casual"),
        signoff_patterns=[
            SignoffPatternResponse(
                pattern=s["pattern"],
                count=s["count"],
                examples=s.get("examples", []),
            )
            for s in data.get("signoff_patterns", [])
        ],
        signoff_usage_rate=data.get("signoff_usage_rate", 0),
        avg_email_length_words=data.get("avg_email_length_words", 0),
        avg_sentences_per_email=data.get("avg_sentences_per_email", 0),
        uses_contractions=data.get("uses_contractions", True),
        formality_score=data.get("formality_score", 0.5),
        typical_structure=data.get("typical_structure", "direct"),
        common_phrases=data.get("common_phrases", [])[:20],
        emails_analyzed=data.get("emails_analyzed", 0),
        prompt_guidance=analyzed.get("prompt_guidance"),
    )


# =============================================================================
# STANDARD EMAIL ENDPOINTS
# =============================================================================

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
