from __future__ import annotations

import sys
from pathlib import Path

# Add parent common directory to path
COMMON_DIR = Path(__file__).parent.parent.parent / "common"
sys.path.insert(0, str(COMMON_DIR))

from feishu.client import (
    BitableAttachmentUploadRequest,
    BitableAttachmentUploadResult,
    FeishuClient,
)
from feishu.auth import load_user_access_token
from feishu.errors import BitableAttachmentUploadError, BitableSyncError


def build_bitable_attachment_upload_request(
    *,
    app_token: str,
    attachment_paths: list[str] | None,
    access_token: str | None = None,
    endpoint: str = "https://open.feishu.cn",
) -> BitableAttachmentUploadRequest | None:
    normalized_paths = [str(Path(path)) for path in (attachment_paths or []) if str(path).strip()]
    if not normalized_paths:
        return None
    return BitableAttachmentUploadRequest(
        app_token=app_token,
        attachment_paths=normalized_paths,
        access_token=access_token,
        endpoint=endpoint,
    )


def perform_bitable_attachment_upload(
    request: BitableAttachmentUploadRequest,
) -> BitableAttachmentUploadResult:
    client = FeishuClient(endpoint=request.endpoint, user_access_token=request.access_token)
    return client.bitable_batch_upload_attachments(request)


def build_attachment_field_value(file_tokens: list[str]) -> list[dict[str, str]]:
    return FeishuClient.build_attachment_field_value(file_tokens)
