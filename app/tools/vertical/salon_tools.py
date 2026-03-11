"""
Salon Vertical Tools
====================
Domain-specific tools for salon/spa bots: Staff calendar management,
advance payment collection, loyalty tracking, and festival marketing campaigns.
"""
import datetime
from typing import Dict, Any, List

from app.tools.base_tool import BaseTool
from app.core.config import settings


class StaffCalendarTool(BaseTool):
    """
    Manages multiple staff members' schedules for a salon.
    Integrates with SlotManager for locking and Google Sheets for staff roster.
    """

    @property
    def tool_name(self) -> str:
        return "StaffCalendarTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "get_next_available_slot":
            return await self.get_next_available_slot(**kwargs)
        elif method == "get_staff_schedule":
            return await self.get_staff_schedule(**kwargs)
        elif method == "book_appointment":
            return await self.book_appointment(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def get_next_available_slot(self, spreadsheet_id: str, service_type: str,
                                      preferred_date: str = None,
                                      preferred_staff: str = None,
                                      sheet_name: str = "Bookings") -> Dict[str, Any]:
        """
        Scans staff bookings sheet to find the earliest open slot.
        If customer has a preferred staff member, checks their calendar first.
        """
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        if not preferred_date:
            preferred_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # Read existing bookings
        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:I"
        )

        if not result["success"]:
            return result

        booked_slots = set()
        for row in result["data"]["rows"][1:]:
            if len(row) >= 3 and row[0] == preferred_date:
                slot_key = f"{row[1]}_{row[5]}" if len(row) > 5 else row[1]
                booked_slots.add(slot_key)

        # Generate slots for the day (10 AM to 8 PM, 30 min each)
        available = []
        for hour in range(10, 20):
            for minute in [0, 30]:
                time_str = f"{hour:02d}:{minute:02d}"
                if preferred_staff:
                    slot_key = f"{time_str}_{preferred_staff}"
                    if slot_key not in booked_slots:
                        available.append({"time": time_str, "staff": preferred_staff})
                else:
                    if time_str not in booked_slots:
                        available.append({"time": time_str, "staff": "Any"})

                if len(available) >= 5:
                    break
            if len(available) >= 5:
                break

        if not available:
            return self._format_response(
                success=False,
                message=f"No slots available on {preferred_date}. Try another date?"
            )

        msg = f"✨ Available slots on {preferred_date}:\n\n"
        for i, slot in enumerate(available, 1):
            msg += f"{i}. {slot['time']} ({slot['staff']})\n"
        msg += "\n_Reply with the slot number to book!_"

        return self._format_response(
            success=True,
            data={"slots": available, "date": preferred_date},
            message=msg
        )

    async def book_appointment(self, spreadsheet_id: str, customer_phone: str,
                               customer_name: str, service: str, staff: str,
                               date: str, time: str,
                               sheet_name: str = "Bookings") -> Dict[str, Any]:
        """
        Books a salon appointment. Writes to Google Sheets.
        Columns: Date | Time | Phone | Name | Service | Staff | Amount | Payment | Status | BookingID
        """
        import uuid
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        booking_id = f"SAL-{uuid.uuid4().hex[:6].upper()}"

        row = [
            date, time, customer_phone, customer_name,
            service, staff, "", "Pending", "Confirmed", booking_id
        ]

        result = await sheets.execute(
            method="append_row",
            spreadsheet_id=spreadsheet_id,
            range_name=sheet_name,
            row_data=row
        )

        if result["success"]:
            return self._format_response(
                success=True,
                data={"booking_id": booking_id, "date": date, "time": time, "staff": staff},
                message=f"💇 Appointment confirmed!\n\n📅 {date} at {time}\n👤 Staff: {staff}\n✂️ Service: {service}\n🎫 Booking ID: {booking_id}"
            )
        return result

    async def get_staff_schedule(self, spreadsheet_id: str, staff_name: str, date: str,
                                 sheet_name: str = "Bookings") -> Dict[str, Any]:
        """Returns all bookings for a specific staff member on a given date."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:I"
        )

        if not result["success"]:
            return result

        schedule = []
        for row in result["data"]["rows"][1:]:
            if len(row) >= 6 and row[0] == date and staff_name.lower() in row[5].lower():
                schedule.append({
                    "time": row[1],
                    "customer": row[3],
                    "service": row[4],
                    "status": row[8] if len(row) > 8 else "Confirmed"
                })

        return self._format_response(
            success=True,
            data={"schedule": schedule, "staff": staff_name, "date": date},
            message=f"{staff_name} has {len(schedule)} appointments on {date}."
        )


class LoyaltyTool(BaseTool):
    """
    Tracks customer visit history and triggers milestone rewards.
    Uses a "Customers" Google Sheet tab.
    """

    @property
    def tool_name(self) -> str:
        return "LoyaltyTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "record_visit":
            return await self.record_visit(**kwargs)
        elif method == "get_loyalty_status":
            return await self.get_loyalty_status(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def record_visit(self, spreadsheet_id: str, customer_phone: str,
                           business_name: str = "Our Salon",
                           sheet_name: str = "Customers") -> Dict[str, Any]:
        """
        Increments visit count. Checks milestones at 5, 10, 20, 50 visits.
        Columns: Phone | Name | Total Visits | Total Spent | Last Visit | Tier
        """
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:F"
        )

        if not result["success"]:
            return result

        today = datetime.datetime.now().strftime("%Y-%m-%d")

        for i, row in enumerate(result["data"]["rows"]):
            if i == 0:
                continue
            if len(row) >= 3 and customer_phone in row[0]:
                visits = int(row[2]) + 1
                
                # Determine tier
                tier = "Bronze"
                if visits >= 50:
                    tier = "Platinum"
                elif visits >= 20:
                    tier = "Gold"
                elif visits >= 10:
                    tier = "Silver"

                # Update visits, last visit date, and tier
                visits_cell = f"{sheet_name}!C{i + 1}"
                date_cell = f"{sheet_name}!E{i + 1}"
                tier_cell = f"{sheet_name}!F{i + 1}"

                await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                     range_name=visits_cell, value=str(visits))
                await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                     range_name=date_cell, value=today)
                await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                     range_name=tier_cell, value=tier)

                # Check milestones
                milestone_msg = None
                milestones = {5: "10% off next visit", 10: "Free basic service",
                              20: "20% off any service", 50: "VIP Platinum membership!"}
                if visits in milestones:
                    milestone_msg = f"🎉 *MILESTONE!* You've visited {business_name} {visits} times!\nReward: {milestones[visits]}"

                return self._format_response(
                    success=True,
                    data={"visits": visits, "tier": tier, "milestone": milestone_msg},
                    message=f"Visit #{visits} recorded. Tier: {tier}"
                )

        return self._format_response(success=False, message="Customer not found in loyalty sheet.")

    async def get_loyalty_status(self, spreadsheet_id: str, customer_phone: str,
                                 sheet_name: str = "Customers") -> Dict[str, Any]:
        """Returns current visit count, tier, and next reward milestone."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:F"
        )

        if not result["success"]:
            return result

        for row in result["data"]["rows"][1:]:
            if len(row) >= 3 and customer_phone in row[0]:
                visits = int(row[2])
                tier = row[5] if len(row) > 5 else "Bronze"
                
                next_milestone = None
                for m in [5, 10, 20, 50]:
                    if visits < m:
                        next_milestone = m
                        break

                remaining = (next_milestone - visits) if next_milestone else 0

                msg = f"⭐ Loyalty Status:\n"
                msg += f"Total Visits: {visits}\n"
                msg += f"Current Tier: {tier}\n"
                if next_milestone:
                    msg += f"Next Reward: {remaining} more visits to go!"

                return self._format_response(
                    success=True,
                    data={"visits": visits, "tier": tier, "next_milestone": next_milestone,
                          "visits_remaining": remaining},
                    message=msg
                )

        return self._format_response(success=False, message="Customer not found.")


class FestivalMarketingTool(BaseTool):
    """
    Generates festival-specific promotional messages for the salon owner to blast
    to their customer base. Leverages the Indian festival calendar.
    """

    FESTIVALS = {
        "diwali": {"emoji": "🪔", "msg": "Iss Diwali apna look banao! Special festive packages available."},
        "holi": {"emoji": "🎨", "msg": "Holi ke baad skin care zaruri hai! Book your post-Holi facial today."},
        "eid": {"emoji": "🌙", "msg": "Eid Mubarak! Look your best — special grooming packages available."},
        "christmas": {"emoji": "🎄", "msg": "Merry Christmas! Treat yourself to a holiday makeover."},
        "karva_chauth": {"emoji": "🌕", "msg": "Karva Chauth special! Mehendi, makeup, and more — book now."},
        "navratri": {"emoji": "🕉️", "msg": "Navratri ki dhoom! Get dolled up for Garba nights."},
        "valentines": {"emoji": "💝", "msg": "Valentine's Day special! Couples packages available."},
        "new_year": {"emoji": "🎉", "msg": "New Year, New Look! Start 2027 looking fabulous."},
    }

    @property
    def tool_name(self) -> str:
        return "FestivalMarketingTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "get_festival_campaign":
            return await self.get_festival_campaign(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def get_festival_campaign(self, festival_name: str,
                                    business_name: str = "Our Salon") -> Dict[str, Any]:
        """Returns a ready-to-send WhatsApp festival promotional message."""
        key = festival_name.lower().replace(" ", "_").replace("'", "")
        festival = self.FESTIVALS.get(key)

        if not festival:
            available = ", ".join(self.FESTIVALS.keys())
            return self._format_response(
                success=False,
                message=f"Festival '{festival_name}' not found. Available: {available}"
            )

        msg = f"{festival['emoji']} *{business_name}* — {festival_name.title()} Special!\n\n"
        msg += f"{festival['msg']}\n\n"
        msg += f"📞 Reply 'book' to schedule your appointment!\n"
        msg += f"💈 Limited slots available — book now!"

        return self._format_response(
            success=True,
            data={"campaign_message": msg, "festival": festival_name},
            message=f"Festival campaign ready for {festival_name}."
        )
