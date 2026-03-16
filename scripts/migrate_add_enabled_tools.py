"""
Migration: Add enabled_tools column to whatsapp_bot_configs
============================================================
Adds the 'enabled_tools' JSON column to the whatsapp_bot_configs table.
This stores the user's tool toggle preferences from the Settings UI.

Usage:
    python scripts/migrate_add_enabled_tools.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from app.db.base import engine as async_engine


async def migrate():
    async with async_engine.begin() as conn:
        # Check if column already exists
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'whatsapp_bot_configs' AND column_name = 'enabled_tools'
        """))
        exists = result.fetchone()
        
        if exists:
            print("✅ Column 'enabled_tools' already exists. No migration needed.")
            return
        
        # Add the column
        await conn.execute(text("""
            ALTER TABLE whatsapp_bot_configs 
            ADD COLUMN enabled_tools JSON DEFAULT NULL
        """))
        print("✅ Added 'enabled_tools' column to whatsapp_bot_configs table.")
    
    await async_engine.dispose()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(migrate())
