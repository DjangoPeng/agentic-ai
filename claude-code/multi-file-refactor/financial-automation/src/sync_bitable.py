from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent common directory to path
COMMON_DIR = Path(__file__).parent.parent.parent / "common"
sys.path.insert(0, str(COMMON_DIR))

from feishu.errors import BitableSyncError
from feishu.client import FeishuClient


EXPENSE_TYPE_LABELS = {
    "transportation_fee": "🚄 交通报销",
}

VALIDATION_STATUS_LABELS = {
    "pass": "✅ 通过",
    "warning": "⚠️ 待复核",
    "error": "❌ 异常",
}

TRANSPORTATION_TYPES = {"transportation_fee"}

TRANSPORT_FIELD_NAMES = {
    "doc_id": "doc_id",
    "expense_type": "报销类型",
    "source_file_name": "源文件名",
    "attachment": "票据附件",
    "invoice_number": "票据号码",
    "amount": "金额",
    "currency": "币种",
    "buyer_name": "购票主体",
    "buyer_tax_id": "购票主体税号",
    "passenger_name": "乘车人",
    "transport_number": "车次",
    "from_station": "出发站",
    "to_station": "到达站",
    "travel_date": "乘车日期",
    "departure_time": "发车时间",
    "seat_no": "座位号",
    "seat_class": "座席",
    "validation_status": "校验状态",
    "needs_review": "是否复核",
    "review_reasons": "复核原因",
}

EXPENSE_FIELD_NAMES = {
    "doc_id": "doc_id",
    "expense_type": "报销类型",
    "source_file_name": "源文件名",
    "attachment": "票据附件",
    "invoice_number": "票据号码",
    "issue_date": "开票日期",
    "amount": "金额",
    "currency": "币种",
    "buyer_name": "购买方名称",
    "buyer_tax_id": "购买方税号",
    "seller_name": "销售方名称",
    "seller_tax_id": "销售方税号",
    "item_name": "项目名称",
    "quantity": "数量",
    "unit_price": "单价",
    "line_amount": "项目金额",
    "tax_rate": "税率",
    "tax_amount": "税额",
    "validation_status": "校验状态",
    "needs_review": "是否复核",
    "review_reasons": "复核原因",
}


class BitableSyncError(RuntimeError):
    """Raised when the Feishu Bitable sync fails."""


@dataclass
class BitableSettings:
    enabled: bool
    dry_run: bool
    endpoint: str
    batch_size: int
    mode: str
    include_attachments: bool
    app_id: str
    app_secret: str
    app_token: str
    transport_table_id: str
    expense_table_id: str


def sync_skill_result_with_config(
    skill_result: dict[str, Any],
    config: dict[str, Any],
    *,
    attachment_paths: list[str] | None = None,
) -> dict[str, Any]:
    settings = load_bitable_settings(config)
    if not settings.enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "message": "Bitable sync is disabled in configuration.",
        }
    return sync_skill_result_to_bitable(
        skill_result,
        settings,
        attachment_paths=attachment_paths,
    )


def load_bitable_settings(config: dict[str, Any]) -> BitableSettings:
    bitable = config.get("sync", {}).get("bitable", {})
    endpoint = str(bitable.get("endpoint") or "https://open.feishu.cn").rstrip("/")
    batch_size = int(bitable.get("batch_size") or 200)
    mode = str(bitable.get("mode") or "user_identity").strip() or "user_identity"
    include_attachments = bool(bitable.get("include_attachments", False))

    return BitableSettings(
        enabled=bool(bitable.get("enabled", False)),
        dry_run=bool(bitable.get("dry_run", True)),
        endpoint=endpoint,
        batch_size=max(1, min(batch_size, 500)),
        mode=mode,
        include_attachments=include_attachments,
        app_id=_resolve_secret(bitable, "app_id"),
        app_secret=_resolve_secret(bitable, "app_secret"),
        app_token=_resolve_secret(bitable, "app_token"),
        transport_table_id=_resolve_secret(bitable, "transport_table_id"),
        expense_table_id=_resolve_secret(bitable, "expense_table_id"),
    )


def sync_skill_result_to_bitable(
    skill_result: dict[str, Any],
    settings: BitableSettings,
    *,
    attachment_paths: list[str] | None = None,
) -> dict[str, Any]:
    documents = skill_result.get("documents", [])
    if not isinstance(documents, list):
        raise BitableSyncError("skill_result.documents must be a list.")

    attachment_index = _build_attachment_index(attachment_paths or [])
    transport_records: list[dict[str, Any]] = []
    expense_records: list[dict[str, Any]] = []

    # Initialize FeishuClient only if not dry_run and using app_identity
    client: FeishuClient | None = None
    if not settings.dry_run and settings.mode == "app_identity":
        client = FeishuClient(
            endpoint=settings.endpoint,
            app_id=settings.app_id,
            app_secret=settings.app_secret,
        )

    for document in documents:
        if not isinstance(document, dict):
            continue
        attachment_payload: list[dict[str, Any]] | str = _build_attachment_text(document.get("source_file_name"))
        if settings.include_attachments and settings.mode == "app_identity" and client:
            source_name = str(document.get("source_file_name") or "")
            source_path = attachment_index.get(source_name)
            if source_path:
                try:
                    uploaded = client.bitable_upload_attachment(
                        settings.app_token,
                        source_path,
                    )
                    attachment_payload = [{"file_token": uploaded["file_token"], "name": uploaded["file_name"]}]
                except BitableSyncError:
                    attachment_payload = _build_attachment_text(source_name)

        invoice_type = str(document.get("document_type") or "unknown")
        if invoice_type in TRANSPORTATION_TYPES:
            transport_records.append(build_transport_record(document, attachment_payload))
        else:
            expense_records.append(build_expense_record(document, attachment_payload))

    summary = {
        "enabled": True,
        "dry_run": settings.dry_run,
        "status": "dry_run" if settings.dry_run else (
            "completed" if settings.mode == "app_identity" else "deferred_to_session_user_identity"
        ),
        "mode": settings.mode,
        "include_attachments": settings.include_attachments,
        "message": (
            "Use current OpenClaw session with Feishu user identity to continue real bitable create/update; this preview/prepared result is not task completion by itself."
            if settings.mode != "app_identity"
            else "App-identity bitable sync executed."
        ),
        "tables": {
            "transport": {
                "table_id": settings.transport_table_id,
                "records_prepared": len(transport_records),
                "records_written": 0,
            },
            "expense": {
                "table_id": settings.expense_table_id,
                "records_prepared": len(expense_records),
                "records_written": 0,
            },
        },
    }

    if settings.dry_run or settings.mode != "app_identity" or not client:
        if transport_records:
            summary["tables"]["transport"]["preview"] = transport_records[:3]
        if expense_records:
            summary["tables"]["expense"]["preview"] = expense_records[:3]
        return summary

    if transport_records:
        result = client.bitable_batch_create(
            settings.app_token,
            settings.transport_table_id,
            transport_records,
            batch_size=settings.batch_size,
        )
        summary["tables"]["transport"]["records_written"] = result.get("total_written", 0)

    if expense_records:
        result = client.bitable_batch_create(
            settings.app_token,
            settings.expense_table_id,
            expense_records,
            batch_size=settings.batch_size,
        )
        summary["tables"]["expense"]["records_written"] = result.get("total_written", 0)

    return summary


def build_transport_record(document: dict[str, Any], attachment_payload: list[dict[str, Any]] | str) -> dict[str, Any]:
    extraction = document.get("extraction", {}) or {}
    doc_info = extraction.get("document", {}) or {}
    buyer = extraction.get("buyer", {}) or {}
    travel = extraction.get("travel", {}) or {}
    passenger = extraction.get("passenger", {}) or {}
    validation = document.get("validation", {}) or {}
    review = document.get("review", {}) or {}
    source_file_name = document.get("source_file_name")

    fields: dict[str, Any] = {
        TRANSPORT_FIELD_NAMES["doc_id"]: document.get("doc_id"),
        TRANSPORT_FIELD_NAMES["expense_type"]: _map_expense_type_label(document.get("document_type")),
        TRANSPORT_FIELD_NAMES["source_file_name"]: source_file_name,
        TRANSPORT_FIELD_NAMES["attachment"]: attachment_payload or _build_attachment_text(source_file_name),
        TRANSPORT_FIELD_NAMES["invoice_number"]: doc_info.get("invoice_number"),
        TRANSPORT_FIELD_NAMES["amount"]: doc_info.get("amount"),
        TRANSPORT_FIELD_NAMES["currency"]: doc_info.get("currency"),
        TRANSPORT_FIELD_NAMES["buyer_name"]: buyer.get("name"),
        TRANSPORT_FIELD_NAMES["buyer_tax_id"]: buyer.get("tax_id"),
        TRANSPORT_FIELD_NAMES["passenger_name"]: passenger.get("name"),
        TRANSPORT_FIELD_NAMES["transport_number"]: travel.get("transport_number"),
        TRANSPORT_FIELD_NAMES["from_station"]: travel.get("from_station"),
        TRANSPORT_FIELD_NAMES["to_station"]: travel.get("to_station"),
        TRANSPORT_FIELD_NAMES["travel_date"]: _date_to_millis(travel.get("travel_date")),
        TRANSPORT_FIELD_NAMES["departure_time"]: travel.get("departure_time"),
        TRANSPORT_FIELD_NAMES["seat_no"]: passenger.get("seat_no"),
        TRANSPORT_FIELD_NAMES["seat_class"]: passenger.get("seat_class"),
        TRANSPORT_FIELD_NAMES["validation_status"]: _map_validation_status(validation.get("status")),
        TRANSPORT_FIELD_NAMES["needs_review"]: _map_review_flag(review.get("needs_review")),
        TRANSPORT_FIELD_NAMES["review_reasons"]: _format_review_reasons(review.get("reasons")),
    }
    return _drop_none(fields)


def build_expense_record(document: dict[str, Any], attachment_payload: list[dict[str, Any]] | str) -> dict[str, Any]:
    extraction = document.get("extraction", {}) or {}
    doc_info = extraction.get("document", {}) or {}
    buyer = extraction.get("buyer", {}) or {}
    seller = extraction.get("seller", {}) or {}
    line_items = extraction.get("line_items", []) or []
    first_item = line_items[0] if line_items else {}
    validation = document.get("validation", {}) or {}
    review = document.get("review", {}) or {}
    source_file_name = document.get("source_file_name")

    fields: dict[str, Any] = {
        EXPENSE_FIELD_NAMES["doc_id"]: document.get("doc_id"),
        EXPENSE_FIELD_NAMES["expense_type"]: _map_expense_type_label(document.get("document_type")),
        EXPENSE_FIELD_NAMES["source_file_name"]: source_file_name,
        EXPENSE_FIELD_NAMES["attachment"]: attachment_payload or _build_attachment_text(source_file_name),
        EXPENSE_FIELD_NAMES["invoice_number"]: doc_info.get("invoice_number"),
        EXPENSE_FIELD_NAMES["issue_date"]: _date_to_millis(doc_info.get("issue_date")),
        EXPENSE_FIELD_NAMES["amount"]: doc_info.get("amount"),
        EXPENSE_FIELD_NAMES["currency"]: doc_info.get("currency"),
        EXPENSE_FIELD_NAMES["buyer_name"]: buyer.get("name"),
        EXPENSE_FIELD_NAMES["buyer_tax_id"]: buyer.get("tax_id"),
        EXPENSE_FIELD_NAMES["seller_name"]: seller.get("name"),
        EXPENSE_FIELD_NAMES["seller_tax_id"]: seller.get("tax_id"),
        EXPENSE_FIELD_NAMES["item_name"]: first_item.get("item_name"),
        EXPENSE_FIELD_NAMES["quantity"]: first_item.get("quantity"),
        EXPENSE_FIELD_NAMES["unit_price"]: first_item.get("unit_price"),
        EXPENSE_FIELD_NAMES["line_amount"]: first_item.get("line_amount"),
        EXPENSE_FIELD_NAMES["tax_rate"]: _normalize_tax_rate(first_item.get("tax_rate")),
        EXPENSE_FIELD_NAMES["tax_amount"]: first_item.get("tax_amount"),
        EXPENSE_FIELD_NAMES["validation_status"]: _map_validation_status(validation.get("status")),
        EXPENSE_FIELD_NAMES["needs_review"]: _map_review_flag(review.get("needs_review")),
        EXPENSE_FIELD_NAMES["review_reasons"]: _format_review_reasons(review.get("reasons")),
    }
    return _drop_none(fields)


def _resolve_secret(section: dict[str, Any], key: str) -> str:
    direct_value = section.get(key)
    if isinstance(direct_value, str) and direct_value.strip():
        return direct_value.strip()
    env_key = section.get(f"{key}_env")
    if isinstance(env_key, str) and env_key.strip():
        return os.environ.get(env_key.strip(), "").strip()
    return ""


def _build_attachment_index(paths: list[str]) -> dict[str, str]:
    index: dict[str, str] = {}
    for raw in paths:
        name = os.path.basename(raw)
        index[name] = raw
    return index


def _date_to_millis(value: Any) -> int | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return int(dt.timestamp() * 1000)


def _join_review_reasons(reasons: Any) -> str:
    if isinstance(reasons, list):
        return ", ".join(str(item) for item in reasons if item)
    if reasons:
        return str(reasons)
    return ""


def _map_expense_type_label(value: Any) -> str:
    raw = str(value or "unknown").strip()
    return EXPENSE_TYPE_LABELS.get(raw, "🧾 费用报销")


def _map_validation_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return VALIDATION_STATUS_LABELS.get(raw, raw or "⚪ 未知")


def _map_review_flag(value: Any) -> str:
    return "是" if bool(value) else "否"


def _normalize_tax_rate(value: Any) -> float | Any:
    if isinstance(value, str):
        raw = value.strip()
        if raw.endswith("%"):
            try:
                return float(raw[:-1]) / 100.0
            except ValueError:
                return value
    return value


def _build_attachment_text(source_file_name: Any) -> str:
    name = str(source_file_name or "").strip()
    if not name:
        return "📎 原图已接收，待挂载"
    return f"🖼️ 原图已接收：{name}"


def _format_review_reasons(reasons: Any) -> str:
    text = _join_review_reasons(reasons)
    if not text:
        return ""
    return f"👀 {text}"


def _build_transport_summary(document: dict[str, Any]) -> str:
    extraction = document.get("extraction", {}) or {}
    doc_info = extraction.get("document", {}) or {}
    travel = extraction.get("travel", {}) or {}
    passenger = extraction.get("passenger", {}) or {}
    amount = doc_info.get("amount")
    amount_text = f"¥{amount:g}" if isinstance(amount, (int, float)) else ""
    route = " → ".join(part for part in [travel.get("from_station"), travel.get("to_station")] if part)
    parts = ["🚄"]
    for value in [passenger.get("name"), travel.get("transport_number"), route, amount_text]:
        if value:
            parts.append(str(value))
    return "｜".join(parts)


def _build_expense_summary(document: dict[str, Any]) -> str:
    extraction = document.get("extraction", {}) or {}
    doc_info = extraction.get("document", {}) or {}
    line_items = extraction.get("line_items", []) or []
    first_item = line_items[0] if line_items else {}
    amount = doc_info.get("amount")
    amount_text = f"¥{amount:g}" if isinstance(amount, (int, float)) else ""
    parts = ["🧾"]
    for value in [first_item.get("item_name"), amount_text, doc_info.get("issue_date")]:
        if value:
            parts.append(str(value))
    return "｜".join(parts)


def _drop_none(fields: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if value == []:
            continue
        cleaned[key] = value
    return cleaned


def _chunk_records(records: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [records[index : index + size] for index in range(0, len(records), size)]
