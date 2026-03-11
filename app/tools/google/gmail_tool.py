import base64
import os
import asyncio
from email.message import EmailMessage
from typing import Dict, Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.tools.base_tool import BaseTool
from app.core.config import settings

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

class GmailTool(BaseTool):
    """
    Google Workspace Tool: Gmail
    Sends automated emails via the Gmail API. 
    Crucial for sending free monthly invoices, payment receipts, and health reports
    to bypass WhatsApp's 24-hour window marketing costs.
    """

    @property
    def tool_name(self) -> str:
        return "GmailTool"

    def _get_service(self, delegated_email: str = None):
        """
        Constructs the Gmail API service.
        If delegated_email is provided, the Service Account attempts to act "on behalf of"
        that merchant's Gmail address. This requires Google Workspace Domain-Wide Delegation.
        Otherwise, it sends as the service account itself (catalyst-bot@...).
        """
        json_path = settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH
        if not json_path or not os.path.exists(json_path):
            raise ValueError(f"Google Service Account JSON missing at {json_path}.")

        creds = service_account.Credentials.from_service_account_file(json_path, scopes=SCOPES)
        
        # If the business has granted Domain-Wide Delegation, impersonate their email
        if delegated_email:
            creds = creds.with_subject(delegated_email)
            
        return build('gmail', 'v1', credentials=creds)

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Dispatcher for Gmail actions."""
        method_name = kwargs.pop("method", None)
        
        if not method_name:
            return self._format_response(success=False, message="Missing 'method' parameter.")
            
        try:
            if method_name == "send_email":
                return await self.send_email(**kwargs)
            elif method_name == "send_monthly_invoice":
                return await self.send_monthly_invoice(**kwargs)
            else:
                return self._format_response(success=False, message=f"Unknown method '{method_name}'")
        except Exception as e:
            return self.handle_error(e)

    async def send_email(self, to_email: str, subject: str, html_body: str, 
                         sender_email: str = "me") -> Dict[str, Any]:
        """
        Sends an HTML email.
        `sender_email` defaults to 'me' (the authenticated account).
        """
        # Create an standard email message
        message = EmailMessage()
        message.set_content("Please enable HTML in your email client to view this message.")
        message.add_alternative(html_body, subtype='html')
        
        message['To'] = to_email
        message['From'] = sender_email
        message['Subject'] = subject

        # Encode the message in base64url format as required by Gmail API
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        # Send it
        # If domain-wide delegation isn't set up, attempting to send as a different 'sender_email' 
        # will fail. We use 'me' by default which uses the service account's own token.
        service = self._get_service()
        
        try:
            request = service.users().messages().send(userId='me', body=create_message)
            send_message = await asyncio.to_thread(request.execute)
            
            return self._format_response(
                success=True,
                data={"message_id": send_message.get('id')},
                message=f"Successfully sent email to {to_email}."
            )
        except HttpError as error:
            # Common error: Service account doesn't have Domain-Wide Delegation to impersonate 
            # a standard @gmail.com account.
            return self._format_response(
                success=False,
                message=f"Gmail API Error: {error._get_reason()}. Make sure the Service Account has permission to send emails.",
                error_details=str(error)
            )

    async def send_monthly_invoice(self, to_email: str, business_name: str, month: str, 
                                   amount: str, payment_link: str) -> Dict[str, Any]:
        """
        Generates and sends a pre-formatted HTML invoice.
        """
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
                <h2>Invoice for {month}</h2>
                <p>Hello,</p>
                <p>This is your automated monthly invoice from <strong>{business_name}</strong>.</p>
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3>Amount Due: {amount}</h3>
                    <a href="{payment_link}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Pay Now Securely</a>
                </div>
                <p>Thank you for your business!</p>
            </body>
        </html>
        """
        return await self.send_email(
            to_email=to_email,
            subject=f"Invoice for {month} - {business_name}",
            html_body=html
        )
