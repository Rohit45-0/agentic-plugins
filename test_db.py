import asyncio
from app.db.base import AsyncSessionLocal
from app.db.models import WhatsAppBotConfig
from sqlalchemy.future import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(WhatsAppBotConfig))
        config = res.scalars().first()
        if not config:
            print("No bot config")
            return
            
        print(f"Config ID: {config.id}, type: {type(config.id)}")
        
        try:
            bot_config_id = str(config.id)
            # Try to query with string
            res2 = await db.execute(select(WhatsAppBotConfig).filter(WhatsAppBotConfig.id == bot_config_id))
            print("Successfully queried with string ID")
        except Exception as e:
            print(f"Failed query with string ID: {e}")
            
if __name__ == "__main__":
    asyncio.run(main())
