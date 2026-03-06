from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid

from app.db.base import get_db
from app.api.deps import get_current_user
from app.db.models import SlotConfig, WhatsAppBotConfig, User

router = APIRouter()

# --- Schemas ---
class SlotConfigUpdateRequest(BaseModel):
    user_id: str
    bot_config_id: str
    working_hours: Dict[str, Any]
    slot_duration_minutes: int
    max_capacity_per_slot: int


# --- Endpoints ---
@router.post("/config")
async def upsert_slot_config(
    payload: SlotConfigUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates or updates the working hours and booking rules for a specific WhatsApp bot.
    """
    try:
        user_uuid = current_user.id
        bot_uuid = uuid.UUID(payload.bot_config_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bot_config_id format")

    # Verify bot config exists
    res_bot = await db.execute(select(WhatsAppBotConfig).filter(
        WhatsAppBotConfig.id == bot_uuid,
        WhatsAppBotConfig.user_id == current_user.id
    ))
    bot_config = res_bot.scalar_one_or_none()

    if not bot_config:
        raise HTTPException(status_code=404, detail="Bot config not found for this user")

    # Check if a SlotConfig already exists for this bot
    if bot_config.slot_config_id:
        res_slot = await db.execute(select(SlotConfig).filter(SlotConfig.id == bot_config.slot_config_id))
        slot_config = res_slot.scalar_one_or_none()
        if not slot_config:
            # Fallback if ID is present but record was deleted
            slot_config = SlotConfig(
                user_id=user_uuid,
            )
            db.add(slot_config)
            await db.flush()
            bot_config.slot_config_id = slot_config.id
    else:
        # Create new slot config
        slot_config = SlotConfig(
            user_id=user_uuid,
        )
        db.add(slot_config)
        await db.flush()
        bot_config.slot_config_id = slot_config.id

    # Update fields
    slot_config.working_hours = payload.working_hours
    slot_config.slot_duration_minutes = payload.slot_duration_minutes
    slot_config.max_capacity_per_slot = payload.max_capacity_per_slot

    await db.commit()

    return {
        "status": "success",
        "message": "Slot configuration updated successfully",
        "data": {
            "slot_config_id": str(slot_config.id),
            "working_hours": slot_config.working_hours,
            "slot_duration_minutes": slot_config.slot_duration_minutes,
            "max_capacity_per_slot": slot_config.max_capacity_per_slot,
        }
    }

@router.get("/config/{bot_config_id}")
async def get_slot_config(
    bot_config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves the booking rules for a specific bot.
    """
    try:
        bot_uuid = uuid.UUID(bot_config_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bot_config_id format")

    res_bot = await db.execute(select(WhatsAppBotConfig).filter(
        WhatsAppBotConfig.id == bot_uuid,
        WhatsAppBotConfig.user_id == current_user.id
    ))
    bot_config = res_bot.scalar_one_or_none()
    if not bot_config:
        raise HTTPException(status_code=404, detail="Bot config not found")
        
    if not bot_config.slot_config_id:
        return {"data": None}
        
    res_slot = await db.execute(select(SlotConfig).filter(SlotConfig.id == bot_config.slot_config_id))
    slot_config = res_slot.scalar_one_or_none()
    if not slot_config:
        return {"data": None}
        
    return {
        "data": {
            "slot_config_id": str(slot_config.id),
            "working_hours": slot_config.working_hours,
            "slot_duration_minutes": slot_config.slot_duration_minutes,
            "max_capacity_per_slot": slot_config.max_capacity_per_slot,
        }
    }
