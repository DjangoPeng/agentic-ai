from __future__ import annotations


class FeishuApiError(RuntimeError):
    """Base exception for all Feishu API errors."""


class FeishuAuthError(FeishuApiError):
    """Raised when Feishu authentication fails (token, app_id/app_secret)."""


class BitableSyncError(FeishuApiError):
    """Raised when Feishu Bitable sync operation fails."""


class BitableAttachmentUploadError(FeishuApiError):
    """Raised when a Bitable attachment upload cannot be completed."""
