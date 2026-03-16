import os
import time
import uuid
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from jose import jwt, JWTError

from app.db.base import get_db
from app.db.models import WhatsAppBotConfig, User
from app.api.deps import get_current_user
from app.core.config import settings
import json
from cryptography.fernet import Fernet


STATE_ALGORITHM = "HS256"


def _get_fernet():
    if not settings.FERNET_KEY:
        raise HTTPException(status_code=500, detail="FERNET_KEY is not configured.")
    key = settings.FERNET_KEY.encode('utf-8')
    return Fernet(key)

router = APIRouter()

# If testing locally, allow insecure HTTP for OAuth
if settings.DEBUG:
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
# We need events to create bookings, readonly to check freeBusy availability,
# and drive.file to create and read the "Catalyst AI - Knowledge Base" doc
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file"
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


def _build_callback_url(request: Request) -> str:
    callback_url = str(request.url_for("calendar_callback"))
    if "railway.app" in str(request.url):
        callback_url = callback_url.replace("http://", "https://")
    return callback_url


def _encode_oauth_state(bot_config_id: str, user_id: str) -> str:
    now_ts = int(time.time())
    payload = {
        "sub": "calendar_oauth",
        "bot_config_id": bot_config_id,
        "user_id": user_id,
        "iat": now_ts,
        "exp": now_ts + settings.CALENDAR_OAUTH_STATE_TTL_SECONDS,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=STATE_ALGORITHM)


def _decode_oauth_state(state_token: str) -> tuple[str, str]:
    try:
        payload = jwt.decode(state_token, settings.SECRET_KEY, algorithms=[STATE_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    if payload.get("sub") != "calendar_oauth":
        raise HTTPException(status_code=400, detail="Invalid OAuth state payload")

    bot_config_id = payload.get("bot_config_id")
    user_id = payload.get("user_id")
    if not bot_config_id or not user_id:
        raise HTTPException(status_code=400, detail="Malformed OAuth state")
    return bot_config_id, user_id


async def _build_google_authorization_url(
    db: AsyncSession, request: Request, bot_config_id: str, current_user: User
) -> str:
    try:
        bot_uuid = uuid.UUID(bot_config_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bot_config_id format")

    res_bot = await db.execute(
        select(WhatsAppBotConfig).filter(
            WhatsAppBotConfig.id == bot_uuid,
            WhatsAppBotConfig.user_id == current_user.id,
        )
    )
    bot_config = res_bot.scalar_one_or_none()
    if not bot_config:
        raise HTTPException(status_code=404, detail="Bot config not found for this user")

    callback_url = _build_callback_url(request)
    flow = _get_flow(callback_url)
    state_token = _encode_oauth_state(str(bot_config.id), str(current_user.id))
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state_token,
    )
    return authorization_url


@router.get("/connect-url/{bot_config_id}")
async def get_connect_calendar_url(
    bot_config_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    authorization_url = await _build_google_authorization_url(db, request, bot_config_id, current_user)
    return {"authorization_url": authorization_url}


@router.get("/connect/{bot_config_id}")
async def connect_calendar(
    bot_config_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1: The merchant clicks 'Connect Google Calendar' on the dashboard.
    We redirect them to the Google Accounts consent screen.
    We pass their bot_config_id in the 'state' parameter so we know who they are when they return.
    """
    authorization_url = await _build_google_authorization_url(db, request, bot_config_id, current_user)
    return RedirectResponse(url=authorization_url)


@router.get("/callback")
async def calendar_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Step 2: Google redirects here with an authorization code.
    We exchange the code for a permanent access/refresh token, and save it to the DB.
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    
    bot_config_id, user_id = _decode_oauth_state(state)

    try:
        bot_uuid = uuid.UUID(bot_config_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed OAuth state IDs")

    res_config = await db.execute(
        select(WhatsAppBotConfig).filter(
            WhatsAppBotConfig.id == bot_uuid,
            WhatsAppBotConfig.user_id == user_uuid,
        )
    )
    config = res_config.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Bot config not found")

    callback_url = _build_callback_url(request)

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

    # Automatically create the Knowledge Base a Google Doc if they don't have one
    if not config.google_doc_id:
        try:
            drive_service = build("drive", "v3", credentials=creds)
            body = {
                "name": f"Catalyst AI - Knowledge Base ({config.business_display_name or 'Bot'})",
                "mimeType": "application/vnd.google-apps.document"
            }
            doc = drive_service.files().create(body=body, fields="id").execute()
            config.google_doc_id = doc.get("id")
            
            # Put some initial template content in it
            docs_service = build("docs", "v1", credentials=creds)
            docs_service.documents().batchUpdate(
                documentId=config.google_doc_id,
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
        except Exception as e:
            # We don't want to crash the whole OAuth flow if doc creation fails
            print(f"Failed to create Google Doc: {e}")

    await db.commit()

    return {"message": "Google Calendar and Knowledge Base connected successfully! You can close this tab."}


async def _get_google_creds(db: AsyncSession, bot_config_id: str) -> Credentials | None:
    res_config = await db.execute(select(WhatsAppBotConfig).filter(WhatsAppBotConfig.id == bot_config_id))
    config = res_config.scalar_one_or_none()
    if not config or not config.google_calendar_token:
        return None
        
    token_data = config.google_calendar_token
    if "encrypted_data" in token_data:
        fernet = _get_fernet()
        decrypted_bytes = fernet.decrypt(token_data["encrypted_data"].encode("utf-8"))
        token_data = json.loads(decrypted_bytes.decode("utf-8"))

    return Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes")
    )

async def get_calendar_service(db: AsyncSession, bot_config_id: str):
    creds = await _get_google_creds(db, bot_config_id)
    if not creds: return None
    return build("calendar", "v3", credentials=creds)

async def get_docs_service(db: AsyncSession, bot_config_id: str):
    creds = await _get_google_creds(db, bot_config_id)
    if not creds: return None
    return build("docs", "v1", credentials=creds)

async def get_drive_service(db: AsyncSession, bot_config_id: str):
    creds = await _get_google_creds(db, bot_config_id)
    if not creds: return None
    return build("drive", "v3", credentials=creds)
