"""
Clinic / Doctor Queue Vertical Tools
=====================================
Token-based queue management, patient history tracking, and prescription saving.
"""
import datetime
from typing import Dict, Any

from app.tools.base_tool import BaseTool


class QueueTool(BaseTool):
    """
    Real-time token queue system for clinics. 
    Assigns token numbers, estimates wait time, advances the queue, and notifies patients.
    Uses a Google Sheets "Queue" tab as the live data source.
    """

    @property
    def tool_name(self) -> str:
        return "QueueTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "generate_token":
            return await self.generate_token(**kwargs)
        elif method == "advance_queue":
            return await self.advance_queue(**kwargs)
        elif method == "get_queue_status":
            return await self.get_queue_status(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def generate_token(self, spreadsheet_id: str, patient_name: str,
                             patient_phone: str, reason: str = "",
                             avg_consult_minutes: int = 10,
                             sheet_name: str = "Queue") -> Dict[str, Any]:
        """
        Assigns the next token number. Estimates wait based on queue length.
        Columns: Token | Name | Phone | Reason | Status | Time
        """
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:F"
        )

        rows = result["data"]["rows"] if result["success"] else []
        waiting_count = sum(1 for r in rows[1:] if len(r) >= 5 and r[4] == "Waiting")
        next_token = len(rows)  # Row count = next token number

        est_wait = waiting_count * avg_consult_minutes
        now = datetime.datetime.now().strftime("%H:%M")

        row = [str(next_token), patient_name, patient_phone, reason, "Waiting", now]

        await sheets.execute(
            method="append_row",
            spreadsheet_id=spreadsheet_id,
            range_name=sheet_name,
            row_data=row
        )

        msg = f"🏥 *Token #{next_token}*\n\n"
        msg += f"👤 {patient_name}\n"
        msg += f"📋 {reason}\n" if reason else ""
        msg += f"⏳ Estimated Wait: ~{est_wait} minutes\n"
        msg += f"👥 People ahead: {waiting_count}\n\n"
        msg += "_We'll notify you when it's your turn!_"

        return self._format_response(
            success=True,
            data={"token": next_token, "wait_minutes": est_wait, "ahead": waiting_count},
            message=msg
        )

    async def advance_queue(self, spreadsheet_id: str,
                            sheet_name: str = "Queue") -> Dict[str, Any]:
        """
        Owner/receptionist calls this when a patient is done.
        Marks current patient as 'Done' and notifies the next 3 patients.
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

        rows = result["data"]["rows"]
        waiting = [(i, r) for i, r in enumerate(rows) if i > 0 and len(r) >= 5 and r[4] == "Waiting"]

        if not waiting:
            return self._format_response(success=True, message="✅ Queue is empty! No more patients waiting.")

        # Mark the first waiting patient as Done
        first_idx, first_row = waiting[0]
        status_cell = f"{sheet_name}!E{first_idx + 1}"
        await sheets.execute(method="update_cell", spreadsheet_id=spreadsheet_id,
                             range_name=status_cell, value="Done")

        # Build notification for next 3
        notifications = []
        for pos, (idx, row) in enumerate(waiting[1:4]):
            if pos == 0:
                notifications.append(f"📢 {row[1]} (Token #{row[0]}): *You're NEXT!* Please come in.")
            else:
                notifications.append(f"⏳ {row[1]} (Token #{row[0]}): {pos} patient(s) ahead of you.")

        return self._format_response(
            success=True,
            data={
                "completed_token": first_row[0],
                "completed_patient": first_row[1],
                "notifications": notifications,
                "remaining_count": len(waiting) - 1
            },
            message=f"Token #{first_row[0]} ({first_row[1]}) marked done. {len(waiting) - 1} patients remaining."
        )

    async def get_queue_status(self, spreadsheet_id: str,
                               sheet_name: str = "Queue") -> Dict[str, Any]:
        """Returns current queue length and the active token number."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:F"
        )

        if not result["success"]:
            return result

        rows = result["data"]["rows"]
        waiting = [r for r in rows[1:] if len(r) >= 5 and r[4] == "Waiting"]
        done = [r for r in rows[1:] if len(r) >= 5 and r[4] == "Done"]

        current_token = waiting[0][0] if waiting else "None"

        msg = f"🏥 *Queue Status*\n\n"
        msg += f"Current Token: #{current_token}\n"
        msg += f"Waiting: {len(waiting)}\n"
        msg += f"Completed: {len(done)}"

        return self._format_response(
            success=True,
            data={"current_token": current_token, "waiting": len(waiting), "completed": len(done)},
            message=msg
        )
