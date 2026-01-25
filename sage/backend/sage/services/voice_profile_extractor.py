"""Voice profile extractor for learning user's writing style from sent emails."""

import re
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sage.models.email import EmailCache
from sage.services.data_layer.models.indexed_entity import IndexedEntityModel


logger = logging.getLogger(__name__)


@dataclass
class GreetingPattern:
    """A greeting pattern with usage statistics."""

    pattern: str  # e.g., "Hi {name}", "Hey", "Good morning"
    count: int = 0
    examples: list[str] = field(default_factory=list)
    recipient_types: list[str] = field(default_factory=list)  # internal, external, etc.


@dataclass
class SignoffPattern:
    """A sign-off pattern with usage statistics."""

    pattern: str  # e.g., "Thanks", "Best regards", "Dave"
    count: int = 0
    examples: list[str] = field(default_factory=list)


@dataclass
class VoiceProfile:
    """Complete voice profile for a user."""

    user_email: str
    extraction_timestamp: datetime

    # Signature
    primary_signature: str | None = None
    signature_variants: list[str] = field(default_factory=list)

    # Greetings
    greeting_patterns: list[GreetingPattern] = field(default_factory=list)
    greeting_usage_rate: float = 0.0  # % of emails that start with a greeting
    preferred_greeting_formal: str | None = None
    preferred_greeting_casual: str | None = None

    # Sign-offs
    signoff_patterns: list[SignoffPattern] = field(default_factory=list)
    signoff_usage_rate: float = 0.0  # % of emails that have explicit sign-off

    # Style metrics
    avg_email_length_chars: float = 0.0
    avg_email_length_words: float = 0.0
    avg_sentences_per_email: float = 0.0
    avg_paragraphs_per_email: float = 0.0

    # Formality indicators
    uses_contractions: bool = True
    formality_score: float = 0.5  # 0=very casual, 1=very formal
    punctuation_style: str = "standard"  # standard, minimal, expressive

    # Common phrases
    common_phrases: list[tuple[str, int]] = field(default_factory=list)
    filler_words: list[str] = field(default_factory=list)

    # Vocabulary
    vocabulary_size: int = 0
    unique_words_sample: list[str] = field(default_factory=list)

    # Email structure
    typical_structure: str = "direct"  # direct, greeting-body-signoff, formal

    # Stats
    emails_analyzed: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "user_email": self.user_email,
            "extraction_timestamp": self.extraction_timestamp.isoformat(),
            "primary_signature": self.primary_signature,
            "signature_variants": self.signature_variants,
            "greeting_patterns": [
                {"pattern": g.pattern, "count": g.count, "examples": g.examples[:3]}
                for g in self.greeting_patterns
            ],
            "greeting_usage_rate": self.greeting_usage_rate,
            "preferred_greeting_formal": self.preferred_greeting_formal,
            "preferred_greeting_casual": self.preferred_greeting_casual,
            "signoff_patterns": [
                {"pattern": s.pattern, "count": s.count, "examples": s.examples[:3]}
                for s in self.signoff_patterns
            ],
            "signoff_usage_rate": self.signoff_usage_rate,
            "avg_email_length_chars": self.avg_email_length_chars,
            "avg_email_length_words": self.avg_email_length_words,
            "avg_sentences_per_email": self.avg_sentences_per_email,
            "avg_paragraphs_per_email": self.avg_paragraphs_per_email,
            "uses_contractions": self.uses_contractions,
            "formality_score": self.formality_score,
            "punctuation_style": self.punctuation_style,
            "common_phrases": [{"phrase": p, "count": c} for p, c in self.common_phrases[:50]],
            "filler_words": self.filler_words,
            "vocabulary_size": self.vocabulary_size,
            "unique_words_sample": self.unique_words_sample[:100],
            "typical_structure": self.typical_structure,
            "emails_analyzed": self.emails_analyzed,
        }

    def to_prompt_guidance(self) -> str:
        """Generate prompt guidance for the Draft Agent."""
        lines = [
            f"# Voice Profile for {self.user_email}",
            "",
            "## Writing Style Guidelines",
            "",
        ]

        # Greeting guidance
        if self.greeting_usage_rate < 0.3:
            lines.append("- **Greetings**: Often skip greetings and get straight to the point")
        elif self.preferred_greeting_casual:
            lines.append(f"- **Greetings**: Typically use '{self.preferred_greeting_casual}' for casual emails")

        if self.preferred_greeting_formal:
            lines.append(f"- **Formal greeting**: Use '{self.preferred_greeting_formal}' for formal contexts")

        # Length guidance
        if self.avg_email_length_words < 50:
            lines.append("- **Length**: Keep emails very brief (under 50 words typically)")
        elif self.avg_email_length_words < 100:
            lines.append("- **Length**: Keep emails concise (50-100 words typically)")
        else:
            lines.append(f"- **Length**: Emails are typically around {int(self.avg_email_length_words)} words")

        # Structure
        lines.append(f"- **Structure**: {self.typical_structure} style")

        # Formality
        if self.formality_score < 0.3:
            lines.append("- **Tone**: Casual and conversational")
        elif self.formality_score < 0.6:
            lines.append("- **Tone**: Professional but approachable")
        else:
            lines.append("- **Tone**: Formal and professional")

        # Contractions
        if self.uses_contractions:
            lines.append("- **Contractions**: Uses contractions (don't, won't, I'll)")
        else:
            lines.append("- **Contractions**: Avoids contractions (do not, will not)")

        # Sign-off
        if self.signoff_patterns:
            top_signoff = self.signoff_patterns[0].pattern
            lines.append(f"- **Sign-off**: Typically uses '{top_signoff}'")

        # Signature
        if self.primary_signature:
            lines.append("")
            lines.append("## Standard Signature")
            lines.append("```")
            lines.append(self.primary_signature)
            lines.append("```")

        # Common phrases
        if self.common_phrases:
            lines.append("")
            lines.append("## Common Phrases")
            for phrase, count in self.common_phrases[:10]:
                lines.append(f"- \"{phrase}\"")

        return "\n".join(lines)


class VoiceProfileExtractor:
    """
    Extract voice profile from sent emails.

    Analyzes:
    - Greeting patterns (Hi, Hello, Hey, Dear, etc.)
    - Sign-off patterns (Thanks, Best, Regards, etc.)
    - Email structure and length
    - Formality indicators
    - Common phrases and vocabulary
    - Signature detection
    """

    # Common greeting patterns to detect
    GREETING_PATTERNS = [
        (r"^hey\b", "Hey"),
        (r"^hi\b", "Hi"),
        (r"^hello\b", "Hello"),
        (r"^dear\b", "Dear"),
        (r"^good morning\b", "Good morning"),
        (r"^good afternoon\b", "Good afternoon"),
        (r"^good evening\b", "Good evening"),
        (r"^greetings\b", "Greetings"),
        (r"^howdy\b", "Howdy"),
    ]

    # Common sign-off patterns
    SIGNOFF_PATTERNS = [
        (r"\bthanks[,!]?\s*$", "Thanks"),
        (r"\bthank you[,!]?\s*$", "Thank you"),
        (r"\bbest[,]?\s*$", "Best"),
        (r"\bbest regards[,]?\s*$", "Best regards"),
        (r"\bregards[,]?\s*$", "Regards"),
        (r"\bkind regards[,]?\s*$", "Kind regards"),
        (r"\bwarm regards[,]?\s*$", "Warm regards"),
        (r"\bcheers[,!]?\s*$", "Cheers"),
        (r"\btake care[,]?\s*$", "Take care"),
        (r"\bsincerely[,]?\s*$", "Sincerely"),
        (r"\brespectfully[,]?\s*$", "Respectfully"),
    ]

    # Formal indicators
    FORMAL_WORDS = {
        "pursuant", "hereby", "aforementioned", "henceforth", "whereas",
        "therefore", "furthermore", "nevertheless", "notwithstanding",
        "respectfully", "sincerely", "cordially", "dear",
    }

    # Casual indicators
    CASUAL_WORDS = {
        "hey", "yeah", "yep", "nope", "gonna", "wanna", "gotta",
        "awesome", "cool", "great", "sounds good", "no worries",
    }

    # Common contractions
    CONTRACTIONS = {
        "i'm", "i'll", "i've", "i'd", "we're", "we'll", "we've", "we'd",
        "you're", "you'll", "you've", "you'd", "they're", "they'll",
        "they've", "they'd", "he's", "she's", "it's", "that's", "there's",
        "here's", "what's", "who's", "how's", "let's", "can't", "won't",
        "don't", "doesn't", "didn't", "isn't", "aren't", "wasn't", "weren't",
        "hasn't", "haven't", "hadn't", "couldn't", "wouldn't", "shouldn't",
    }

    def __init__(self, user_email: str):
        """
        Initialize extractor for a specific user.

        Args:
            user_email: The user's email address
        """
        self.user_email = user_email.lower()

    async def extract(
        self, session: AsyncSession, progress_callback=None, sample_size: int | None = None
    ) -> VoiceProfile:
        """
        Extract voice profile from sent emails.

        Args:
            session: Database session
            progress_callback: Optional callback for progress updates (phase, percent)
            sample_size: Optional limit on emails to analyze (None = all)

        Returns:
            VoiceProfile with extracted patterns
        """
        profile = VoiceProfile(
            user_email=self.user_email,
            extraction_timestamp=datetime.utcnow(),
        )

        if progress_callback:
            progress_callback("Loading sent emails", 0)

        # Load sent emails
        logger.info("Loading sent emails...")
        emails = await self._load_sent_emails(session, sample_size)
        profile.emails_analyzed = len(emails)

        if not emails:
            logger.warning("No sent emails found")
            return profile

        if progress_callback:
            progress_callback("Extracting signatures", 10)

        # Extract signature
        logger.info("Extracting signature patterns...")
        profile.primary_signature, profile.signature_variants = self._extract_signatures(emails)

        if progress_callback:
            progress_callback("Analyzing greetings", 25)

        # Analyze greetings
        logger.info("Analyzing greeting patterns...")
        profile.greeting_patterns, profile.greeting_usage_rate = self._analyze_greetings(emails)
        if profile.greeting_patterns:
            # Most common is likely casual
            profile.preferred_greeting_casual = profile.greeting_patterns[0].pattern
            # Look for formal options
            for g in profile.greeting_patterns:
                if g.pattern.lower() in ["dear", "good morning", "good afternoon", "hello"]:
                    profile.preferred_greeting_formal = g.pattern
                    break

        if progress_callback:
            progress_callback("Analyzing sign-offs", 40)

        # Analyze sign-offs
        logger.info("Analyzing sign-off patterns...")
        profile.signoff_patterns, profile.signoff_usage_rate = self._analyze_signoffs(emails)

        if progress_callback:
            progress_callback("Analyzing style metrics", 55)

        # Analyze style metrics
        logger.info("Analyzing style metrics...")
        self._analyze_style_metrics(emails, profile)

        if progress_callback:
            progress_callback("Extracting phrases", 70)

        # Extract common phrases
        logger.info("Extracting common phrases...")
        profile.common_phrases = self._extract_common_phrases(emails)

        if progress_callback:
            progress_callback("Analyzing vocabulary", 85)

        # Analyze vocabulary
        logger.info("Analyzing vocabulary...")
        profile.vocabulary_size, profile.unique_words_sample = self._analyze_vocabulary(emails)

        if progress_callback:
            progress_callback("Determining structure", 95)

        # Determine typical structure
        profile.typical_structure = self._determine_structure(profile)

        if progress_callback:
            progress_callback("Complete", 100)

        logger.info(
            f"Voice profile extraction complete: {profile.emails_analyzed} emails, "
            f"{len(profile.greeting_patterns)} greeting patterns, "
            f"{len(profile.signoff_patterns)} sign-off patterns"
        )

        return profile

    async def _load_sent_emails(
        self, session: AsyncSession, limit: int | None = None
    ) -> list[EmailCache]:
        """Load sent emails with body text, filtering out automated/system emails."""
        query = (
            select(EmailCache)
            .where(EmailCache.labels.contains(["SENT"]))
            .where(EmailCache.body_text.isnot(None))
            .where(EmailCache.body_text != "")
            .order_by(EmailCache.received_at.desc())
        )

        if limit:
            # Fetch more than needed to account for filtering
            query = query.limit(limit * 2)

        result = await session.execute(query)
        all_emails = list(result.scalars().all())

        # Filter out automated/system emails
        filtered = []
        for email in all_emails:
            if self._is_automated_email(email):
                continue
            filtered.append(email)
            if limit and len(filtered) >= limit:
                break

        return filtered

    def _is_automated_email(self, email: EmailCache) -> bool:
        """Check if email is automated/system-generated (not human-written)."""
        subject = (email.subject or "").lower()
        body = (email.body_text or "").lower()[:500]

        # Calendar-related
        if any(x in subject for x in [
            "@ mon", "@ tue", "@ wed", "@ thu", "@ fri", "@ sat", "@ sun",
            "accepted:", "declined:", "tentative:", "invitation:",
            "daily agenda", "updated invitation", "canceled event",
        ]):
            return True

        # System emails
        if any(x in subject for x in [
            "automated", "auto-reply", "out of office", "delivery status",
            "read receipt", "undeliverable", "mailer-daemon",
        ]):
            return True

        # Body checks for calendar/meeting content
        if any(x in body for x in [
            "forwarding this invitation could allow",
            "join zoom meeting",
            "google meet",
            "add to calendar",
            "you are receiving this email at the account",
            "speaker 1:", "speaker 2:",  # Transcripts
            "speaker:", "transcript",  # More transcript markers
            "fireflies.ai", "meeting notes from",
        ]):
            return True

        # Very short or empty after quotes removal
        clean_body = self._get_body_without_quotes(email.body_text or "")
        clean_body = self._remove_signature(clean_body)
        if len(clean_body.strip()) < 10:
            return True

        return False

    def _extract_signatures(
        self, emails: list[EmailCache]
    ) -> tuple[str | None, list[str]]:
        """
        Extract signature patterns from emails.

        Looks for repeated blocks at the end of emails that contain
        name, contact info, or typical signature markers.
        """
        signature_candidates: Counter[str] = Counter()

        # Known signature markers
        sig_markers = ["dave loeffel", "cfa", "highlands", "cell:", "404."]

        for email in emails:
            body = email.body_text or ""

            # Remove quoted content (lines starting with >)
            lines = [l for l in body.split("\n") if not l.strip().startswith(">")]
            body = "\n".join(lines)

            # Look for signature-like blocks (last 5-10 lines)
            lines = body.strip().split("\n")
            if len(lines) >= 3:
                # Try different signature lengths
                for sig_len in [3, 4, 5, 6, 7]:
                    if len(lines) >= sig_len:
                        candidate = "\n".join(lines[-sig_len:]).strip()
                        candidate_lower = candidate.lower()

                        # Filter out very short or very long candidates
                        if not (20 < len(candidate) < 500):
                            continue

                        # Must contain at least one signature marker
                        has_marker = any(m in candidate_lower for m in sig_markers)
                        if not has_marker:
                            continue

                        # Skip if it looks like calendar/system content
                        if any(x in candidate_lower for x in [
                            "forwarding this invitation",
                            "learn more http",
                            "unsubscribe",
                            "view in browser",
                        ]):
                            continue

                        signature_candidates[candidate] += 1

        if not signature_candidates:
            return None, []

        # Find most common signature
        most_common = signature_candidates.most_common(10)

        # Primary signature is the most frequent with enough occurrences
        primary = None
        for sig, count in most_common:
            if count >= 5:
                primary = sig
                break

        # Variants are other common signatures
        variants = [sig for sig, count in most_common[1:5] if count >= 3 and sig != primary]

        return primary, variants

    def _analyze_greetings(
        self, emails: list[EmailCache]
    ) -> tuple[list[GreetingPattern], float]:
        """Analyze greeting patterns in emails."""
        greeting_counts: dict[str, GreetingPattern] = {}
        emails_with_greeting = 0

        for email in emails:
            body = self._get_body_without_quotes(email.body_text or "")
            if not body.strip():
                continue

            # Get first line
            first_line = body.strip().split("\n")[0].strip().lower()

            greeting_found = False
            for pattern, name in self.GREETING_PATTERNS:
                if re.search(pattern, first_line, re.IGNORECASE):
                    greeting_found = True
                    if name not in greeting_counts:
                        greeting_counts[name] = GreetingPattern(pattern=name)
                    greeting_counts[name].count += 1
                    if len(greeting_counts[name].examples) < 5:
                        greeting_counts[name].examples.append(first_line[:50])
                    break

            if greeting_found:
                emails_with_greeting += 1

        # Sort by count
        patterns = sorted(greeting_counts.values(), key=lambda x: x.count, reverse=True)
        usage_rate = emails_with_greeting / len(emails) if emails else 0.0

        return patterns, usage_rate

    def _analyze_signoffs(
        self, emails: list[EmailCache]
    ) -> tuple[list[SignoffPattern], float]:
        """Analyze sign-off patterns in emails."""
        signoff_counts: dict[str, SignoffPattern] = {}
        emails_with_signoff = 0

        for email in emails:
            body = self._get_body_without_quotes(email.body_text or "")
            body = self._remove_signature(body)

            if not body.strip():
                continue

            # Get last few lines
            lines = body.strip().split("\n")
            last_lines = " ".join(lines[-3:]).lower()

            signoff_found = False
            for pattern, name in self.SIGNOFF_PATTERNS:
                if re.search(pattern, last_lines, re.IGNORECASE):
                    signoff_found = True
                    if name not in signoff_counts:
                        signoff_counts[name] = SignoffPattern(pattern=name)
                    signoff_counts[name].count += 1
                    if len(signoff_counts[name].examples) < 5:
                        signoff_counts[name].examples.append(last_lines[:50])
                    break

            if signoff_found:
                emails_with_signoff += 1

        patterns = sorted(signoff_counts.values(), key=lambda x: x.count, reverse=True)
        usage_rate = emails_with_signoff / len(emails) if emails else 0.0

        return patterns, usage_rate

    def _analyze_style_metrics(self, emails: list[EmailCache], profile: VoiceProfile) -> None:
        """Analyze various style metrics."""
        total_chars = 0
        total_words = 0
        total_sentences = 0
        total_paragraphs = 0
        contraction_count = 0
        formal_word_count = 0
        casual_word_count = 0

        for email in emails:
            body = self._get_body_without_quotes(email.body_text or "")
            body = self._remove_signature(body)

            if not body.strip():
                continue

            # Length
            total_chars += len(body)
            words = body.split()
            total_words += len(words)

            # Sentences (rough count)
            sentences = re.split(r"[.!?]+", body)
            total_sentences += len([s for s in sentences if s.strip()])

            # Paragraphs
            paragraphs = body.split("\n\n")
            total_paragraphs += len([p for p in paragraphs if p.strip()])

            # Contractions
            body_lower = body.lower()
            for contraction in self.CONTRACTIONS:
                if contraction in body_lower:
                    contraction_count += 1

            # Formality indicators
            for word in self.FORMAL_WORDS:
                if word in body_lower:
                    formal_word_count += 1

            for word in self.CASUAL_WORDS:
                if word in body_lower:
                    casual_word_count += 1

        n = len(emails)
        if n > 0:
            profile.avg_email_length_chars = total_chars / n
            profile.avg_email_length_words = total_words / n
            profile.avg_sentences_per_email = total_sentences / n
            profile.avg_paragraphs_per_email = total_paragraphs / n

        # Determine formality
        profile.uses_contractions = contraction_count > n * 0.1

        total_indicators = formal_word_count + casual_word_count
        if total_indicators > 0:
            profile.formality_score = formal_word_count / total_indicators
        else:
            # Default based on other indicators
            profile.formality_score = 0.4 if profile.uses_contractions else 0.6

    def _extract_common_phrases(
        self, emails: list[EmailCache]
    ) -> list[tuple[str, int]]:
        """Extract commonly used phrases (2-4 word sequences)."""
        phrase_counts: Counter[str] = Counter()

        for email in emails:
            body = self._get_body_without_quotes(email.body_text or "")
            body = self._remove_signature(body)

            # Clean and tokenize
            words = re.findall(r"\b[a-z]+\b", body.lower())

            # Extract n-grams (2-4 words)
            for n in [2, 3, 4]:
                for i in range(len(words) - n + 1):
                    phrase = " ".join(words[i : i + n])
                    # Filter out boring phrases
                    if not self._is_boring_phrase(phrase):
                        phrase_counts[phrase] += 1

        # Filter to phrases used at least 5 times
        common = [(phrase, count) for phrase, count in phrase_counts.items() if count >= 5]
        common.sort(key=lambda x: x[1], reverse=True)

        return common[:100]

    def _is_boring_phrase(self, phrase: str) -> bool:
        """Check if a phrase is too common/boring to include."""
        boring_patterns = [
            r"^the\b", r"^a\b", r"^an\b", r"^to\b", r"^of\b", r"^in\b",
            r"^on\b", r"^at\b", r"^for\b", r"^and\b", r"^or\b", r"^is\b",
            r"^it\b", r"^be\b", r"^as\b", r"^by\b", r"^from\b", r"^with\b",
            r"\bthe$", r"\ba$", r"\ban$", r"\bto$", r"\bof$",
        ]
        for pattern in boring_patterns:
            if re.search(pattern, phrase):
                return True

        # Transcript patterns
        transcript_patterns = [
            "speaker", "yeah", "uh", "um", "okay so", "you know",
            "i mean", "like i", "gonna", "wanna",
        ]
        for p in transcript_patterns:
            if p in phrase:
                return True

        return False

    def _analyze_vocabulary(
        self, emails: list[EmailCache]
    ) -> tuple[int, list[str]]:
        """Analyze vocabulary usage."""
        all_words: Counter[str] = Counter()

        for email in emails:
            body = self._get_body_without_quotes(email.body_text or "")
            body = self._remove_signature(body)

            words = re.findall(r"\b[a-z]{3,}\b", body.lower())
            all_words.update(words)

        # Vocabulary size
        vocab_size = len(all_words)

        # Sample of unique words (excluding very common ones)
        common_words = {
            "the", "and", "for", "are", "but", "not", "you", "all", "can",
            "had", "her", "was", "one", "our", "out", "day", "get", "has",
            "him", "his", "how", "its", "may", "new", "now", "old", "see",
            "two", "way", "who", "did", "let", "put", "say", "she", "too",
            "use", "that", "with", "have", "this", "will", "your", "from",
            "they", "been", "call", "come", "could", "down", "each", "find",
        }
        unique = [w for w, c in all_words.most_common(500) if w not in common_words]

        return vocab_size, unique[:100]

    def _determine_structure(self, profile: VoiceProfile) -> str:
        """Determine typical email structure based on patterns."""
        has_greetings = profile.greeting_usage_rate > 0.3
        has_signoffs = profile.signoff_usage_rate > 0.3
        is_brief = profile.avg_email_length_words < 50

        if is_brief and not has_greetings:
            return "direct"  # Gets straight to the point
        elif has_greetings and has_signoffs:
            return "greeting-body-signoff"  # Traditional structure
        elif profile.formality_score > 0.6:
            return "formal"
        else:
            return "casual"

    def _get_body_without_quotes(self, body: str) -> str:
        """Remove quoted content from email body."""
        lines = []
        for line in body.split("\n"):
            # Skip quoted lines
            if line.strip().startswith(">"):
                continue
            # Skip "On ... wrote:" lines
            if re.match(r"^On .+ wrote:$", line.strip()):
                continue
            lines.append(line)
        return "\n".join(lines)

    def _remove_signature(self, body: str) -> str:
        """Remove signature block from email body."""
        lines = body.split("\n")

        # Look for signature markers
        sig_markers = ["--", "—", "dave loeffel", "regards,", "thanks,", "best,"]

        for i, line in enumerate(lines):
            line_lower = line.strip().lower()
            for marker in sig_markers:
                if line_lower.startswith(marker) or line_lower == marker:
                    return "\n".join(lines[:i])

        # If no marker found, try to detect by common signature patterns
        # (email, phone, www patterns in last lines)
        for i in range(len(lines) - 1, max(0, len(lines) - 8), -1):
            line_lower = lines[i].lower()
            if re.search(r"\b\d{3}[.-]\d{3}[.-]\d{4}\b", line_lower):  # Phone
                return "\n".join(lines[:i])
            if re.search(r"@\w+\.\w+", line_lower):  # Email
                return "\n".join(lines[:i])
            if "www." in line_lower:  # Website
                return "\n".join(lines[:i])

        return body

    async def save_profile(
        self, session: AsyncSession, profile: VoiceProfile
    ) -> str:
        """
        Save voice profile to indexed_entities table.

        Args:
            session: Database session
            profile: The profile to save

        Returns:
            Entity ID of the saved profile
        """
        entity_id = f"voice_profile_{self.user_email.replace('@', '_at_')}"

        # Check if exists
        result = await session.execute(
            select(IndexedEntityModel).where(IndexedEntityModel.id == entity_id)
        )
        existing = result.scalar_one_or_none()

        data = profile.to_dict()
        prompt_guidance = profile.to_prompt_guidance()

        if existing:
            existing.structured = data
            existing.analyzed = {
                "summary": f"Voice profile for {self.user_email}: "
                          f"{profile.emails_analyzed} emails analyzed, "
                          f"{profile.avg_email_length_words:.0f} avg words, "
                          f"formality: {profile.formality_score:.2f}",
                "prompt_guidance": prompt_guidance,
            }
            existing.updated_at = datetime.utcnow()
            existing.deleted_at = None
        else:
            model = IndexedEntityModel(
                id=entity_id,
                entity_type="voice_profile",
                source="voice_profile_extractor",
                structured=data,
                analyzed={
                    "summary": f"Voice profile for {self.user_email}: "
                              f"{profile.emails_analyzed} emails analyzed, "
                              f"{profile.avg_email_length_words:.0f} avg words, "
                              f"formality: {profile.formality_score:.2f}",
                    "prompt_guidance": prompt_guidance,
                },
            )
            session.add(model)

        await session.flush()
        logger.info(f"Saved voice profile as {entity_id}")
        return entity_id
