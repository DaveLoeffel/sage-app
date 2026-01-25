"""Email schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, computed_field

from sage.models.email import EmailCategory, EmailPriority


class EmailAnalysis(BaseModel):
    """AI analysis of an email."""

    category: EmailCategory
    priority: EmailPriority
    summary: str
    action_items: list[str] | None = None
    sentiment: str | None = None
    requires_response: bool
    suggested_response_time: str | None = None


class EmailResponse(BaseModel):
    """Schema for email response."""

    id: int
    gmail_id: str
    thread_id: str
    subject: str
    sender_email: str
    sender_name: str | None = None
    to_emails: list[str] | None = None
    snippet: str | None = None
    body_text: str | None = None
    labels: list[str] | None = None
    is_unread: bool
    has_attachments: bool
    received_at: datetime

    # AI analysis
    category: EmailCategory | None = None
    priority: EmailPriority | None = None
    summary: str | None = None
    requires_response: bool | None = None

    @computed_field
    @property
    def is_in_inbox(self) -> bool:
        """Check if email is still in inbox (not archived/filed)."""
        return self.labels is not None and "INBOX" in self.labels

    @computed_field
    @property
    def needs_attention(self) -> bool:
        """Check if email needs attention (unread AND in inbox)."""
        return self.is_unread and self.is_in_inbox

    class Config:
        from_attributes = True


class EmailListResponse(BaseModel):
    """Schema for paginated email list."""

    emails: list[EmailResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class DraftReplyRequest(BaseModel):
    """Schema for generating a draft reply."""

    tone: str | None = None  # e.g., "professional", "friendly", "brief"
    key_points: list[str] | None = None
    context: str | None = None


class DraftReplyResponse(BaseModel):
    """Schema for draft reply response."""

    subject: str
    body: str
    suggested_attachments: list[str] | None = None
    confidence: float
    notes: str | None = None


# Bulk Import Schemas

class BulkImportRequest(BaseModel):
    """Request schema for bulk email import."""

    include_inbox: bool = True
    include_sent: bool = True
    include_labels: list[str] | None = None  # Additional labels like "Signal"
    max_emails: int | None = None  # None = no limit (fetch all)
    active_window_days: int = 90  # Emails within this window get full AI analysis


class ImportTierStats(BaseModel):
    """Statistics for a single import tier."""

    total: int = 0
    processed: int = 0
    skipped: int = 0  # Already existed
    errors: int = 0


class BulkImportProgress(BaseModel):
    """Progress tracking for bulk import operation."""

    import_id: str
    status: str  # "pending", "fetching_ids", "processing", "completed", "failed"
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Discovery phase
    total_message_ids: int = 0
    message_ids_fetched: int = 0

    # Processing phase - by tier
    tier1_full_corpus: ImportTierStats = ImportTierStats()
    tier2_active_window: ImportTierStats = ImportTierStats()
    tier3_voice_corpus: ImportTierStats = ImportTierStats()

    # Overall stats
    emails_processed: int = 0
    emails_skipped: int = 0
    embeddings_generated: int = 0
    ai_analyses_performed: int = 0

    # Current activity
    current_phase: str = "initializing"
    current_email: str | None = None
    error_message: str | None = None

    # Estimated costs
    estimated_embedding_cost: float = 0.0
    estimated_ai_cost: float = 0.0


class BulkImportResponse(BaseModel):
    """Response schema for bulk import initiation."""

    import_id: str
    message: str
    status: str
    progress_url: str


# Behavioral Analysis Schemas

class VIPContactResponse(BaseModel):
    """VIP contact from behavioral analysis."""

    email: str
    name: str | None = None
    total_received: int
    total_responded: int
    response_rate: float
    avg_response_time_hours: float | None = None


class BehavioralInsightsResponse(BaseModel):
    """Response schema for behavioral analysis results."""

    user_email: str
    analysis_timestamp: datetime

    # VIP contacts
    vip_contacts: list[VIPContactResponse]
    vip_count: int

    # Response patterns
    avg_response_time_hours: float
    quick_response_threshold_hours: float

    # Priority keywords (top 20)
    priority_keywords: list[dict]  # [{"word": str, "count": int}]

    # Label patterns
    starred_senders: list[str]
    important_senders: list[str]

    # Summary stats
    total_threads_analyzed: int
    threads_with_response: int
    total_senders: int


class BehavioralAnalysisProgress(BaseModel):
    """Progress tracking for behavioral analysis."""

    status: str  # "running", "completed", "failed"
    phase: str
    percent_complete: int
    message: str | None = None
    error: str | None = None


# Voice Profile Schemas

class GreetingPatternResponse(BaseModel):
    """Greeting pattern from voice profile."""

    pattern: str
    count: int
    examples: list[str] = []


class SignoffPatternResponse(BaseModel):
    """Sign-off pattern from voice profile."""

    pattern: str
    count: int
    examples: list[str] = []


class VoiceProfileResponse(BaseModel):
    """Response schema for voice profile."""

    user_email: str
    extraction_timestamp: datetime

    # Signature
    primary_signature: str | None = None
    signature_variants: list[str] = []

    # Greetings
    greeting_patterns: list[GreetingPatternResponse] = []
    greeting_usage_rate: float
    preferred_greeting_formal: str | None = None
    preferred_greeting_casual: str | None = None

    # Sign-offs
    signoff_patterns: list[SignoffPatternResponse] = []
    signoff_usage_rate: float

    # Style metrics
    avg_email_length_words: float
    avg_sentences_per_email: float
    uses_contractions: bool
    formality_score: float
    typical_structure: str

    # Common phrases (top 20)
    common_phrases: list[dict] = []

    # Stats
    emails_analyzed: int

    # Prompt guidance for Draft Agent
    prompt_guidance: str | None = None


class VoiceProfileProgress(BaseModel):
    """Progress tracking for voice profile extraction."""

    status: str  # "running", "completed", "failed"
    phase: str
    percent_complete: int
    message: str | None = None
    error: str | None = None
