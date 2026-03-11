"""
Restaurant Vertical Tools
=========================
Domain-specific tools for restaurant bots: Menu management, Order tracking,
Weather-based promotions, and Delivery dispatch.
"""
import asyncio
import datetime
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.base_tool import BaseTool
from app.core.config import settings


class MenuTool(BaseTool):
    """
    Manages the restaurant's live menu. Can read from Google Sheets, 
    toggle item availability, and format menu for WhatsApp display.
    """

    @property
    def tool_name(self) -> str:
        return "MenuTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "get_menu_for_display":
            return await self.get_menu_for_display(**kwargs)
        elif method == "check_item_availability":
            return await self.check_item_availability(**kwargs)
        elif method == "update_item_availability":
            return await self.update_item_availability(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def get_menu_for_display(self, spreadsheet_id: str, sheet_name: str = "Menu") -> Dict[str, Any]:
        """
        Reads the menu from Google Sheets and formats it as a beautiful WhatsApp message.
        Expected Sheet columns: Item Name | Price | Category | Available (Yes/No)
        """
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:D"
        )

        if not result["success"]:
            return result

        rows = result["data"]["rows"]
        if not rows or len(rows) < 2:
            return self._format_response(success=False, message="Menu sheet is empty.")

        headers = rows[0]
        items = rows[1:]

        # Group by category
        categories = {}
        for row in items:
            if len(row) < 4:
                continue
            name, price, category, available = row[0], row[1], row[2], row[3]
            if available.lower() not in ["yes", "y", "true", "1"]:
                continue
            if category not in categories:
                categories[category] = []
            categories[category].append({"name": name, "price": price})

        # Format for WhatsApp
        msg = "📋 *Today's Menu*\n\n"
        for cat, items_list in categories.items():
            msg += f"*── {cat.upper()} ──*\n"
            for item in items_list:
                msg += f"  • {item['name']} — ₹{item['price']}\n"
            msg += "\n"
        msg += "_Reply with item names to order!_"

        return self._format_response(
            success=True,
            data={"menu_message": msg, "categories": categories},
            message="Menu loaded successfully."
        )

    async def check_item_availability(self, spreadsheet_id: str, item_name: str, 
                                      sheet_name: str = "Menu") -> Dict[str, Any]:
        """Check if a specific item is currently available."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:D"
        )

        if not result["success"]:
            return result

        for row in result["data"]["rows"][1:]:
            if len(row) >= 4 and item_name.lower() in row[0].lower():
                is_available = row[3].lower() in ["yes", "y", "true", "1"]
                return self._format_response(
                    success=True,
                    data={"item": row[0], "price": row[1], "available": is_available},
                    message=f"{row[0]} is {'available' if is_available else 'currently unavailable'}."
                )

        return self._format_response(success=False, message=f"Item '{item_name}' not found on menu.")

    async def update_item_availability(self, spreadsheet_id: str, item_name: str, 
                                        available: bool, sheet_name: str = "Menu") -> Dict[str, Any]:
        """Owner command: Toggle an item on/off the menu."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:D"
        )

        if not result["success"]:
            return result

        for i, row in enumerate(result["data"]["rows"]):
            if i == 0:
                continue
            if len(row) >= 1 and item_name.lower() in row[0].lower():
                cell = f"{sheet_name}!D{i + 1}"
                update_result = await sheets.execute(
                    method="update_cell",
                    spreadsheet_id=spreadsheet_id,
                    range_name=cell,
                    value="Yes" if available else "No"
                )
                status_text = "available" if available else "unavailable"
                return self._format_response(
                    success=True,
                    data={"item": row[0], "new_status": status_text},
                    message=f"✅ {row[0]} is now marked as {status_text}."
                )

        return self._format_response(success=False, message=f"Item '{item_name}' not found.")


class OrderTool(BaseTool):
    """
    Manages restaurant orders: creation, status tracking, order history,
    and total calculation. Persists to Google Sheets "Orders" tab.
    """

    @property
    def tool_name(self) -> str:
        return "OrderTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "create_order":
            return await self.create_order(**kwargs)
        elif method == "update_order_status":
            return await self.update_order_status(**kwargs)
        elif method == "get_order_history":
            return await self.get_order_history(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def create_order(self, spreadsheet_id: str, customer_phone: str, customer_name: str,
                           items: str, total_amount: str, delivery_address: str = "Dine-in",
                           sheet_name: str = "Orders") -> Dict[str, Any]:
        """
        Creates a new order row in the Orders sheet.
        Columns: Date | Time | Phone | Name | Items | Total | Address | Status | Order ID
        """
        import uuid
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        now = datetime.datetime.now()
        order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"

        row = [
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M"),
            customer_phone,
            customer_name,
            items,
            total_amount,
            delivery_address,
            "Received",
            order_id
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
                data={"order_id": order_id, "total": total_amount},
                message=f"✅ Order {order_id} placed successfully! Total: ₹{total_amount}"
            )
        return result

    async def update_order_status(self, spreadsheet_id: str, order_id: str, new_status: str,
                                   sheet_name: str = "Orders") -> Dict[str, Any]:
        """Update order status: received → confirmed → preparing → out_for_delivery → delivered"""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:I"
        )

        if not result["success"]:
            return result

        for i, row in enumerate(result["data"]["rows"]):
            if len(row) >= 9 and row[8] == order_id:
                cell = f"{sheet_name}!H{i + 1}"
                await sheets.execute(
                    method="update_cell",
                    spreadsheet_id=spreadsheet_id,
                    range_name=cell,
                    value=new_status
                )
                return self._format_response(
                    success=True,
                    data={"order_id": order_id, "status": new_status},
                    message=f"Order {order_id} status updated to: {new_status}"
                )

        return self._format_response(success=False, message=f"Order '{order_id}' not found.")

    async def get_order_history(self, spreadsheet_id: str, customer_phone: str, limit: int = 5,
                                sheet_name: str = "Orders") -> Dict[str, Any]:
        """Return a customer's past orders for easy reordering."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:I"
        )

        if not result["success"]:
            return result

        history = []
        for row in reversed(result["data"]["rows"]):
            if len(row) >= 5 and customer_phone in row[2]:
                history.append({
                    "date": row[0],
                    "items": row[4],
                    "total": row[5],
                    "status": row[7] if len(row) > 7 else "Unknown"
                })
                if len(history) >= limit:
                    break

        return self._format_response(
            success=True,
            data={"orders": history},
            message=f"Found {len(history)} past orders."
        )


class WeatherOrderTool(BaseTool):
    """
    Checks weather and suggests rain-day promotions.
    Uses OpenWeatherMap free tier (no API key required for basic calls, 
    or use the free tier key for 60 calls/minute).
    """

    @property
    def tool_name(self) -> str:
        return "WeatherOrderTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "check_weather_and_suggest":
            return await self.check_weather_and_suggest(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def check_weather_and_suggest(self, city: str = "Pune") -> Dict[str, Any]:
        """
        Checks real-time weather. If rainy/stormy, returns a promo template.
        Uses wttr.in (100% free, no API key needed).
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://wttr.in/{city}?format=j1")

            if resp.status_code != 200:
                return self._format_response(success=False, message="Weather service unavailable.")

            data = resp.json()
            current = data["current_condition"][0]

            temp_c = current["temp_C"]
            desc = current["weatherDesc"][0]["value"]
            humidity = current["humidity"]

            is_rainy = any(keyword in desc.lower() for keyword in ["rain", "drizzle", "thunder", "storm", "shower"])
            is_cold = int(temp_c) < 20

            promo = None
            if is_rainy:
                promo = f"🌧️ Baarish ka mausam, ghar pe hi rahe! Order karo garam khana, deliver karte hai! 🍲"
            elif is_cold:
                promo = f"❄️ Thandi lag rahi hai? Garam chai aur snacks mangao, seedha ghar pe! ☕"

            return self._format_response(
                success=True,
                data={
                    "temperature_c": temp_c,
                    "description": desc,
                    "humidity": humidity,
                    "is_rainy": is_rainy,
                    "is_cold": is_cold,
                    "promo_message": promo
                },
                message=f"Weather in {city}: {temp_c}°C, {desc}"
            )

        except Exception as e:
            return self.handle_error(e)
