"""Fireflies.ai MCP server for meeting transcripts.

This MCP server provides access to Fireflies.ai meeting transcripts and notes.
It uses the Fireflies GraphQL API to fetch meeting data.

API Documentation: https://docs.fireflies.ai/graphql-api/query/transcript
"""

from datetime import datetime
from typing import Any

import httpx
from fastmcp import FastMCP

from sage.config import get_settings

settings = get_settings()

# Initialize MCP server
mcp = FastMCP("Fireflies Meeting Transcripts")

FIREFLIES_API_URL = "https://api.fireflies.ai/graphql"


async def graphql_request(query: str, variables: dict | None = None) -> dict[str, Any]:
    """Make a GraphQL request to Fireflies API."""
    headers = {
        "Authorization": f"Bearer {settings.fireflies_api_key}",
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


@mcp.tool()
async def list_recent_meetings(limit: int = 10) -> list[dict[str, Any]]:
    """
    List recent meeting transcripts.

    Args:
        limit: Maximum number of meetings to return (default: 10, max: 50)

    Returns:
        List of meeting summaries with id, title, date, duration, and participants
    """
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

    result = await graphql_request(query, {"limit": min(limit, 50)})
    transcripts = result.get("data", {}).get("transcripts", [])

    return [
        {
            "id": t["id"],
            "title": t.get("title", "Untitled Meeting"),
            "date": t.get("date"),
            "duration_minutes": t.get("duration"),
            "participants": [
                a.get("email") or a.get("name")
                for a in t.get("meeting_attendees", [])
            ],
        }
        for t in transcripts
    ]


@mcp.tool()
async def get_meeting_transcript(meeting_id: str) -> dict[str, Any]:
    """
    Get the full transcript of a specific meeting.

    Args:
        meeting_id: The Fireflies meeting ID

    Returns:
        Meeting details including full transcript, summary, and action items
    """
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

    result = await graphql_request(query, {"id": meeting_id})
    transcript = result.get("data", {}).get("transcript")

    if not transcript:
        return {"error": f"Meeting {meeting_id} not found"}

    # Format the transcript
    formatted_transcript = []
    for sentence in transcript.get("sentences", []):
        formatted_transcript.append({
            "speaker": sentence.get("speaker_name", "Unknown"),
            "text": sentence.get("text", ""),
            "timestamp": sentence.get("start_time"),
        })

    summary = transcript.get("summary", {})

    return {
        "id": transcript["id"],
        "title": transcript.get("title", "Untitled Meeting"),
        "date": transcript.get("date"),
        "duration_minutes": transcript.get("duration"),
        "participants": [
            a.get("email") or a.get("name")
            for a in transcript.get("meeting_attendees", [])
        ],
        "summary": summary.get("overview"),
        "key_points": summary.get("shorthand_bullet", []),
        "action_items": summary.get("action_items", []),
        "keywords": summary.get("keywords", []),
        "transcript": formatted_transcript,
    }


@mcp.tool()
async def get_meeting_summary(meeting_id: str) -> dict[str, Any]:
    """
    Get just the AI-generated summary and action items from a meeting.

    Args:
        meeting_id: The Fireflies meeting ID

    Returns:
        Meeting summary including overview, key points, and action items
    """
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

    result = await graphql_request(query, {"id": meeting_id})
    transcript = result.get("data", {}).get("transcript")

    if not transcript:
        return {"error": f"Meeting {meeting_id} not found"}

    summary = transcript.get("summary", {})

    return {
        "id": transcript["id"],
        "title": transcript.get("title", "Untitled Meeting"),
        "date": transcript.get("date"),
        "overview": summary.get("overview"),
        "key_points": summary.get("shorthand_bullet", []),
        "action_items": summary.get("action_items", []),
        "keywords": summary.get("keywords", []),
        "outline": summary.get("outline", []),
    }


@mcp.tool()
async def search_meetings(
    query: str,
    participant_email: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Search for meetings by keyword or participant.

    Args:
        query: Search query (searches title and transcript content)
        participant_email: Filter by participant email (optional)
        start_date: Filter meetings after this date (ISO format, optional)
        end_date: Filter meetings before this date (ISO format, optional)
        limit: Maximum results to return (default: 10)

    Returns:
        List of matching meeting summaries
    """
    # Note: Fireflies API search capabilities may vary
    # This is a simplified implementation that filters on the client side

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

    result = await graphql_request(gql_query, {"limit": 100})  # Fetch more for filtering
    transcripts = result.get("data", {}).get("transcripts", [])

    # Filter results
    filtered = []
    for t in transcripts:
        # Check query match
        title = t.get("title", "").lower()
        overview = t.get("summary", {}).get("overview", "").lower()
        query_lower = query.lower()

        if query_lower not in title and query_lower not in overview:
            continue

        # Check participant filter
        if participant_email:
            attendees = t.get("meeting_attendees", [])
            emails = [a.get("email", "").lower() for a in attendees]
            if participant_email.lower() not in emails:
                continue

        # Check date filters
        meeting_date = t.get("date")
        if meeting_date:
            try:
                meeting_dt = datetime.fromisoformat(meeting_date.replace("Z", "+00:00"))
                if start_date:
                    start_dt = datetime.fromisoformat(start_date)
                    if meeting_dt < start_dt:
                        continue
                if end_date:
                    end_dt = datetime.fromisoformat(end_date)
                    if meeting_dt > end_dt:
                        continue
            except ValueError:
                pass

        filtered.append({
            "id": t["id"],
            "title": t.get("title", "Untitled Meeting"),
            "date": t.get("date"),
            "duration_minutes": t.get("duration"),
            "participants": [
                a.get("email") or a.get("name")
                for a in t.get("meeting_attendees", [])
            ],
            "summary_preview": t.get("summary", {}).get("overview", "")[:200],
        })

        if len(filtered) >= limit:
            break

    return filtered


@mcp.tool()
async def get_meetings_with_person(email: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Get all meetings with a specific person.

    Args:
        email: The email address of the person
        limit: Maximum meetings to return (default: 10)

    Returns:
        List of meetings that included this person
    """
    return await search_meetings(query="", participant_email=email, limit=limit)


# Run the MCP server
if __name__ == "__main__":
    mcp.run()
