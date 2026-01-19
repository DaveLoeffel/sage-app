"""Entrata Email Report Parser MCP server.

Since Entrata doesn't provide a public API, this MCP server parses
property metrics from emailed reports (daily/weekly summaries).

Reports are parsed from emails in the Gmail inbox and stored in the database
for trend analysis and reporting.
"""

import re
from datetime import datetime, date
from typing import Any

from fastmcp import FastMCP
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sage.config import get_settings
from sage.services.database import async_session_maker
from sage.models.email import EmailCache

settings = get_settings()

# Initialize MCP server
mcp = FastMCP("Entrata Property Reports Parser")

# Common patterns for Entrata report emails
ENTRATA_SENDER_PATTERNS = [
    r"@entrata\.com$",
    r"noreply.*entrata",
    r"reports.*entrata",
]

ENTRATA_SUBJECT_PATTERNS = [
    r"daily.*report",
    r"weekly.*summary",
    r"occupancy.*report",
    r"property.*metrics",
    r"portfolio.*report",
]


def is_entrata_report(email: EmailCache) -> bool:
    """Check if an email is an Entrata report."""
    sender = email.sender_email.lower()
    subject = email.subject.lower()

    # Check sender
    for pattern in ENTRATA_SENDER_PATTERNS:
        if re.search(pattern, sender, re.IGNORECASE):
            return True

    # Check subject
    for pattern in ENTRATA_SUBJECT_PATTERNS:
        if re.search(pattern, subject, re.IGNORECASE):
            return True

    return False


def parse_percentage(text: str) -> float | None:
    """Extract percentage value from text."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if match:
        return float(match.group(1))
    return None


def parse_currency(text: str) -> float | None:
    """Extract currency value from text."""
    match = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", text)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def parse_number(text: str) -> int | None:
    """Extract integer from text."""
    match = re.search(r"(\d+)", text)
    if match:
        return int(match.group(1))
    return None


@mcp.tool()
async def parse_property_report(email_id: int) -> dict[str, Any]:
    """
    Parse property metrics from an Entrata report email.

    Args:
        email_id: The database ID of the email to parse

    Returns:
        Parsed property metrics including occupancy, rent, and unit counts
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(EmailCache).where(EmailCache.id == email_id)
        )
        email = result.scalar_one_or_none()

        if not email:
            return {"error": f"Email {email_id} not found"}

        if not is_entrata_report(email):
            return {"error": "Email does not appear to be an Entrata report"}

        body = email.body_text or ""

        # Extract metrics using various patterns
        metrics = {
            "email_id": email_id,
            "report_date": email.received_at.isoformat(),
            "subject": email.subject,
            "properties": [],
        }

        # Try to parse overall portfolio metrics
        portfolio_metrics = parse_portfolio_metrics(body)
        if portfolio_metrics:
            metrics["portfolio"] = portfolio_metrics

        # Try to parse individual property metrics
        property_sections = extract_property_sections(body)
        for prop_name, prop_text in property_sections:
            prop_metrics = parse_property_metrics(prop_name, prop_text)
            if prop_metrics:
                metrics["properties"].append(prop_metrics)

        return metrics


def parse_portfolio_metrics(body: str) -> dict[str, Any] | None:
    """Parse portfolio-level metrics from report body."""
    metrics = {}

    # Occupancy patterns
    occ_patterns = [
        r"portfolio\s+occupancy[:\s]*(\d+(?:\.\d+)?)\s*%",
        r"overall\s+occupancy[:\s]*(\d+(?:\.\d+)?)\s*%",
        r"total\s+occupancy[:\s]*(\d+(?:\.\d+)?)\s*%",
    ]
    for pattern in occ_patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            metrics["occupancy_percent"] = float(match.group(1))
            break

    # Units patterns
    units_patterns = [
        r"total\s+units[:\s]*(\d+)",
        r"portfolio\s+units[:\s]*(\d+)",
        r"(\d+)\s+total\s+units",
    ]
    for pattern in units_patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            metrics["total_units"] = int(match.group(1))
            break

    # Occupied units
    occ_units_patterns = [
        r"occupied\s+units[:\s]*(\d+)",
        r"(\d+)\s+occupied",
    ]
    for pattern in occ_units_patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            metrics["occupied_units"] = int(match.group(1))
            break

    # Average rent
    rent_patterns = [
        r"average\s+rent[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
        r"avg\s+rent[:\s]*\$\s*([\d,]+(?:\.\d{2})?)",
    ]
    for pattern in rent_patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            metrics["average_rent"] = float(match.group(1).replace(",", ""))
            break

    return metrics if metrics else None


def extract_property_sections(body: str) -> list[tuple[str, str]]:
    """Extract individual property sections from report."""
    sections = []

    # Try to find property name headers
    # Common patterns: "Property Name:", "--- Property Name ---", etc.
    patterns = [
        r"(?:^|\n)([A-Z][A-Za-z\s]+(?:Apartments|Residences|Place|Court|Park))[\s:]*\n([\s\S]+?)(?=(?:^|\n)[A-Z][A-Za-z\s]+(?:Apartments|Residences|Place|Court|Park)|$)",
        r"Property:\s*([^\n]+)\n([\s\S]+?)(?=Property:|$)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, body, re.MULTILINE)
        if matches:
            sections.extend(matches)
            break

    return sections


def parse_property_metrics(name: str, text: str) -> dict[str, Any] | None:
    """Parse metrics for a single property."""
    metrics = {
        "name": name.strip(),
    }

    # Occupancy
    occ = parse_percentage(text)
    if occ:
        metrics["occupancy_percent"] = occ

    # Look for specific metrics
    patterns = {
        "total_units": r"(?:total\s+)?units[:\s]*(\d+)",
        "occupied_units": r"occupied[:\s]*(\d+)",
        "vacant_units": r"vacant[:\s]*(\d+)",
        "notice_units": r"(?:on\s+)?notice[:\s]*(\d+)",
        "avg_rent": r"(?:avg|average)\s+rent[:\s]*\$\s*([\d,]+)",
        "market_rent": r"market\s+rent[:\s]*\$\s*([\d,]+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).replace(",", "")
            metrics[key] = float(value) if "rent" in key else int(value)

    return metrics if len(metrics) > 1 else None


@mcp.tool()
async def get_recent_reports(
    days: int = 7,
    property_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get recently parsed property reports.

    Args:
        days: Number of days to look back (default: 7)
        property_name: Filter by property name (optional)

    Returns:
        List of parsed report summaries
    """
    async with async_session_maker() as db:
        # Find Entrata report emails from the last N days
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)

        result = await db.execute(
            select(EmailCache).where(
                EmailCache.received_at >= cutoff
            ).order_by(EmailCache.received_at.desc())
        )
        emails = result.scalars().all()

        reports = []
        for email in emails:
            if is_entrata_report(email):
                parsed = await parse_property_report(email.id)
                if "error" not in parsed:
                    # Filter by property name if specified
                    if property_name:
                        parsed["properties"] = [
                            p for p in parsed.get("properties", [])
                            if property_name.lower() in p.get("name", "").lower()
                        ]
                    reports.append(parsed)

        return reports


@mcp.tool()
async def get_occupancy_trend(
    property_name: str,
    days: int = 30,
) -> dict[str, Any]:
    """
    Get occupancy trend for a specific property over time.

    Args:
        property_name: Name of the property to track
        days: Number of days to include (default: 30)

    Returns:
        Occupancy data points over time for trend analysis
    """
    reports = await get_recent_reports(days=days, property_name=property_name)

    data_points = []
    for report in reports:
        for prop in report.get("properties", []):
            if property_name.lower() in prop.get("name", "").lower():
                data_points.append({
                    "date": report.get("report_date"),
                    "occupancy_percent": prop.get("occupancy_percent"),
                    "occupied_units": prop.get("occupied_units"),
                    "total_units": prop.get("total_units"),
                })

    # Sort by date
    data_points.sort(key=lambda x: x.get("date", ""))

    return {
        "property_name": property_name,
        "period_days": days,
        "data_points": data_points,
        "latest_occupancy": data_points[-1].get("occupancy_percent") if data_points else None,
        "trend": calculate_trend(data_points) if len(data_points) >= 2 else None,
    }


def calculate_trend(data_points: list[dict]) -> str:
    """Calculate if occupancy is trending up, down, or stable."""
    if len(data_points) < 2:
        return "insufficient_data"

    values = [p.get("occupancy_percent") for p in data_points if p.get("occupancy_percent")]
    if len(values) < 2:
        return "insufficient_data"

    first_half = sum(values[:len(values)//2]) / (len(values)//2)
    second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)

    diff = second_half - first_half
    if diff > 1:
        return "increasing"
    elif diff < -1:
        return "decreasing"
    else:
        return "stable"


# Run the MCP server
if __name__ == "__main__":
    mcp.run()
