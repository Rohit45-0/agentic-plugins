"""
Tiffin Service Vertical Tools
==============================
Domain-specific tools for Tiffin bots: Subscription management, weekly menu planning,
nutrition info, and daily delivery sheet generation.
"""
import datetime
from typing import Dict, Any, List

from app.tools.base_tool import BaseTool
from app.core.config import settings


class SubscriptionTool(BaseTool):
    """
    Manages tiffin subscriptions: create, pause, resume, and list active subscribers.
    All data stored in the owner's Google Sheets "Subscribers" tab.
    """

    @property
    def tool_name(self) -> str:
        return "SubscriptionTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "create_subscription":
            return await self.create_subscription(**kwargs)
        elif method == "pause_subscription":
            return await self.pause_subscription(**kwargs)
        elif method == "resume_subscription":
            return await self.resume_subscription(**kwargs)
        elif method == "get_active_subscribers":
            return await self.get_active_subscribers(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def create_subscription(self, spreadsheet_id: str, customer_phone: str,
                                  customer_name: str, plan_type: str,
                                  delivery_address: str,
                                  sheet_name: str = "Subscribers") -> Dict[str, Any]:
        """
        Creates a new tiffin subscription.
        plan_type: daily_lunch | daily_dinner | both | weekly
        Columns: Phone | Name | Plan | Address | Start Date | Status | Pause From | Pause To
        """
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        now = datetime.datetime.now().strftime("%Y-%m-%d")

        row = [
            customer_phone, customer_name, plan_type,
            delivery_address, now, "Active", "", ""
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
                data={"plan": plan_type, "start_date": now},
                message=f"✅ Subscription created for {customer_name}! Plan: {plan_type}, starting {now}."
            )
        return result

    async def pause_subscription(self, spreadsheet_id: str, customer_phone: str,
                                 from_date: str, to_date: str,
                                 sheet_name: str = "Subscribers") -> Dict[str, Any]:
        """Pause a subscriber's deliveries for a date range (e.g., travel/holiday)."""
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
                # Update Status, Pause From, Pause To
                status_cell = f"{sheet_name}!F{i + 1}"
                from_cell = f"{sheet_name}!G{i + 1}"
                to_cell = f"{sheet_name}!H{i + 1}"

                await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                     range_name=status_cell, value="Paused")
                await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                     range_name=from_cell, value=from_date)
                await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                     range_name=to_cell, value=to_date)

                return self._format_response(
                    success=True,
                    message=f"⏸️ Subscription paused from {from_date} to {to_date}."
                )

        return self._format_response(success=False, message="Subscriber not found.")

    async def resume_subscription(self, spreadsheet_id: str, customer_phone: str,
                                  sheet_name: str = "Subscribers") -> Dict[str, Any]:
        """Resume a paused subscription."""
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
                status_cell = f"{sheet_name}!F{i + 1}"
                from_cell = f"{sheet_name}!G{i + 1}"
                to_cell = f"{sheet_name}!H{i + 1}"

                await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                     range_name=status_cell, value="Active")
                await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                     range_name=from_cell, value="")
                await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                                     range_name=to_cell, value="")

                return self._format_response(success=True, message="▶️ Subscription resumed!")

        return self._format_response(success=False, message="Subscriber not found.")

    async def get_active_subscribers(self, spreadsheet_id: str,
                                     sheet_name: str = "Subscribers") -> Dict[str, Any]:
        """Returns all subscribers whose status is 'Active' for today's delivery."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:H"
        )

        if not result["success"]:
            return result

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        active = []
        
        for row in result["data"]["rows"][1:]:
            if len(row) < 6:
                continue
            status = row[5]
            
            # Check if paused and within pause window
            if status == "Paused" and len(row) >= 8:
                pause_from = row[6]
                pause_to = row[7]
                if pause_from <= today <= pause_to:
                    continue

            if status in ["Active", "Paused"]:  # Paused but outside pause window = still active
                active.append({
                    "phone": row[0],
                    "name": row[1],
                    "plan": row[2],
                    "address": row[3]
                })

        return self._format_response(
            success=True,
            data={"subscribers": active, "count": len(active)},
            message=f"Found {len(active)} active subscribers for today."
        )


class MenuPlannerTool(BaseTool):
    """
    Reads the weekly menu from Google Sheets and returns today's menu.
    Expected sheet: "WeeklyMenu" with columns Day | Lunch | Dinner
    """

    @property
    def tool_name(self) -> str:
        return "MenuPlannerTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "get_todays_menu":
            return await self.get_todays_menu(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def get_todays_menu(self, spreadsheet_id: str,
                              sheet_name: str = "WeeklyMenu") -> Dict[str, Any]:
        """Reads the weekly menu and returns today's specific meals."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:C"
        )

        if not result["success"]:
            return result

        today_name = datetime.datetime.now().strftime("%A")

        for row in result["data"]["rows"][1:]:
            if len(row) >= 3 and row[0].lower() == today_name.lower():
                msg = f"🍱 *Today's Menu ({today_name})*\n\n"
                msg += f"🥗 *Lunch:* {row[1]}\n"
                msg += f"🍛 *Dinner:* {row[2]}\n"
                msg += "\n_Enjoy your meal!_"

                return self._format_response(
                    success=True,
                    data={"day": today_name, "lunch": row[1], "dinner": row[2], "formatted_message": msg},
                    message=f"Today's menu loaded for {today_name}."
                )

        return self._format_response(success=False, message=f"No menu found for {today_name}.")


class DeliverySheetTool(BaseTool):
    """
    Generates a text-based delivery manifest for the delivery boy.
    Reads active subscribers and formats a numbered checklist.
    """

    @property
    def tool_name(self) -> str:
        return "DeliverySheetTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "generate_daily_delivery_sheet":
            return await self.generate_daily_delivery_sheet(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def generate_daily_delivery_sheet(self, spreadsheet_id: str) -> Dict[str, Any]:
        """Generates a numbered WhatsApp delivery list for today."""
        sub_tool = SubscriptionTool()
        result = await sub_tool.execute(
            method="get_active_subscribers",
            spreadsheet_id=spreadsheet_id
        )

        if not result["success"]:
            return result

        subscribers = result["data"]["subscribers"]
        today = datetime.datetime.now().strftime("%d %b %Y")

        msg = f"📦 *Delivery Sheet — {today}*\n"
        msg += f"Total Deliveries: {len(subscribers)}\n\n"

        for i, sub in enumerate(subscribers, 1):
            msg += f"{i}. *{sub['name']}*\n"
            msg += f"   📍 {sub['address']}\n"
            msg += f"   📞 {sub['phone']}\n"
            msg += f"   🍱 {sub['plan']}\n\n"

        msg += "Drive safe! 🛵"

        return self._format_response(
            success=True,
            data={"delivery_message": msg, "total_deliveries": len(subscribers)},
            message=f"Delivery sheet generated for {len(subscribers)} deliveries."
        )
