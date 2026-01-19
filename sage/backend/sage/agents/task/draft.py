"""
Draft Agent - Content Writing in Dave's Voice.

The Draft Agent specializes in writing content:
- Email drafts in Dave's voice
- Short messages (text, Slack, etc.)
- Document sections
- Tone and style adaptation

See sage-agent-architecture.md Section 3.2 for specifications.

TODO: Implementation in Phase 5 - migrate from core/claude_agent.py
"""

from typing import Any

from ..base import BaseAgent, AgentResult, AgentType, SearchContext


# Dave's voice profile from architecture spec
VOICE_PROFILE = {
    "tone": "professional, warm, direct",
    "formality": 7,  # out of 10
    "greetings": ["Hi [First Name],", "[First Name],"],
    "closings": ["[signature block only]"],
    "avoids": [
        "excessive exclamation points",
        "emojis",
        "hope this finds you well"
    ],
    "paragraph_style": "concise, 2-3 sentences typical",
}


class DraftAgent(BaseAgent):
    """
    Writes content in Dave's voice.

    This agent understands Dave's communication style deeply and can:
    - Draft emails that sound like Dave wrote them
    - Adapt tone for different recipients (team vs investors vs vendors)
    - Write short messages for text/Slack
    - Revise existing drafts to better match voice

    Capabilities:
        - draft_email: Write email in Dave's voice
        - draft_message: Write short message
        - revise_draft: Improve existing draft
        - adapt_tone: Adjust formality/tone of content
    """

    name = "draft"
    description = "Writes content in Dave's voice"
    agent_type = AgentType.TASK
    capabilities = [
        "draft_email",
        "draft_message",
        "revise_draft",
        "adapt_tone",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.voice_profile = VOICE_PROFILE

    async def execute(
        self,
        capability: str,
        params: dict[str, Any],
        context: SearchContext | None = None
    ) -> AgentResult:
        """Execute a draft capability."""
        self._validate_capability(capability)

        # Get context if not provided
        if context is None:
            context = await self.get_context(
                task_description=f"Draft task: {capability}",
                hints=params.get("hints", [])
            )

        try:
            if capability == "draft_email":
                return await self._draft_email(params, context)
            elif capability == "draft_message":
                return await self._draft_message(params, context)
            elif capability == "revise_draft":
                return await self._revise_draft(params, context)
            elif capability == "adapt_tone":
                return await self._adapt_tone(params, context)
            else:
                return AgentResult(
                    success=False,
                    data={},
                    errors=[f"Unknown capability: {capability}"]
                )
        except Exception as e:
            return AgentResult(
                success=False,
                data={},
                errors=[f"Draft agent error: {str(e)}"]
            )

    async def _draft_email(
        self, params: dict, context: SearchContext
    ) -> AgentResult:
        """
        Draft an email in Dave's voice.

        Expected params:
            recipient_email: str
            purpose: str - What the email should accomplish
            key_points: list[str] (optional)
            reply_to_email_id: str (optional) - If replying to an email
            tone_override: str (optional) - e.g., "more formal"

        Returns:
            subject, body, tone_used, confidence, alternative_phrasings

        Note: Returns draft only - requires user approval before sending
        """
        raise NotImplementedError("draft_email not yet implemented")

    async def _draft_message(
        self, params: dict, context: SearchContext
    ) -> AgentResult:
        """
        Draft a short message (text, Slack, etc.).

        Expected params:
            recipient: str
            purpose: str
            medium: str (text, slack, etc.)
            max_length: int (optional)

        Returns:
            message, alternatives
        """
        raise NotImplementedError("draft_message not yet implemented")

    async def _revise_draft(
        self, params: dict, context: SearchContext
    ) -> AgentResult:
        """
        Improve an existing draft.

        Expected params:
            draft_text: str
            feedback: str (optional) - What to improve
            target_tone: str (optional)

        Returns:
            revised_text, changes_made
        """
        raise NotImplementedError("revise_draft not yet implemented")

    async def _adapt_tone(
        self, params: dict, context: SearchContext
    ) -> AgentResult:
        """
        Adjust the tone/formality of content.

        Expected params:
            text: str
            target_tone: str (e.g., "more formal", "friendlier", "shorter")
            recipient_context: str (optional)

        Returns:
            adapted_text, tone_analysis
        """
        raise NotImplementedError("adapt_tone not yet implemented")
