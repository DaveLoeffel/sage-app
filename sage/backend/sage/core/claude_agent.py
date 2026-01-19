"""Claude Agent SDK integration with MCP servers."""

import json
from typing import Any

from anthropic import Anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sage.config import get_settings
from sage.models.email import EmailCache, EmailCategory, EmailPriority
from sage.schemas.email import EmailAnalysis, DraftReplyResponse

settings = get_settings()

# System prompt for Dave's personal AI assistant
SYSTEM_PROMPT = """You are Sage, a personal AI assistant for Dave Loeffel. Your role is to help Dave manage ALL aspects of his life - both professional and personal. You are his trusted assistant who helps him stay organized, informed, and on top of everything that matters to him.

## About Dave
- CEO of Highlands Residential LLC, a multifamily real estate company
- Family man with personal relationships and commitments that matter deeply to him
- Prioritizes clear, direct communication
- Values efficiency and getting to the point
- Wants help managing his whole life, not just work

## Your Scope - Everything in Dave's Life
You help with ALL aspects of Dave's life including:
- **Business**: Investors, property managers, vendors, team members, deals, operations
- **Family**: Spouse, children, parents, relatives, family events, birthdays, anniversaries
- **Personal**: Friends, personal appointments, hobbies, health, travel, personal projects
- **Financial**: Personal investments, stock portfolio, financial planning
- **Home**: Household management, maintenance, personal errands

## Your Responsibilities
1. **Email Management**: Analyze and prioritize ALL emails - business AND personal
2. **Follow-up Tracking**: Ensure nothing falls through the cracks - whether it's a business deal or remembering to call mom
3. **Draft Replies**: Write responses matching Dave's style for any context
4. **Briefings**: Provide morning briefings covering work, family, and personal priorities
5. **Meeting Prep**: Context for business meetings AND personal commitments
6. **Life Management**: Help Dave be present for what matters - family events, personal milestones, etc.

## Communication Style Guidelines
When drafting emails for Dave:
- Be professional but personable
- Get to the point quickly
- Use short paragraphs
- End with clear next steps when applicable
- Match the formality level of the sender
- For internal team: slightly more casual
- For investors: professional and thorough
- For vendors: professional and directive
- For family/friends: warm, personal, genuine

## Follow-up Rules
- Day 2: Send a gentle reminder if no response
- Day 7: Escalate to supervisor if available, otherwise send firmer follow-up
- Auto-close when response is detected

## Priority Levels
- URGENT: Requires immediate attention (family emergencies, investor issues, legal matters)
- HIGH: Important, time-sensitive (deals in progress, family events, team issues)
- NORMAL: Standard communications - business or personal
- LOW: FYIs, newsletters, non-time-sensitive

## Contact Categories
- **Team**: Work colleagues and employees
- **Investor**: Business investors and partners
- **Vendor**: Service providers (business)
- **Family**: Spouse, children, parents, siblings, relatives
- **Client**: Business clients
- **Partner**: Business partners
- **Other**: Friends, acquaintances, personal contacts

## Available Tools
You have access to various MCP servers for:
- Gmail: Read emails, send emails, create drafts
- Google Calendar: View and manage calendar events (work AND personal)
- Google Drive: Access documents
- Memory: Store and retrieve persistent information about people, preferences, etc.
- Stock prices: Check market data (Alpha Vantage)
- Web: Fetch and analyze web content

## Your Personality
- You are helpful, proactive, and genuinely care about Dave's wellbeing
- You treat family and personal matters with the same importance as business
- You remember context about the people in Dave's life
- You help Dave be more present for his family by keeping him organized
- You never dismiss personal matters as "not your job"

Always be proactive in identifying potential issues and opportunities to help Dave be more effective in ALL areas of his life."""


class ClaudeAgent:
    """Claude Agent with MCP server integrations."""

    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.conversations: dict[str, list[dict]] = {}

    async def analyze_email(self, email: EmailCache) -> EmailAnalysis:
        """Analyze an email for categorization and priority."""
        prompt = f"""Analyze this email and provide:
1. Category (urgent, action_required, fyi, newsletter, personal, spam)
2. Priority level (low, normal, high, urgent)
3. Brief summary (1-2 sentences)
4. Action items if any
5. Sentiment (positive, neutral, negative)
6. Whether it requires a response

Email:
From: {email.sender_name} <{email.sender_email}>
Subject: {email.subject}
Date: {email.received_at}

{email.body_text or email.snippet or '[No body content]'}

Respond in JSON format:
{{
    "category": "...",
    "priority": "...",
    "summary": "...",
    "action_items": ["..."] or null,
    "sentiment": "...",
    "requires_response": true/false,
    "suggested_response_time": "..." or null
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse the response
        content = response.content[0].text
        # Extract JSON from the response
        try:
            # Try to find JSON in the response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(content[start:end])
            else:
                raise ValueError("No JSON found in response")
        except (json.JSONDecodeError, ValueError):
            # Fallback to defaults if parsing fails
            data = {
                "category": "unknown",
                "priority": "normal",
                "summary": "Unable to analyze email",
                "action_items": None,
                "sentiment": "neutral",
                "requires_response": False,
                "suggested_response_time": None,
            }

        # Normalize category and priority to lowercase
        category_str = data.get("category", "unknown").lower()
        priority_str = data.get("priority", "normal").lower()

        # Handle potential variations
        if category_str not in [e.value for e in EmailCategory]:
            category_str = "unknown"
        if priority_str not in [e.value for e in EmailPriority]:
            priority_str = "normal"

        return EmailAnalysis(
            category=EmailCategory(category_str),
            priority=EmailPriority(priority_str),
            summary=data.get("summary", ""),
            action_items=data.get("action_items"),
            sentiment=data.get("sentiment"),
            requires_response=data.get("requires_response", False),
            suggested_response_time=data.get("suggested_response_time"),
        )

    async def generate_draft_reply(
        self,
        email: EmailCache,
        tone: str | None = None,
        key_points: list[str] | None = None,
        context: str | None = None,
    ) -> DraftReplyResponse:
        """Generate a draft reply for an email."""
        tone_instruction = f"Use a {tone} tone." if tone else "Match the sender's tone."
        key_points_text = "\n".join(f"- {p}" for p in key_points) if key_points else ""

        prompt = f"""Draft a reply to this email from Dave Loeffel.

Original Email:
From: {email.sender_name} <{email.sender_email}>
Subject: {email.subject}
Date: {email.received_at}

{email.body_text or email.snippet or '[No body content]'}

Instructions:
- {tone_instruction}
{f'- Include these key points:{chr(10)}{key_points_text}' if key_points_text else ''}
{f'- Additional context: {context}' if context else ''}

Write a professional reply that:
1. Addresses the sender's main points
2. Is concise and actionable
3. Ends with clear next steps if applicable

Respond in JSON format:
{{
    "subject": "Re: ...",
    "body": "...",
    "suggested_attachments": ["..."] or null,
    "confidence": 0.0-1.0,
    "notes": "..." or null
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(content[start:end])
            else:
                raise ValueError("No JSON found")
        except (json.JSONDecodeError, ValueError):
            data = {
                "subject": f"Re: {email.subject}",
                "body": "Unable to generate draft reply.",
                "confidence": 0.0,
            }

        return DraftReplyResponse(
            subject=data.get("subject", f"Re: {email.subject}"),
            body=data.get("body", ""),
            suggested_attachments=data.get("suggested_attachments"),
            confidence=data.get("confidence", 0.5),
            notes=data.get("notes"),
        )

    async def chat(
        self,
        message: str,
        conversation_id: str,
        context: dict | None = None,
    ) -> dict[str, Any]:
        """Process a chat message."""
        # Get or create conversation history
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        history = self.conversations[conversation_id]

        # Add context to the message if provided
        full_message = message
        if context:
            context_str = json.dumps(context, indent=2)
            full_message = f"Context: {context_str}\n\nUser message: {message}"

        history.append({"role": "user", "content": full_message})

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=history,
        )

        assistant_message = response.content[0].text
        history.append({"role": "assistant", "content": assistant_message})

        # Keep conversation history manageable
        if len(history) > 20:
            history = history[-20:]
            self.conversations[conversation_id] = history

        return {
            "message": assistant_message,
            "tool_calls": None,  # TODO: Implement MCP tool calls
            "suggestions": self._generate_suggestions(assistant_message),
        }

    def _generate_suggestions(self, response: str) -> list[str]:
        """Generate follow-up question suggestions based on the response."""
        # Simple heuristic-based suggestions
        suggestions = []

        if "email" in response.lower():
            suggestions.append("Show me urgent emails")
        if "follow" in response.lower() or "reminder" in response.lower():
            suggestions.append("What follow-ups are overdue?")
        if "meeting" in response.lower() or "calendar" in response.lower():
            suggestions.append("What's on my calendar today?")

        return suggestions[:3] if suggestions else [
            "What should I focus on today?",
            "Show me overdue follow-ups",
            "Generate my morning briefing",
        ]

    async def summarize_email_thread(
        self, thread_id: str, db: AsyncSession
    ) -> str:
        """Summarize an email thread."""
        result = await db.execute(
            select(EmailCache)
            .where(EmailCache.thread_id == thread_id)
            .order_by(EmailCache.received_at)
        )
        emails = result.scalars().all()

        if not emails:
            return "No emails found in this thread."

        thread_text = "\n\n---\n\n".join([
            f"From: {e.sender_name} <{e.sender_email}>\n"
            f"Date: {e.received_at}\n\n"
            f"{e.body_text or e.snippet or '[No content]'}"
            for e in emails
        ])

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Summarize this email thread concisely:\n\n{thread_text}",
            }],
        )

        return response.content[0].text

    async def find_action_items(
        self, thread_id: str, db: AsyncSession
    ) -> list[str]:
        """Extract action items from an email thread."""
        result = await db.execute(
            select(EmailCache)
            .where(EmailCache.thread_id == thread_id)
            .order_by(EmailCache.received_at)
        )
        emails = result.scalars().all()

        if not emails:
            return []

        thread_text = "\n\n---\n\n".join([
            f"From: {e.sender_name} <{e.sender_email}>\n"
            f"Date: {e.received_at}\n\n"
            f"{e.body_text or e.snippet or '[No content]'}"
            for e in emails
        ])

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"""Extract all action items from this email thread.
Return as a JSON array of strings.

Thread:
{thread_text}

Respond with just a JSON array like: ["action 1", "action 2"]""",
            }],
        )

        content = response.content[0].text
        try:
            start = content.find("[")
            end = content.rfind("]") + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
        except (json.JSONDecodeError, ValueError):
            pass
        return []

    async def semantic_search_emails(
        self, query: str, limit: int = 10
    ) -> list[dict]:
        """Perform semantic search on emails using Qdrant."""
        # TODO: Implement Qdrant vector search
        # For now, return empty list
        return []


# Singleton instance
_agent: ClaudeAgent | None = None


async def get_claude_agent() -> ClaudeAgent:
    """Get the singleton Claude agent instance."""
    global _agent
    if _agent is None:
        _agent = ClaudeAgent()
    return _agent
