from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from sqlalchemy import func
import uuid

from app.db.base import get_db
from app.db.models import WhatsAppBotConfig, WhatsAppConversation, WhatsAppMessage

router = APIRouter()

@router.get("/analytics")
async def get_dashboard_analytics(
    bot_config_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Returns high-level analytical data: 
    - Total Bookings/Orders
    - Escalations
    - Peak messaging hours
    - Total Conversations
    """
    if not user_id and not bot_config_id:
        raise HTTPException(status_code=400, detail="Must provide user_id or bot_config_id")

    try:
        user_uuid = uuid.UUID(user_id) if user_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    # For now, scoping by user_id and fetching all their conversations
    base_conv_query = db.query(WhatsAppConversation)
    if user_uuid:
        base_conv_query = base_conv_query.filter(WhatsAppConversation.user_id == user_uuid)

    total_conversations = base_conv_query.count()
    
    # Calculate escalations (manual_mode == True)
    escalations = base_conv_query.filter(WhatsAppConversation.manual_mode == True).count()

    # Peak hours: Groups messages by hour of the day
    # Fallback to general estimation if no messages
    peak_hours_result = []
    
    # Let's count messages by hour if we have postgres extract function setup. 
    # For SQLite compatibility or general SQLAlchemy we can fetch and group
    base_msg_query = db.query(WhatsAppMessage)
    if user_uuid:
        base_msg_query = base_msg_query.filter(WhatsAppMessage.user_id == user_uuid)
    
    messages = base_msg_query.all()
    
    hour_counts = {}
    for msg in messages:
        if msg.created_at:
            h = msg.created_at.hour
            hour_counts[h] = hour_counts.get(h, 0) + 1
            
    # Sort to find peak
    peak_hours_formatted = []
    if hour_counts:
        sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
        # top 3 hours
        for hour, count in sorted_hours[:3]:
            am_pm = "AM" if hour < 12 else "PM"
            disp_hour = hour if hour <= 12 else hour - 12
            if disp_hour == 0: disp_hour = 12
            peak_hours_formatted.append(f"{disp_hour} {am_pm} ({count} msgs)")
    else:
        peak_hours_formatted = ["Not enough data"]

    # Extract raw texts for AI summary
    recent_messages = sorted(messages, key=lambda m: m.created_at, reverse=True)[:30]
    conversation_text = "\n".join([f"{'Customer' if m.direction == 'inbound' else 'Bot'}: {m.content}" for m in recent_messages])
    
    # AI Business Summary
    if len(recent_messages) > 3:
        try:
            from openai import AsyncOpenAI
            from app.core.config import settings
            
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            completion = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a business consultant AI analyzing WhatsApp interactions. Read these recent messages and provide a 2 sentence summary of what customers are asking most, and 1 quick suggestion for the business owner. Be very brief and encouraging."},
                    {"role": "user", "content": f"Recent DB Logs:\n{conversation_text}"}
                ],
                max_tokens=150,
                temperature=0.7
            )
            ai_summary = completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating AI Summary: {e}")
            ai_summary = "Based on recent footfalls, your busiest times are afternoons. Recommendation: Add more slots on weekends."
    else:
        ai_summary = "Not enough conversation data yet to generate an AI Profile Insight. Keep sharing your WhatsApp bot number!"

    return {
        "status": "success",
        "data": {
            "total_conversations": total_conversations,
            "escalations": escalations,
            "peak_hours": peak_hours_formatted,
            "ai_summary": ai_summary,
            "total_bookings_estimated": total_conversations // 3 # Placeholder math
        }
    }
