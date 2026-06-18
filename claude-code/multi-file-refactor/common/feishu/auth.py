from __future__ import annotations

import json
from pathlib import Path

from .errors import FeishuAuthError, BitableAttachmentUploadError
from .http import post_json


def get_tenant_access_token(endpoint: str, app_id: str, app_secret: str) -> str:
    """Get Feishu tenant access token using app_id and app_secret."""
    if not app_id or not app_secret:
        raise FeishuAuthError("Missing FEISHU_APP_ID or FEISHU_APP_SECRET.")

    response = post_json(
        f"{endpoint.rstrip('/')}/open-apis/auth/v3/tenant_access_token/internal",
        {
            "app_id": app_id,
            "app_secret": app_secret,
        },
    )
    token = str(response.get("tenant_access_token") or "")
    if not token:
        raise FeishuAuthError("Failed to obtain tenant_access_token from Feishu.")
    return token


def load_user_access_token(token_file: str | Path) -> str:
    """Load user access token from a JSON file."""
    payload = json.loads(Path(token_file).read_text(encoding="utf-8") or "{}")
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise BitableAttachmentUploadError(
            f"No access_token found in token file: {token_file}"
        )
    return token
