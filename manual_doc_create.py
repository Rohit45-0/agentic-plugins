import asyncio
import json
from sqlalchemy.future import select
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.db.base import AsyncSessionLocal
from app.db.models import WhatsAppBotConfig
from app.api.calendar import _get_fernet

async def manual_create_knowledge_doc(bot_config_id: str):
    print(f"Starting doc creation for {bot_config_id}")
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(WhatsAppBotConfig).filter(WhatsAppBotConfig.id == bot_config_id))
        config = res.scalar_one_or_none()
        if not config or not config.google_calendar_token:
            print("Bot config or token not found.")
            return

        token_data = config.google_calendar_token
        if "encrypted_data" in token_data:
            fernet = _get_fernet()
            decrypted_bytes = fernet.decrypt(token_data["encrypted_data"].encode("utf-8"))
            token_data = json.loads(decrypted_bytes.decode("utf-8"))

        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes")
        )

        print(f"Token scopes: {creds.scopes}")
        
        # Check if drive.file is in scopes
        if "https://www.googleapis.com/auth/drive.file" not in creds.scopes:
            print("ERROR: Drive scope not found in token! User needs to RE-CONNECT to grant new permissions.")
            return

        try:
            drive_service = build("drive", "v3", credentials=creds)
            body = {
                "name": f"Catalyst AI - Knowledge Base ({config.business_display_name or 'Bot'})",
                "mimeType": "application/vnd.google-apps.document"
            }
            print("Creating drive file...")
            doc = drive_service.files().create(body=body, fields="id").execute()
            doc_id = doc.get("id")
            print(f"Created doc with ID: {doc_id}")
            
            # Put some initial template content
            docs_service = build("docs", "v1", credentials=creds)
            print("Inserting text...")
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={
                    "requests": [
                        {
                            "insertText": {
                                "location": {"index": 1},
                                "text": "Welcome to your Catalyst AI Knowledge Base!\n\nWrite down your business rules, prices, menus, and any other information you want your AI bot to know about. You can update this document at any time and then click 'Sync to Bot' in your dashboard to immediately update your bot's brain."
                            }
                        }
                    ]
                }
            ).execute()
            
            config.google_doc_id = doc_id
            await db.commit()
            print("Success: Google Doc created and saved to DB.")

        except Exception as e:
            print(f"FAILED to create Google Doc: {e}")

if __name__ == "__main__":
    # The user's bot config ID as found in previous steps
    asyncio.run(manual_create_knowledge_doc('ef72d6ec-49a5-4df8-b618-2636cb1c6978'))
