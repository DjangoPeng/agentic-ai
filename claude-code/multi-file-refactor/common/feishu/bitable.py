from __future__ import annotations

from typing import Any


def pick_reusable_record_id(
    records: list[dict[str, Any]],
    primary_field: str = "doc_id",
) -> str | None:
    """Find a record with empty primary field to reuse (blank row strategy)."""
    for record in records:
        if not isinstance(record, dict):
            continue
        fields = record.get("fields")
        if not isinstance(fields, dict):
            continue
        primary_value = fields.get(primary_field)
        if primary_value in (None, "", []):
            record_id = record.get("record_id") or record.get("id")
            if isinstance(record_id, str) and record_id.strip():
                return record_id.strip()
    return None


def choose_write_action(existing_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Choose between update (reuse blank row) or create new row."""
    reusable = pick_reusable_record_id(existing_records)
    if reusable:
        return {"action": "update", "record_id": reusable}
    return {"action": "create"}


def coerce_field_value(value: Any, field_meta: dict[str, Any] | None = None) -> Any:
    """Coerce a value to the appropriate Bitable field type."""
    if field_meta is None:
        return value

    field_type = int((field_meta.get("type") or 0) or 0)

    # Bitable field types: 1=Text, 2=Number, 3=SingleSelect, 4=MultiSelect, etc.
    if value is None:
        return None

    if field_type == 2:  # Number
        if isinstance(value, (int, float)):
            return value
        try:
            return int(str(value))
        except (ValueError, TypeError):
            try:
                return float(str(value))
            except (ValueError, TypeError):
                return None

    if field_type in (1, 3):  # Text or SingleSelect
        if isinstance(value, list):
            return ", ".join(str(v) for v in value if v is not None)
        return str(value) if value is not None else None

    if field_type == 4:  # MultiSelect
        if isinstance(value, list):
            return [str(v) for v in value if v is not None]
        return [str(value)] if value is not None else []

    if field_type == 1001:  # CreatedBy / UpdatedBy (Person)
        if isinstance(value, dict) and "id" in value:
            return value
        return None

    if field_type == 5:  # Date (milliseconds)
        if isinstance(value, (int, float)):
            return int(value)
        try:
            return int(str(value))
        except (ValueError, TypeError):
            return None

    return value


def coerce_row(
    row: dict[str, Any],
    fields_meta: list[dict[str, Any]],
) -> dict[str, Any]:
    """Coerce all fields in a row to match Bitable field types."""
    meta_by_name = {m.get("field_name"): m for m in fields_meta if m.get("field_name")}
    result: dict[str, Any] = {}

    for field_name, value in row.items():
        if value is None:
            continue
        field_meta = meta_by_name.get(field_name)
        coerced = coerce_field_value(value, field_meta)
        if coerced is not None:
            result[field_name] = coerced

    return result
