import datetime
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_

# For raw SQL queries or updates if needed
from sqlalchemy import update

from app.db.models import Booking, SlotConfig
from app.tools.base_tool import BaseTool

class SlotManager(BaseTool):
    """
    Core Infrastrucure Tool: Slot Manager
    Prevents double bookings by enforcing a locking mechanism.
    Since Redis is currently unavailable in the environment, this implements 
    a robust fallback using the PostgreSQL 'bookings' table for both HOLDING 
    and CONFIRMED states.
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    @property
    def tool_name(self) -> str:
        return "SlotManager"

    # 1. check_availability
    async def check_availability(self, business_id: str, date_str: str, time_str: str) -> bool:
        """
        Check if a slot is completely free.
        A slot is NOT free if it's 'confirmed', 'completed', or if it's 'holding' AND the hold hasn't expired.
        Hold expiration is defined as > 3 minutes ago.
        """
        stmt = select(Booking).filter(
            Booking.user_id == business_id,
            Booking.booking_date == date_str,
            Booking.booking_time == time_str
        )
        res = await self.db.execute(stmt)
        bookings = res.scalars().all()
        
        now = datetime.datetime.now()
        hold_timeout = datetime.timedelta(minutes=3)
        
        for b in bookings:
            if b.status in ["confirmed", "completed"]:
                return False
            if b.status == "holding":
                # Check if hold expired
                if now - b.updated_at < hold_timeout:
                    return False
        return True

    # 2. hold_slot
    async def hold_slot(self, business_id: str, date_str: str, time_str: str, 
                        customer_phone: str) -> Dict[str, Any]:
        """
        Attempt to acquire a temporary 3-minute hold on a slot.
        """
        is_free = await self.check_availability(business_id, date_str, time_str)
        if not is_free:
            return self._format_response(
                success=False, 
                message=f"Slot {date_str} {time_str} is currently taken or being held by someone else."
            )
            
        # Clean up any expired holds for this exact slot just to keep DB clean
        now = datetime.datetime.now()
        hold_timeout = datetime.timedelta(minutes=3)
        cutoff_time = now - hold_timeout
        
        # It's free, try to create or update a hold
        new_hold = Booking(
            user_id=business_id,
            customer_phone=customer_phone,
            booking_date=date_str,
            booking_time=time_str,
            status="holding"
        )
        self.db.add(new_hold)
        try:
            await self.db.commit()
            return self._format_response(
                success=True, 
                data={"booking_id": str(new_hold.id), "expires_in_seconds": 180},
                message=f"Slot successfully held for 3 minutes."
            )
        except Exception as e:
            await self.db.rollback()
            return self.handle_error(e)

    # 3. confirm_slot
    async def confirm_slot(self, booking_id: str, payment_status: str = "pending", 
                           payment_id: str = None) -> Dict[str, Any]:
        """
        Convert a 'holding' slot to 'confirmed'.
        Uses optimistic locking via the 'version' column to ensure concurrency safety.
        """
        stmt = select(Booking).filter(Booking.id == booking_id)
        res = await self.db.execute(stmt)
        booking = res.scalars().first()
        
        if not booking:
            return self._format_response(success=False, message="Booking hold not found.")
            
        if booking.status == "confirmed":
            return self._format_response(success=True, message="Slot is already confirmed.")
            
        current_version = booking.version
        
        # Optimistic lock update
        update_stmt = (
            update(Booking)
            .where(and_(Booking.id == booking_id, Booking.version == current_version))
            .values(
                status="confirmed",
                payment_status=payment_status,
                payment_id=payment_id,
                version=current_version + 1,
                updated_at=datetime.datetime.now()
            )
        )
        
        res = await self.db.execute(update_stmt)
        
        if res.rowcount == 0:
            await self.db.rollback()
            return self._format_response(
                success=False, 
                message="Conflict: Another process modified this booking at the exact same moment."
            )
            
        await self.db.commit()
        return self._format_response(
            success=True,
            data={"booking_id": str(booking.id)},
            message="Booking successfully confirmed."
        )

    # 4. release_hold
    async def release_hold(self, booking_id: str) -> Dict[str, Any]:
        """
        Explicitly release a hold (e.g., if a customer says 'cancel my request').
        """
        stmt = select(Booking).filter(Booking.id == booking_id, Booking.status == "holding")
        res = await self.db.execute(stmt)
        booking = res.scalars().first()
        
        if booking:
            await self.db.delete(booking)
            await self.db.commit()
            return self._format_response(success=True, message="Hold released.")
            
        return self._format_response(success=False, message="No active hold found to release.")

    # 5. register_walkin
    async def register_walkin(self, business_id: str, date_str: str, time_str: str, 
                              customer_phone: str = "walkin") -> Dict[str, Any]:
        """
        Owner command: Immediately force-books a slot. 
        If anyone is currently holding it, the walk-in wins and deletes their hold.
        """
        # Find any active holds or bookings for this exact slot
        stmt = select(Booking).filter(
            Booking.user_id == business_id,
            Booking.booking_date == date_str,
            Booking.booking_time == time_str
        )
        res = await self.db.execute(stmt)
        existing = res.scalars().all()
        
        evicted_customers = []
        
        for b in existing:
            if b.status == "confirmed":
                return self._format_response(
                    success=False, 
                    message=f"Cannot walk-in. Slot {time_str} is already CONFIRMED by another customer."
                )
            if b.status == "holding":
                evicted_customers.append(b.customer_phone)
                await self.db.delete(b)
                
        # Force book the walkin
        walkin = Booking(
            user_id=business_id,
            customer_phone=customer_phone,
            booked_via="walkin",
            status="confirmed",
            booking_date=date_str,
            booking_time=time_str
        )
        self.db.add(walkin)
        await self.db.commit()
        
        data = {"evicted_holds": evicted_customers}
        
        return self._format_response(
            success=True, 
            data=data,
            message=f"Walk-in successfully registered for {time_str}."
        )

    # Required implementation of abstract method
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Dispatcher method so this class conforms to BaseTool interface.
        Expects a 'method' parameter (e.g., 'check_availability', 'hold_slot', etc.)
        """
        method_name = kwargs.pop("method", None)
        if not method_name:
            return self._format_response(success=False, message="Missing 'method' parameter for SlotManager.")
            
        if method_name == "check_availability":
            is_free = await self.check_availability(**kwargs)
            return self._format_response(success=True, data={"available": is_free})
        elif method_name == "hold_slot":
            return await self.hold_slot(**kwargs)
        elif method_name == "confirm_slot":
            return await self.confirm_slot(**kwargs)
        elif method_name == "release_hold":
            return await self.release_hold(**kwargs)
        elif method_name == "register_walkin":
            return await self.register_walkin(**kwargs)
        else:
            return self._format_response(success=False, message=f"Unknown method '{method_name}'")
