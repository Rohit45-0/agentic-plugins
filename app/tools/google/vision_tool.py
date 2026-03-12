import asyncio
import os
from typing import Dict, Any

from app.tools.base_tool import BaseTool
from app.core.config import settings

class VisionTool(BaseTool):
    """
    Google Workspace Tool: Vision (OCR)
    Extracts raw text from messy, handwritten grocery lists, prescriptions, or menus sent via WhatsApp.
    Operates using the same Service Account JSON as the Sheets Tool.
    """

    @property
    def tool_name(self) -> str:
        return "VisionTool"

    def _get_credentials_path(self) -> str:
        json_path = settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH
        if not json_path or not os.path.exists(json_path):
            raise ValueError(f"Google Service Account JSON missing at {json_path}.")
        return json_path

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Dispatcher for Vision/OCR actions."""
        method_name = kwargs.pop("method", None)
        
        if not method_name:
            return self._format_response(success=False, message="Missing 'method' parameter.")
            
        try:
            if method_name == "extract_text_from_image":
                return await self.extract_text_from_image(**kwargs)
            elif method_name == "parse_order_from_image":
                return await self.parse_order_from_image(**kwargs)
            else:
                return self._format_response(success=False, message=f"Unknown method '{method_name}'")
        except Exception as e:
            return self.handle_error(e)

    async def mock_execute(self, **kwargs) -> Dict[str, Any]:
        """Return fake extracted text if in MOCK mode to avoid API costs during dev."""
        method_name = kwargs.get("method")
        
        if method_name == "extract_text_from_image":
            return self._format_response(
                success=True,
                data={"extracted_text": "2 kg Aashirvaad Atta\n1 Surf Excel 500g\nAmul Butter"},
                message="Mock: Successfully extracted text."
            )
        elif method_name == "parse_order_from_image":
            return self._format_response(
                success=True,
                data={
                    "items": ["Aashirvaad Atta", "Surf Excel", "Amul Butter"],
                    "quantities": ["2 kg", "500g", "1"],
                    "special_notes": ""
                },
                message="Mock: Successfully parsed order."
            )
            
        return await super().mock_execute(**kwargs)

    async def extract_text_from_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Takes raw image bytes (e.g., downloaded directly from WhatsApp media URL)
        and sends it to Google Cloud Vision for Document Text Detection (OCR).
        """
        try:
            from google.cloud import vision
            from google.oauth2 import service_account
        except ImportError:
            return self._format_response(success=False, message="google-cloud-vision not installed.")

        # Mount the credentials explicitly so we don't rely on OS Environment Variables
        creds_path = self._get_credentials_path()
        credentials = service_account.Credentials.from_service_account_file(creds_path)
        
        client = vision.ImageAnnotatorClient(credentials=credentials)
        image = vision.Image(content=image_bytes)

        # We use document_text_detection as it is optimized for dense handwritten/printed text
        def _call_vision():
            return client.document_text_detection(image=image)
            
        response = await asyncio.to_thread(_call_vision)

        if response.error.message:
            return self._format_response(
                success=False, 
                message=f"Google Vision Error: {response.error.message}"
            )

        extracted_text = response.full_text_annotation.text
        
        return self._format_response(
            success=True,
            data={"extracted_text": extracted_text},
            message="Successfully extracted text via Google Vision."
        )

    async def parse_order_from_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Step 1: Extract messy text using Vision
        Step 2: Clean it up using the LLM (GPT-4o) into a perfect JSON structure.
        """
        vision_result = await self.extract_text_from_image(image_bytes)
        
        if not vision_result["success"]:
            return vision_result
            
        raw_text = vision_result["data"]["extracted_text"]
        
        # In a real scenario, we would pass 'raw_text' to the OpenAI/Langchain pipeline here.
        # For now, we return the raw text with a prompt suggestion for the AI.
        
        system_prompt = (
            "You are an AI order parser. Convert the following messy OCR text into a strict JSON list "
            "of items and quantities. If it looks like a medical prescription, flag it as 'prescription'."
        )

        
        return self._format_response(
            success=True,
            data={
                "raw_text": raw_text,
                "suggested_llm_prompt": system_prompt
            },
            message="Extracted. Ready for LLM formatting."
        )
