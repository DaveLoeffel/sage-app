"""Fireflies.ai service for meeting transcripts."""

from datetime import datetime, timezone
from typing import Any

import httpx

from sage.config import get_settings

settings = get_settings()

FIREFLIES_API_URL = "https://api.fireflies.ai/graphql"


def _convert_fireflies_date(date_value: int | str | None) -> str | None:
    """Convert Fireflies date (Unix timestamp in milliseconds) to ISO format."""
    if date_value is None:
        return None
    try:
        if isinstance(date_value, int):
            # Fireflies returns Unix timestamp in milliseconds
            dt = datetime.fromtimestamp(date_value / 1000, tz=timezone.utc)
            return dt.isoformat()
        elif isinstance(date_value, str):
            # Already a string, return as-is
            return date_value
    except (ValueError, OSError):
        pass
    return None


def _convert_duration(duration: float | int | None) -> int | None:
    """Convert Fireflies duration (float minutes) to integer."""
    if duration is None:
        return None
    return round(duration)


def _to_list(value: str | list | None) -> list[str]:
    """Convert a string or list to a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Split by newlines and filter empty lines
        lines = [line.strip() for line in value.split('\n') if line.strip()]
        return lines
    return []


class FirefliesService:
    """Service for interacting with Fireflies.ai API."""

    def __init__(self):
        self.api_key = settings.fireflies_api_key

    @property
    def is_configured(self) -> bool:
        """Check if Fireflies API key is configured."""
        return bool(self.api_key)

    async def _graphql_request(
        self, query: str, variables: dict | None = None
    ) -> dict[str, Any]:
        """Make a GraphQL request to Fireflies API."""
        if not self.is_configured:
            raise ValueError("Fireflies API key not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                FIREFLIES_API_URL,
                json={"query": query, "variables": variables or {}},
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def list_recent_meetings(self, limit: int = 10) -> list[dict[str, Any]]:
        """List recent meeting transcripts."""
        query = """
        query RecentTranscripts($limit: Int) {
            transcripts(limit: $limit) {
                id
                title
                date
                duration
                participants
                meeting_attendees {
                    name
                    email
                }
            }
        }
        """

        result = await self._graphql_request(query, {"limit": min(limit, 50)})
        transcripts = result.get("data", {}).get("transcripts", [])

        return [
            {
                "id": t["id"],
                "title": t.get("title", "Untitled Meeting"),
                "date": _convert_fireflies_date(t.get("date")),
                "duration_minutes": _convert_duration(t.get("duration")),
                "participants": [
                    a.get("email") or a.get("name")
                    for a in t.get("meeting_attendees", [])
                ],
            }
            for t in transcripts
        ]

    async def get_meeting_transcript(self, meeting_id: str) -> dict[str, Any] | None:
        """Get the full transcript of a specific meeting."""
        query = """
        query GetTranscript($id: String!) {
            transcript(id: $id) {
                id
                title
                date
                duration
                participants
                meeting_attendees {
                    name
                    email
                }
                sentences {
                    speaker_name
                    text
                    start_time
                    end_time
                }
                summary {
                    overview
                    shorthand_bullet
                    action_items
                    keywords
                }
            }
        }
        """

        result = await self._graphql_request(query, {"id": meeting_id})
        transcript = result.get("data", {}).get("transcript")

        if not transcript:
            return None

        # Format the transcript
        formatted_transcript = []
        for sentence in transcript.get("sentences", []):
            formatted_transcript.append(
                {
                    "speaker": sentence.get("speaker_name", "Unknown"),
                    "text": sentence.get("text", ""),
                    "timestamp": sentence.get("start_time"),
                }
            )

        summary = transcript.get("summary", {})

        return {
            "id": transcript["id"],
            "title": transcript.get("title", "Untitled Meeting"),
            "date": _convert_fireflies_date(transcript.get("date")),
            "duration_minutes": _convert_duration(transcript.get("duration")),
            "participants": [
                a.get("email") or a.get("name")
                for a in transcript.get("meeting_attendees", [])
            ],
            "summary": summary.get("overview"),
            "key_points": _to_list(summary.get("shorthand_bullet")),
            "action_items": _to_list(summary.get("action_items")),
            "keywords": _to_list(summary.get("keywords")),
            "transcript": formatted_transcript,
        }

    async def get_meeting_summary(self, meeting_id: str) -> dict[str, Any] | None:
        """Get just the AI-generated summary and action items from a meeting."""
        query = """
        query GetMeetingSummary($id: String!) {
            transcript(id: $id) {
                id
                title
                date
                summary {
                    overview
                    shorthand_bullet
                    action_items
                    keywords
                    outline
                }
            }
        }
        """

        result = await self._graphql_request(query, {"id": meeting_id})
        transcript = result.get("data", {}).get("transcript")

        if not transcript:
            return None

        summary = transcript.get("summary", {})

        return {
            "id": transcript["id"],
            "title": transcript.get("title", "Untitled Meeting"),
            "date": _convert_fireflies_date(transcript.get("date")),
            "overview": summary.get("overview"),
            "key_points": _to_list(summary.get("shorthand_bullet")),
            "action_items": _to_list(summary.get("action_items")),
            "keywords": _to_list(summary.get("keywords")),
            "outline": _to_list(summary.get("outline")),
        }

    async def search_meetings(
        self,
        search_query: str = "",
        participant_email: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for meetings by keyword or participant."""
        gql_query = """
        query SearchTranscripts($limit: Int) {
            transcripts(limit: $limit) {
                id
                title
                date
                duration
                participants
                meeting_attendees {
                    name
                    email
                }
                summary {
                    overview
                }
            }
        }
        """

        result = await self._graphql_request(
            gql_query, {"limit": 100}
        )  # Fetch more for filtering
        transcripts = result.get("data", {}).get("transcripts", [])

        # Filter results
        filtered = []
        for t in transcripts:
            # Check query match
            if search_query:
                title = t.get("title", "").lower()
                overview = t.get("summary", {}).get("overview", "").lower()
                query_lower = search_query.lower()

                if query_lower not in title and query_lower not in overview:
                    continue

            # Check participant filter
            if participant_email:
                attendees = t.get("meeting_attendees", [])
                emails = [a.get("email", "").lower() for a in attendees if a.get("email")]
                if participant_email.lower() not in emails:
                    continue

            # Check date filters
            meeting_date_raw = t.get("date")
            if meeting_date_raw and (start_date or end_date):
                try:
                    # Convert from milliseconds timestamp
                    if isinstance(meeting_date_raw, int):
                        meeting_dt = datetime.fromtimestamp(
                            meeting_date_raw / 1000, tz=timezone.utc
                        )
                    else:
                        meeting_dt = datetime.fromisoformat(
                            str(meeting_date_raw).replace("Z", "+00:00")
                        )
                    if start_date:
                        start_dt = datetime.fromisoformat(start_date)
                        if meeting_dt < start_dt:
                            continue
                    if end_date:
                        end_dt = datetime.fromisoformat(end_date)
                        if meeting_dt > end_dt:
                            continue
                except (ValueError, OSError):
                    pass

            filtered.append(
                {
                    "id": t["id"],
                    "title": t.get("title", "Untitled Meeting"),
                    "date": _convert_fireflies_date(t.get("date")),
                    "duration_minutes": _convert_duration(t.get("duration")),
                    "participants": [
                        a.get("email") or a.get("name")
                        for a in t.get("meeting_attendees", [])
                    ],
                    "summary_preview": (t.get("summary") or {}).get("overview", "")[:200],
                }
            )

            if len(filtered) >= limit:
                break

        return filtered


# Singleton instance
_fireflies_service: FirefliesService | None = None


def get_fireflies_service() -> FirefliesService:
    """Get or create the Fireflies service instance."""
    global _fireflies_service
    if _fireflies_service is None:
        _fireflies_service = FirefliesService()
    return _fireflies_service
