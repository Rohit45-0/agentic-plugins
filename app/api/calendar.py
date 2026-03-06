import os
import datetime
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.db.base import get_db
from app.db.models import WhatsAppBotConfig
from app.core.config import settings
import json
from cryptography.fernet import Fernet

def _get_fernet():
    key = settings.FERNET_KEY.encode('utf-8')
    return Fernet(key)

router = APIRouter()

# If testing locally, allow insecure HTTP for OAuth
if settings.DEBUG:
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
# We need events to create bookings, readonly to check freeBusy availability,
# and drive.readonly to read Google Docs for RAG knowledge sync
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

def _get_flow(redirect_uri: str):
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google credentials not configured.")
        
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "project_id": "nexus-calendar",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uris": [redirect_uri]
        }
    }
    
    flow = Flow.from_client_config(
        client_config, 
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    return flow


@router.get("/connect/{bot_config_id}")
async def connect_calendar(bot_config_id: str, request: Request):
    """
    Step 1: The merchant clicks 'Connect Google Calendar' on the dashboard.
    We redirect them to the Google Accounts consent screen.
    We pass their bot_config_id in the 'state' parameter so we know who they are when they return.
    """
    callback_url = str(request.url_for("calendar_callback"))
    if "railway.app" in str(request.url):
        callback_url = callback_url.replace("http://", "https://")
        
    flow = _get_flow(callback_url)
    authorization_url, state = flow.authorization_url(
        access_type="offline", # Need offline access to get a refresh token
        prompt="consent",      # Force consent screen to guarantee refresh token is given
        state=bot_config_id    # Pass ID back and forth
    )
    return RedirectResponse(url=authorization_url)


@router.get("/callback")
async def calendar_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Step 2: Google redirects here with an authorization code.
    We exchange the code for a permanent access/refresh token, and save it to the DB.
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state") # This is the bot_config_id
    
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
        
    res_config = await db.execute(select(WhatsAppBotConfig).filter(WhatsAppBotConfig.id == state))
    config = res_config.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Bot config not found")

    callback_url = str(request.url_for("calendar_callback"))
    if "railway.app" in str(request.url):
        callback_url = callback_url.replace("http://", "https://")

    flow = _get_flow(callback_url)
    try:
        # Provide the full url from the request so oauthlib can verify the state
        # Railway terminates SSL, so we rewrite the scheme if necessary
        req_url = str(request.url)
        if "railway.app" in req_url:
            req_url = req_url.replace("http://", "https://")
            
        flow.fetch_token(authorization_response=req_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch token: {str(e)}")

    creds = flow.credentials
    
    # Save token payload to PostgreSQL, encrypted via Fernet
    fernet = _get_fernet()
    raw_token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }
    encrypted_bytes = fernet.encrypt(json.dumps(raw_token_data).encode("utf-8"))

    config.google_calendar_token = {
        "encrypted_data": encrypted_bytes.decode("utf-8")
    }
    await db.commit()

    return {"message": "Google Calendar connected successfully! You can close this tab."}


async def get_calendar_service(db: AsyncSession, bot_config_id: str):
    """
    Step 3: Internal helper function.
    Given a bot_config_id, returns a working Google Calendar API client.
    Automatically uses the refresh token if the current token is expired.
    """
    res_config = await db.execute(select(WhatsAppBotConfig).filter(WhatsAppBotConfig.id == bot_config_id))
    config = res_config.scalar_one_or_none()
    if not config or not config.google_calendar_token:
        return None
        
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
    
    return build("calendar", "v3", credentials=creds)
