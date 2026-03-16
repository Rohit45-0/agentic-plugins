import json
import os
from typing import Optional, Sequence

from google.oauth2 import service_account

from app.core.config import settings


def get_service_account_credentials(scopes: Optional[Sequence[str]] = None) -> service_account.Credentials:
    """
    Build service account credentials from either a JSON env var or a file path.
    """
    json_blob = settings.GOOGLE_SERVICE_ACCOUNT_JSON
    json_path = settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH

    if json_blob:
        info = json.loads(json_blob)
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)

    if json_path and os.path.exists(json_path):
        return service_account.Credentials.from_service_account_file(json_path, scopes=scopes)

    raise ValueError(
        "Google Service Account JSON missing. Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_JSON_PATH."
    )
