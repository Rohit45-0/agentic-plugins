import json
from datetime import datetime, timedelta
import redis.asyncio as redis
from sqlalchemy.orm import Session
from app.db.models import SlotConfig
from app.core.config import settings

# Shared Redis client for locks
_redis_url = settings.REDIS_URL
redis_client = redis.from_url(_redis_url)

async def generate_available_slots(db: Session, slot_config_id: str, target_date: datetime):
    """
    Given a merchant's SlotConfig and a date, generates all mathematically 
    possible slots based on their working hours and duration.
    Does NOT check Google Calendar yet.
    """
    config = db.query(SlotConfig).filter(SlotConfig.id == slot_config_id).first()
    if not config:
        return []

    day_of_week = target_date.strftime("%A").lower()
    
    # E.g. [{"start": "09:00", "end": "13:00"}, {"start": "14:00", "end": "17:00"}]
    # Handle if working_hours is a string instead of dict due to older setups
    hours = config.working_hours
    if isinstance(hours, str):
        try:
            hours = json.loads(hours)
        except Exception:
            hours = {}

    todays_blocks = hours.get(day_of_week, [])
    
    possible_slots = []
    
    for block in todays_blocks:
        start_time_str = block.get("start")
        end_time_str = block.get("end")
        if not start_time_str or not end_time_str:
            continue
            
        start_dt = datetime.combine(target_date.date(), datetime.strptime(start_time_str, "%H:%M").time())
        end_dt = datetime.combine(target_date.date(), datetime.strptime(end_time_str, "%H:%M").time())
        
        current_slot_start = start_dt
        while current_slot_start + timedelta(minutes=config.slot_duration_minutes) <= end_dt:
            possible_slots.append({
                "start": current_slot_start.strftime("%Y-%m-%d %H:%M"),
                "end": (current_slot_start + timedelta(minutes=config.slot_duration_minutes)).strftime("%Y-%m-%d %H:%M")
            })
            current_slot_start += timedelta(minutes=config.slot_duration_minutes)
            
    return possible_slots


async def get_final_available_slots(db: Session, bot_config_id: str, target_date: datetime):
    """
    1. Gets mathematical slots from rules.
    2. Queries Google Calendar for busy periods.
    3. Filters busy slots out.
    """
    from app.db.models import WhatsAppBotConfig
    bot_config = db.query(WhatsAppBotConfig).filter(WhatsAppBotConfig.id == bot_config_id).first()
    
    if not bot_config or not bot_config.slot_config_id:
        return []
        
    possible_slots = await generate_available_slots(db, bot_config.slot_config_id, target_date)
    if not possible_slots:
        return []

    # Get live Google Calendar service
    from app.api.calendar import get_calendar_service
    service = get_calendar_service(db, bot_config_id)
    if not service:
        # If they haven't connected a calendar, everything mathematically generated is "free"
        return possible_slots

    # Determine start and end of search space
    min_time = datetime.strptime(possible_slots[0]["start"], "%Y-%m-%d %H:%M")
    max_time = datetime.strptime(possible_slots[-1]["end"], "%Y-%m-%d %H:%M")
    
    # Needs to be RFC 3339 formatted with a tz indicator (default to IST or user's local, assuming IST given +05:30)
    import pytz
    ist = pytz.timezone("Asia/Kolkata")
    
    # Note: freebusy returns UTC, so localize properly
    time_min_str = ist.localize(min_time).isoformat()
    time_max_str = ist.localize(max_time).isoformat()

    try:
        body = {
            "timeMin": time_min_str,
            "timeMax": time_max_str,
            "timeZone": "Asia/Kolkata",
            "items": [{"id": "primary"}]
        }
        
        eventsResult = service.freebusy().query(body=body).execute()
        busy_spans = eventsResult.get("calendars", {}).get("primary", {}).get("busy", [])
        
        # Filter possible_slots
        available_slots = []
        for p_slot in possible_slots:
            slot_start = ist.localize(datetime.strptime(p_slot["start"], "%Y-%m-%d %H:%M"))
            slot_end = ist.localize(datetime.strptime(p_slot["end"], "%Y-%m-%d %H:%M"))
            
            is_busy = False
            for span in busy_spans:
                busy_start = datetime.fromisoformat(span["start"].replace('Z', '+00:00'))
                busy_end = datetime.fromisoformat(span["end"].replace('Z', '+00:00'))
                
                # Check overlap
                if max(slot_start, busy_start) < min(slot_end, busy_end):
                    is_busy = True
                    break
                    
            if not is_busy:
                available_slots.append(p_slot)
                
        return available_slots

    except Exception as e:
        print(f"Error checking Google Calendar freebusy: {e}")
        return possible_slots  # Fallback gracefully



async def acquire_slot_lock(slot_config_id: str, slot_start_time: str, customer_phone: str) -> bool:
    """
    Attempts to lock a specific slot in Redis to prevent double booking.
    Returns True if successful, False if someone else holds the lock.
    """
    lock_key = f"lock:slot:{slot_config_id}:{slot_start_time}"
    
    # NX = strictly Set if Not Exists
    # EX 60 = Expire lock automatically in 60 seconds if it crashes
    acquired = await redis_client.set(lock_key, customer_phone, nx=True, ex=60)
    
    return bool(acquired)


async def release_slot_lock(slot_config_id: str, slot_start_time: str, customer_phone: str):
    """
    Releases the slot lock after Google Calendar confirms the booking, 
    but only if THIS customer owns the lock.
    """
    lock_key = f"lock:slot:{slot_config_id}:{slot_start_time}"
    
    # Fetch current owner
    current_owner = await redis_client.get(lock_key)
    if current_owner and current_owner.decode("utf-8") == customer_phone:
        await redis_client.delete(lock_key)


async def create_calendar_event(db: Session, bot_config_id: str, customer_phone: str, date_time_str: str) -> bool:
    """
    Creates the actual event in Google Calendar once the slot is locked.
    date_time_str should be 'YYYY-MM-DD HH:MM'
    """
    from app.db.models import WhatsAppBotConfig, SlotConfig
    from app.api.calendar import get_calendar_service
    import pytz
    
    bot_config = db.query(WhatsAppBotConfig).filter(WhatsAppBotConfig.id == bot_config_id).first()
    if not bot_config or not bot_config.slot_config_id:
        return False
        
    slot_config = db.query(SlotConfig).filter(SlotConfig.id == bot_config.slot_config_id).first()
    duration_mins = slot_config.slot_duration_minutes if slot_config else 15
    
    service = get_calendar_service(db, bot_config_id)
    if not service:
        # No calendar connected, we just pretend it succeeded (it's locked in our DB conceptually)
        return True

    try:
        ist = pytz.timezone("Asia/Kolkata")
        start_dt = ist.localize(datetime.strptime(date_time_str, "%Y-%m-%d %H:%M"))
        end_dt = start_dt + timedelta(minutes=duration_mins)

        event = {
            'summary': f'Booking - {customer_phone}',
            'description': f'Automatically booked via Catalyst Nexus WhatsApp Bot for number {customer_phone}.',
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
        }

        service.events().insert(calendarId='primary', body=event).execute()
        return True
    except Exception as e:
        print(f"Failed to create Google Calendar event: {e}")
        return False


def cancel_calendar_events(db: Session, bot_config_id: str, customer_phone: str, target_date_str: str) -> int:
    """
    Cancel (delete) all Google Calendar events for a specific customer phone on a given date.
    target_date_str should be 'YYYY-MM-DD'.
    Returns number of events cancelled.
    """
    from app.db.models import WhatsAppBotConfig
    from app.api.calendar import get_calendar_service
    import pytz

    service = get_calendar_service(db, bot_config_id)
    if not service:
        return 0

    try:
        ist = pytz.timezone("Asia/Kolkata")
        day_start = ist.localize(datetime.strptime(target_date_str, "%Y-%m-%d"))
        day_end = day_start + timedelta(days=1)

        # Search for events on that day that match the customer phone
        events_result = service.events().list(
            calendarId='primary',
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            q=customer_phone,  # Search by customer phone in event summary/description
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        cancelled = 0
        for event in events:
            summary = event.get('summary', '')
            description = event.get('description', '')
            # Only delete events that belong to this customer
            if customer_phone in summary or customer_phone in description:
                service.events().delete(calendarId='primary', eventId=event['id']).execute()
                cancelled += 1

        return cancelled
    except Exception as e:
        print(f"Failed to cancel Google Calendar events: {e}")
        return 0
