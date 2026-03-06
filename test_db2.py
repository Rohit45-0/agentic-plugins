import asyncio
from app.db.base import AsyncSessionLocal
from app.db.models import WhatsAppBotConfig, SlotConfig
from sqlalchemy.future import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(WhatsAppBotConfig))
        configs = res.scalars().all()
        for c in configs:
            print(f"Bot Config: {c.id}")
            print(f"  Phone Number: {c.phone_number_id}")
            print(f"  Is Active: {c.is_active}")
            print(f"  Slot Config ID: {c.slot_config_id}")
            print(f"  Has Calendar Token: {bool(c.google_calendar_token)}")
            if c.slot_config_id:
                s_res = await db.execute(select(SlotConfig).filter(SlotConfig.id == c.slot_config_id))
                s = s_res.scalar_one_or_none()
                if s:
                    print(f"  Slot Config: {s.id}")
                else:
                    print(f"  Slot Config: Not Found matching ID!")

if __name__ == "__main__":
    asyncio.run(main())
