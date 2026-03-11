"""
Kirana Store Vertical Tools
============================
Catalog management via barcode, Udhar (credit) ledger, and stock alerts.
"""
import datetime
from typing import Dict, Any

from app.tools.base_tool import BaseTool


class CatalogTool(BaseTool):
    """
    Product catalog management. Can auto-populate products via barcode scanning
    using the 100% free Open Food Facts API.
    """

    @property
    def tool_name(self) -> str:
        return "CatalogTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "add_product_by_barcode":
            return await self.add_product_by_barcode(**kwargs)
        elif method == "search_catalog":
            return await self.search_catalog(**kwargs)
        elif method == "add_product_manual":
            return await self.add_product_manual(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def add_product_by_barcode(self, spreadsheet_id: str, barcode: str,
                                     price: str = "", stock: str = "",
                                     sheet_name: str = "Inventory") -> Dict[str, Any]:
        """
        Scans a barcode against Open Food Facts (100% free, no API key) 
        and adds the product to the store's inventory sheet.
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json")

            if resp.status_code != 200:
                return self._format_response(success=False, message="Barcode lookup service unavailable.")

            data = resp.json()
            if data.get("status") != 1:
                return self._format_response(success=False, message=f"Barcode {barcode} not found in database.")

            product = data["product"]
            name = product.get("product_name", "Unknown Product")
            brand = product.get("brands", "Unknown")
            category = product.get("categories", "General")
            image = product.get("image_url", "")

            # Write to Google Sheets
            from app.tools.google.sheets_tool import GoogleSheetsTool
            sheets = GoogleSheetsTool()

            row = [barcode, name, brand, category, price, stock, image]
            await sheets.execute(
                method="append_row",
                spreadsheet_id=spreadsheet_id,
                range_name=sheet_name,
                row_data=row
            )

            return self._format_response(
                success=True,
                data={"barcode": barcode, "name": name, "brand": brand, "category": category},
                message=f"✅ Added: {name} ({brand}) to inventory."
            )

        except Exception as e:
            return self.handle_error(e)

    async def add_product_manual(self, spreadsheet_id: str, name: str, price: str,
                                 stock: str, sheet_name: str = "Inventory") -> Dict[str, Any]:
        """Manually add a product without barcode scanning."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        row = ["MANUAL", name, "", "General", price, stock, ""]
        result = await sheets.execute(
            method="append_row",
            spreadsheet_id=spreadsheet_id,
            range_name=sheet_name,
            row_data=row
        )

        if result["success"]:
            return self._format_response(
                success=True,
                data={"name": name, "price": price, "stock": stock},
                message=f"✅ {name} added to inventory at ₹{price}."
            )
        return result

    async def search_catalog(self, spreadsheet_id: str, query: str,
                             sheet_name: str = "Inventory") -> Dict[str, Any]:
        """Fuzzy search the inventory by product name."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:F"
        )

        if not result["success"]:
            return result

        matches = []
        for row in result["data"]["rows"][1:]:
            if len(row) >= 5 and query.lower() in row[1].lower():
                matches.append({
                    "name": row[1],
                    "brand": row[2] if len(row) > 2 else "",
                    "price": row[4] if len(row) > 4 else "",
                    "stock": row[5] if len(row) > 5 else ""
                })

        return self._format_response(
            success=True,
            data={"results": matches},
            message=f"Found {len(matches)} products matching '{query}'."
        )


class UdharTool(BaseTool):
    """
    Credit Ledger (Udhar/Khata) management. 
    Tracks customer credit purchases and payments in a Google Sheets ledger.
    """

    @property
    def tool_name(self) -> str:
        return "UdharTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "add_credit_entry":
            return await self.add_credit_entry(**kwargs)
        elif method == "record_payment":
            return await self.record_payment(**kwargs)
        elif method == "get_balance":
            return await self.get_balance(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def add_credit_entry(self, spreadsheet_id: str, customer_phone: str,
                               customer_name: str, amount: float,
                               items_description: str,
                               sheet_name: str = "Udhar") -> Dict[str, Any]:
        """
        Adds a credit (udhar) entry to the ledger.
        Columns: Date | Phone | Name | Items | Amount | Type | Running Balance | Notes
        """
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        # Get current balance
        balance_result = await self.get_balance(spreadsheet_id, customer_phone, sheet_name)
        current_balance = balance_result["data"].get("balance", 0) if balance_result["success"] else 0
        new_balance = current_balance + amount

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        row = [now, customer_phone, customer_name, items_description,
               str(amount), "Credit", str(new_balance), ""]

        result = await sheets.execute(
            method="append_row",
            spreadsheet_id=spreadsheet_id,
            range_name=sheet_name,
            row_data=row
        )

        if result["success"]:
            return self._format_response(
                success=True,
                data={"new_balance": new_balance, "amount_added": amount},
                message=f"📝 Udhar recorded: ₹{amount}\nNew balance: ₹{new_balance}"
            )
        return result

    async def record_payment(self, spreadsheet_id: str, customer_phone: str,
                             customer_name: str, amount: float,
                             sheet_name: str = "Udhar") -> Dict[str, Any]:
        """Records a payment against the udhar balance."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        balance_result = await self.get_balance(spreadsheet_id, customer_phone, sheet_name)
        current_balance = balance_result["data"].get("balance", 0) if balance_result["success"] else 0
        new_balance = current_balance - amount

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        row = [now, customer_phone, customer_name, "Payment Received",
               str(amount), "Debit", str(new_balance), ""]

        result = await sheets.execute(
            method="append_row",
            spreadsheet_id=spreadsheet_id,
            range_name=sheet_name,
            row_data=row
        )

        if result["success"]:
            return self._format_response(
                success=True,
                data={"new_balance": new_balance, "amount_paid": amount},
                message=f"💰 Payment of ₹{amount} recorded.\nRemaining balance: ₹{new_balance}"
            )
        return result

    async def get_balance(self, spreadsheet_id: str, customer_phone: str,
                          sheet_name: str = "Udhar") -> Dict[str, Any]:
        """Returns the current outstanding balance for a customer."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:G"
        )

        if not result["success"]:
            return result

        # Find the last entry for this customer (most recent running balance)
        last_balance = 0
        for row in reversed(result["data"]["rows"]):
            if len(row) >= 7 and customer_phone in row[1]:
                try:
                    last_balance = float(row[6])
                except ValueError:
                    last_balance = 0
                break

        return self._format_response(
            success=True,
            data={"balance": last_balance, "customer_phone": customer_phone},
            message=f"Current udhar balance: ₹{last_balance}"
        )


class StockAlertTool(BaseTool):
    """
    Monitors inventory levels and alerts the owner when items run low.
    """

    @property
    def tool_name(self) -> str:
        return "StockAlertTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "check_low_stock":
            return await self.check_low_stock(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def check_low_stock(self, spreadsheet_id: str, threshold: int = 5,
                              sheet_name: str = "Inventory") -> Dict[str, Any]:
        """
        Scans inventory and returns items with stock below threshold.
        Expected columns: Barcode | Name | Brand | Category | Price | Stock
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

        low_items = []
        for row in result["data"]["rows"][1:]:
            if len(row) >= 6:
                try:
                    stock = int(row[5])
                    if stock <= threshold:
                        low_items.append({"name": row[1], "stock": stock})
                except ValueError:
                    continue

        if not low_items:
            return self._format_response(success=True, data={"low_stock": []},
                                         message="✅ All items are well-stocked!")

        msg = "⚠️ *Low Stock Alert!*\n\n"
        for item in low_items:
            msg += f"• {item['name']} — only {item['stock']} left\n"
        msg += "\n_Please restock soon!_"

        return self._format_response(
            success=True,
            data={"low_stock": low_items},
            message=msg
        )
