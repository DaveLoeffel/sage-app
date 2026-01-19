#!/usr/bin/env python3
"""One-time script to sync Plaud-labeled emails from Gmail."""

import asyncio
import sys
from pathlib import Path

# Add the backend to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sage.config import get_settings
from sage.services.database import async_session_maker
from sage.core.email_processor import EmailProcessor


async def sync_plaud_emails():
    """Sync emails with the 'Plaud' Gmail label."""
    settings = get_settings()

    async with async_session_maker() as db:
        processor = EmailProcessor(db)

        # Sync emails with the Plaud label
        query = "label:Plaud"
        print(f"Syncing emails with query: {query}")

        synced_count = await processor.sync_emails_by_query(query=query, max_results=500)
        await db.commit()

        print(f"Synced {synced_count} Plaud-labeled emails")

        return synced_count


if __name__ == "__main__":
    result = asyncio.run(sync_plaud_emails())
    print(f"\nDone! Total synced: {result}")
