"""
Coaching / Tuition Center Vertical Tools
=========================================
Attendance tracking, batch management, fee invoicing, and homework submission.
"""
import datetime
from typing import Dict, Any, List

from app.tools.base_tool import BaseTool


class AttendanceTool(BaseTool):
    """
    Tracks daily attendance per batch in Google Sheets.
    """

    @property
    def tool_name(self) -> str:
        return "AttendanceTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "mark_attendance":
            return await self.mark_attendance(**kwargs)
        elif method == "get_attendance_report":
            return await self.get_attendance_report(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def mark_attendance(self, spreadsheet_id: str, batch_name: str,
                              student_phone: str, student_name: str,
                              status: str = "Present",
                              sheet_name: str = "Attendance") -> Dict[str, Any]:
        """
        Marks a student's attendance for today.
        Columns: Date | Batch | Phone | Name | Status
        """
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        row = [today, batch_name, student_phone, student_name, status]

        result = await sheets.execute(
            method="append_row",
            spreadsheet_id=spreadsheet_id,
            range_name=sheet_name,
            row_data=row
        )

        if result["success"]:
            emoji = "✅" if status == "Present" else "❌"
            return self._format_response(
                success=True,
                data={"date": today, "student": student_name, "status": status},
                message=f"{emoji} {student_name} marked as {status} for {batch_name} on {today}."
            )
        return result

    async def get_attendance_report(self, spreadsheet_id: str, student_phone: str,
                                    month: str = None,
                                    sheet_name: str = "Attendance") -> Dict[str, Any]:
        """Generates attendance percentage for a student over a specified month."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        if not month:
            month = datetime.datetime.now().strftime("%Y-%m")

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:E"
        )

        if not result["success"]:
            return result

        total = 0
        present = 0
        for row in result["data"]["rows"][1:]:
            if len(row) >= 5 and student_phone in row[2] and row[0].startswith(month):
                total += 1
                if row[4] == "Present":
                    present += 1

        percentage = round((present / total) * 100, 1) if total > 0 else 0

        msg = f"📊 *Attendance Report — {month}*\n\n"
        msg += f"Classes Attended: {present}/{total}\n"
        msg += f"Attendance: {percentage}%\n"
        if percentage < 75:
            msg += "\n⚠️ _Attendance is below 75%. Please attend regularly._"

        return self._format_response(
            success=True,
            data={"present": present, "total": total, "percentage": percentage},
            message=msg
        )


class FeeManagementTool(BaseTool):
    """
    Generates monthly fee invoices with payment links and tracks payment status.
    """

    @property
    def tool_name(self) -> str:
        return "FeeManagementTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "create_fee_invoice":
            return await self.create_fee_invoice(**kwargs)
        elif method == "get_pending_fees":
            return await self.get_pending_fees(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def create_fee_invoice(self, spreadsheet_id: str, student_phone: str,
                                 student_name: str, month: str, amount: str,
                                 due_date: str, business_name: str = "Coaching Center",
                                 sheet_name: str = "Fees") -> Dict[str, Any]:
        """
        Creates a fee invoice row and returns a formatted message.
        Columns: Month | Phone | Name | Amount | Due Date | Status | Payment ID
        """
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        row = [month, student_phone, student_name, amount, due_date, "Unpaid", ""]

        result = await sheets.execute(
            method="append_row",
            spreadsheet_id=spreadsheet_id,
            range_name=sheet_name,
            row_data=row
        )

        if result["success"]:
            msg = f"📄 *Fee Invoice — {month}*\n\n"
            msg += f"Student: {student_name}\n"
            msg += f"Amount: ₹{amount}\n"
            msg += f"Due Date: {due_date}\n"
            msg += f"From: {business_name}\n\n"
            msg += "_Please pay before the due date to avoid late fees._"

            return self._format_response(
                success=True,
                data={"month": month, "amount": amount, "due_date": due_date},
                message=msg
            )
        return result

    async def get_pending_fees(self, spreadsheet_id: str,
                               sheet_name: str = "Fees") -> Dict[str, Any]:
        """Returns all students with unpaid fees."""
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:G"
        )

        if not result["success"]:
            return result

        pending = []
        for row in result["data"]["rows"][1:]:
            if len(row) >= 6 and row[5] == "Unpaid":
                pending.append({
                    "month": row[0],
                    "phone": row[1],
                    "name": row[2],
                    "amount": row[3],
                    "due_date": row[4]
                })

        msg = f"💰 *Pending Fees: {len(pending)} students*\n\n"
        for p in pending:
            msg += f"• {p['name']} — ₹{p['amount']} (Due: {p['due_date']})\n"

        return self._format_response(
            success=True,
            data={"pending": pending, "count": len(pending)},
            message=msg
        )


class BatchTool(BaseTool):
    """
    Manages student batches and sends batch-wide announcements.
    """

    @property
    def tool_name(self) -> str:
        return "BatchTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        method = kwargs.pop("method", None)
        if method == "get_batch_students":
            return await self.get_batch_students(**kwargs)
        elif method == "send_batch_announcement":
            return await self.send_batch_announcement(**kwargs)
        return self._format_response(success=False, message=f"Unknown method '{method}'")

    async def get_batch_students(self, spreadsheet_id: str, batch_name: str,
                                 sheet_name: str = "Batches") -> Dict[str, Any]:
        """
        Returns all students in a specific batch.
        Columns: Batch | Phone | Name | Subject | Status
        """
        from app.tools.google.sheets_tool import GoogleSheetsTool
        sheets = GoogleSheetsTool()

        result = await sheets.execute(
            method="read_range",
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_name}!A:E"
        )

        if not result["success"]:
            return result

        students = []
        for row in result["data"]["rows"][1:]:
            if len(row) >= 3 and batch_name.lower() in row[0].lower():
                students.append({
                    "phone": row[1],
                    "name": row[2],
                    "subject": row[3] if len(row) > 3 else ""
                })

        return self._format_response(
            success=True,
            data={"students": students, "batch": batch_name, "count": len(students)},
            message=f"Batch '{batch_name}' has {len(students)} students."
        )

    async def send_batch_announcement(self, spreadsheet_id: str, batch_name: str,
                                      message: str,
                                      sheet_name: str = "Batches") -> Dict[str, Any]:
        """
        Prepares an announcement for all students in a batch.
        Returns the list of phone numbers so the WhatsApp bot can iterate and send.
        """
        students_result = await self.get_batch_students(spreadsheet_id, batch_name, sheet_name)

        if not students_result["success"]:
            return students_result

        students = students_result["data"]["students"]
        phones = [s["phone"] for s in students]

        formatted_msg = f"📢 *Announcement — {batch_name}*\n\n{message}"

        return self._format_response(
            success=True,
            data={"phones": phones, "message": formatted_msg, "count": len(phones)},
            message=f"Announcement ready. Will be sent to {len(phones)} students."
        )
