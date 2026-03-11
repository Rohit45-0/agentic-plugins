"""
Gym / Yoga Studio Vertical Tools
=================================
Membership management, class booking with waitlist, progress tracking, and streaks.
"""
import datetime
from typing import Dict, Any

from app.tools.base_tool import BaseTool


class MembershipTool(BaseTool):
    """
    Tracks gym memberships: creation, status checks, pause/resume, and expiry alerts.
    """

    @property
    def tool_name(self) -> str:
        return "MembershipTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "create_membership":
            return await self.create_membership(**kwargs)
        elif method == "check_membership_status":
            return await self.check_membership_status(**kwargs)
        elif method == "pause_membership":
            return await self.pause_membership(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def create_membership(self, spreadsheet_id: str, customer_phone: str,
                                customer_name: str, plan_type: str,
                                amount: str,
                                sheet_name: str = "Members") -> Dict[str, Any]:
        """
        Creates a new gym membership.
        plan_type: monthly | quarterly | half_yearly | annual
        Columns: Phone | Name | Plan | Start | End | Amount | Status | Streak
        """
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        start = datetime.datetime.now()
        plan_days = {"monthly": 30, "quarterly": 90, "half_yearly": 180, "annual": 365}
        days = plan_days.get(plan_type, 30)
        end = start + datetime.timedelta(days=days)

        row = [
            customer_phone, customer_name, plan_type,
            start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
            amount, "Active", "0"
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
                data={"plan": plan_type, "start": start.strftime("%Y-%m-%d"),
                      "end": end.strftime("%Y-%m-%d")},
                message=f"🏋️ Membership created!\n\nPlan: {plan_type}\nValid until: {end.strftime('%d %b %Y')}\nAmount: ₹{amount}"
            )
        return result

    async def check_membership_status(self, spreadsheet_id: str, customer_phone: str,
                                      sheet_name: str = "Members") -> Dict[str, Any]:
        """Returns membership status, days remaining, and current streak."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:H"
        )

        if not result["success"]:
            return result

        for row in result["data"]["rows"][1:]:
            if len(row) >= 7 and customer_phone in row[0]:
                end_date = datetime.datetime.strptime(row[4], "%Y-%m-%d")
                today = datetime.datetime.now()
                days_left = (end_date - today).days
                status = "Active" if days_left > 0 else "Expired"
                streak = row[7] if len(row) > 7 else "0"

                msg = f"🏋️ *Membership Status*\n\n"
                msg += f"Plan: {row[2]}\n"
                msg += f"Status: {'✅ Active' if status == 'Active' else '❌ Expired'}\n"
                msg += f"Days Remaining: {max(days_left, 0)}\n"
                msg += f"Valid Until: {row[4]}\n"
                msg += f"Current Streak: {streak} days 🔥\n"

                if days_left <= 7 and days_left > 0:
                    msg += "\n⚠️ _Your membership expires soon! Renew to keep your streak._"

                return self._format_response(
                    success=True,
                    data={"status": status, "days_left": max(days_left, 0),
                          "plan": row[2], "streak": streak},
                    message=msg
                )

        return self._format_response(success=False, message="Membership not found.")

    async def pause_membership(self, spreadsheet_id: str, customer_phone: str,
                               pause_days: int,
                               sheet_name: str = "Members") -> Dict[str, Any]:
        """Pauses membership and extends end date by the pause duration."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:H"
        )

        if not result["success"]:
            return result

        for i, row in enumerate(result["data"]["rows"]):
            if i == 0:
                continue
            if len(row) >= 5 and customer_phone in row[0]:
                old_end = datetime.datetime.strptime(row[4], "%Y-%m-%d")
                new_end = old_end + datetime.timedelta(days=pause_days)

                end_cell = f"{sheet_name}!E{i + 1}"
                status_cell = f"{sheet_name}!G{i + 1}"

                await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                     range_name=end_cell, value=new_end.strftime("%Y-%m-%d"))
                await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                     range_name=status_cell, value="Paused")

                return self._format_response(
                    success=True,
                    data={"new_end_date": new_end.strftime("%Y-%m-%d"), "pause_days": pause_days},
                    message=f"⏸️ Membership paused for {pause_days} days. New expiry: {new_end.strftime('%d %b %Y')}"
                )

        return self._format_response(success=False, message="Member not found.")


class ClassBookingTool(BaseTool):
    """
    Manages class/session bookings with capacity limits and waitlist support.
    """

    @property
    def tool_name(self) -> str:
        return "ClassBookingTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "get_class_schedule":
            return await self.get_class_schedule(**kwargs)
        elif method == "book_class":
            return await self.book_class(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def get_class_schedule(self, spreadsheet_id: str,
                                 sheet_name: str = "ClassSchedule") -> Dict[str, Any]:
        """
        Returns upcoming classes with capacity info.
        Columns: Date | Time | Class Name | Instructor | Max Capacity | Booked | Waitlisted
        """
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:G"
        )

        if not result["success"]:
            return result

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        classes = []

        for row in result["data"]["rows"][1:]:
            if len(row) >= 6 and row[0] >= today:
                booked = int(row[5]) if row[5] else 0
                max_cap = int(row[4]) if row[4] else 20
                spots_left = max_cap - booked

                classes.append({
                    "date": row[0], "time": row[1],
                    "name": row[2], "instructor": row[3],
                    "spots_left": spots_left
                })

        msg = "🧘 *Upcoming Classes*\n\n"
        for c in classes[:10]:
            status = f"{c['spots_left']} spots left" if c['spots_left'] > 0 else "FULL (waitlist available)"
            msg += f"• *{c['name']}* — {c['date']} {c['time']}\n  Instructor: {c['instructor']} | {status}\n\n"

        return self._format_response(
            success=True,
            data={"classes": classes},
            message=msg
        )

    async def book_class(self, spreadsheet_id: str, customer_phone: str,
                         class_date: str, class_time: str,
                         sheet_name: str = "ClassSchedule",
                         bookings_sheet: str = "ClassBookings") -> Dict[str, Any]:
        """Books a customer into a class or adds to waitlist if full."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        # Check capacity
        schedule_result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:G"
        )

        if not schedule_result["success"]:
            return schedule_result

        target_row_idx = None
        class_name = ""
        for i, row in enumerate(schedule_result["data"]["rows"]):
            if i == 0:
                continue
            if len(row) >= 6 and row[0] == class_date and row[1] == class_time:
                booked = int(row[5]) if row[5] else 0
                max_cap = int(row[4]) if row[4] else 20
                class_name = row[2]
                target_row_idx = i

                if booked < max_cap:
                    # Book directly
                    new_count = booked + 1
                    booked_cell = f"{sheet_name}!F{i + 1}"
                    await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                         range_name=booked_cell, value=str(new_count))

                    # Record booking
                    booking_row = [class_date, class_time, class_name, customer_phone, "Booked"]
                    await sheets.execute(method="append_row", spreadsheet_id=spreadsheet_id,
                                         range_name=bookings_sheet, row_data=booking_row)

                    return self._format_response(
                        success=True,
                        data={"class": class_name, "status": "Booked"},
                        message=f"✅ You're booked for *{class_name}* on {class_date} at {class_time}!"
                    )
                else:
                    # Waitlist
                    waitlisted = int(row[6]) + 1 if len(row) > 6 and row[6] else 1
                    wait_cell = f"{sheet_name}!G{i + 1}"
                    await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                         range_name=wait_cell, value=str(waitlisted))

                    booking_row = [class_date, class_time, class_name, customer_phone, "Waitlisted"]
                    await sheets.execute(method="append_row", spreadsheet_id=spreadsheet_id,
                                         range_name=bookings_sheet, row_data=booking_row)

                    return self._format_response(
                        success=True,
                        data={"class": class_name, "status": "Waitlisted", "position": waitlisted},
                        message=f"⏳ Class is full. You are #{waitlisted} on the waitlist for *{class_name}*."
                    )

        return self._format_response(success=False, message=f"No class found on {class_date} at {class_time}.")


class StreakTool(BaseTool):
    """
    Tracks consecutive gym visit streaks and sends milestone celebrations.
    """

    @property
    def tool_name(self) -> str:
        return "StreakTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "update_streak":
            return await self.update_streak(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def update_streak(self, spreadsheet_id: str, customer_phone: str,
                            business_name: str = "The Gym",
                            sheet_name: str = "Members") -> Dict[str, Any]:
        """
        Increments the streak counter. Sends milestone messages at 7, 14, 30, 50, 100 days.
        """
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:H"
        )

        if not result["success"]:
            return result

        for i, row in enumerate(result["data"]["rows"]):
            if i == 0:
                continue
            if len(row) >= 1 and customer_phone in row[0]:
                current_streak = int(row[7]) if len(row) > 7 and row[7] else 0
                new_streak = current_streak + 1

                streak_cell = f"{sheet_name}!H{i + 1}"
                await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                     range_name=streak_cell, value=str(new_streak))

                # Check milestones
                milestone_msg = None
                milestones = {
                    7: "1 week strong! 💪",
                    14: "2 weeks! You're unstoppable! 🔥",
                    30: "30-day warrior! You're in the top 5% of members! 🏆",
                    50: "50 days! Absolute legend! 👑",
                    100: "100 DAYS! You are officially a fitness machine! 🦾"
                }

                if new_streak in milestones:
                    milestone_msg = f"🎉 *{business_name} — Streak Milestone!*\n\n"
                    milestone_msg += f"🔥 {new_streak}-Day Streak!\n"
                    milestone_msg += f"{milestones[new_streak]}\n\n"
                    milestone_msg += "_Keep it going! Don't break the chain!_"

                return self._format_response(
                    success=True,
                    data={"streak": new_streak, "milestone": milestone_msg is not None},
                    message=milestone_msg or f"🔥 Streak: {new_streak} days! Keep going!"
                )

        return self._format_response(success=False, message="Member not found.")
