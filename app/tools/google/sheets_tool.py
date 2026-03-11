import asyncio
import os
from typing import Dict, Any, List

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.tools.base_tool import BaseTool
from app.core.config import settings

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

class GoogleSheetsTool(BaseTool):
    """
    Core Infrastructure Tool: Google Sheets
    Connects to the Google Sheets API via a Service Account to perform real-time reads and writes.
    Perfect for Udhar Ledgers, real-time Order injection, and Attendance trackers.
    """

    @property
    def tool_name(self) -> str:
        return "GoogleSheetsTool"

    def _get_service(self):
        """Constructs and returns the Google Sheets API v4 service resource."""
        json_path = settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH
        if not json_path or not os.path.exists(json_path):
            raise ValueError(f"Google Service Account JSON missing at {json_path}. Please configure GOOGLE_SERVICE_ACCOUNT_JSON_PATH.")

        creds = service_account.Credentials.from_service_account_file(json_path, scopes=SCOPES)
        return build('sheets', 'v4', credentials=creds)

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Main dispatcher for real API calls to Google Sheets.
        """
        method_name = kwargs.pop("method", None)
        if not method_name:
            return self._format_response(success=False, message="Missing 'method' parameter.")

        try:
            if method_name == "append_row":
                return await self.append_row(**kwargs)
            elif method_name == "read_range":
                return await self.read_range(**kwargs)
            elif method_name == "update_cell":
                return await self.update_cell(**kwargs)
            else:
                return self._format_response(success=False, message=f"Unknown method '{method_name}'")
        except Exception as e:
            return self.handle_error(e)

    async def append_row(self, spreadsheet_id: str, range_name: str, row_data: List[Any], 
                         value_input_option: str = "USER_ENTERED") -> Dict[str, Any]:
        """
        Appends a single row of data to the bottom of the specified range.
        Format range_name as: "SheetName!A:A" or just "SheetName"
        """
        service = self._get_service()
        body = {
            "values": [row_data]
        }
        
        # Async wrap the synchronous google api call
        request = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, 
            range=range_name,
            valueInputOption=value_input_option, 
            body=body
        )
        response = await asyncio.to_thread(request.execute)

        return self._format_response(
            success=True,
            data={"updated_range": response.get('updates', {}).get('updatedRange')},
            message=f"Successfully appended {len(row_data)} columns to sheet."
        )

    async def read_range(self, spreadsheet_id: str, range_name: str) -> Dict[str, Any]:
        """
        Reads a range of data. Returns a list of lists representing Rows x Columns.
        Format range_name as "SheetName!A1:E10"
        """
        service = self._get_service()
        
        request = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, 
            range=range_name
        )
        response = await asyncio.to_thread(request.execute)
        
        values = response.get('values', [])
        
        return self._format_response(
            success=True,
            data={"rows": values, "row_count": len(values)},
            message=f"Successfully read {len(values)} rows."
        )

    async def update_cell(self, spreadsheet_id: str, range_name: str, value: Any) -> Dict[str, Any]:
        """
        Updates a specific individual cell (or range) with a new value.
        range_name MUST be specific like "SheetName!C5"
        """
        service = self._get_service()
        body = {
            "values": [[value]]
        }
        
        request = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, 
            range=range_name,
            valueInputOption="USER_ENTERED", 
            body=body
        )
        response = await asyncio.to_thread(request.execute)

        return self._format_response(
            success=True,
            data={"updated_cells": response.get('updatedCells')},
            message=f"Successfully updated cell {range_name}."
        )
