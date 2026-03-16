"""
Migration: Add google_sheet_id column to whatsapp_bot_configs
=============================================================
Adds a dedicated sheet id field so Sheets tools do not conflict with google_doc_id.

Usage:
    python scripts/migrate_add_google_sheet_id.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text

from app.db.base import engine as async_engine


async def migrate():
    async with async_engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'whatsapp_bot_configs'
                  AND column_name = 'google_sheet_id'
                """
            )
        )
        exists = result.fetchone()
        if exists:
            print("Column 'google_sheet_id' already exists. No migration needed.")
            return

        await conn.execute(
            text(
                """
                ALTER TABLE whatsapp_bot_configs
                ADD COLUMN google_sheet_id VARCHAR NULL
                """
            )
        )
        print("Added 'google_sheet_id' column to whatsapp_bot_configs.")

    await async_engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(migrate())
