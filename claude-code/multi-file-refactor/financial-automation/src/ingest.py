from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
SKIP_REASON_UNSUPPORTED_EXT = "unsupported_ext"
SKIP_REASON_EMPTY_FILE = "empty_file"
SKIP_REASON_TEMP_FILE = "temp_file"
SKIP_REASON_NOT_READABLE = "not_readable"
SKIP_REASON_NOT_FILE = "not_file"


def load_input_documents(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load and normalize local input files into a stable document list."""
    input_dir_value = (
        config.get("paths", {}).get("input_dir")
        if isinstance(config, dict)
        else None
    )
    input_dir = Path(str(input_dir_value)).expanduser() if input_dir_value else None

    report: dict[str, Any] = {
        "source": "local_dir",
        "input_dir": str(input_dir) if input_dir else None,
        "total_seen": 0,
        "accepted": 0,
        "skipped": 0,
        "skip_reasons": {},
        "errors": [],
    }
    documents: list[dict[str, Any]] = []

    if input_dir is None:
        report["errors"].append("Missing paths.input_dir in app config.")
        return documents, report

    if not input_dir.exists():
        report["errors"].append(f"Input directory does not exist: {input_dir}")
        return documents, report

    if not input_dir.is_dir():
        report["errors"].append(f"Input path is not a directory: {input_dir}")
        return documents, report

    for path in _scan_local_dir(input_dir):
        report["total_seen"] += 1
        accepted, reason = _is_supported_file(path)
        if not accepted:
            _count_skip_reason(report, reason)
            continue

        try:
            item = _build_document_item(path)
        except OSError as exc:
            _count_skip_reason(report, SKIP_REASON_NOT_READABLE)
            report["errors"].append(f"Failed to stat/read file {path}: {exc}")
            continue

        documents.append(item)
        report["accepted"] += 1

    report["skipped"] = report["total_seen"] - report["accepted"]
    documents.sort(key=lambda x: (x["modified_at"], x["file_path"].lower()))
    return documents, report


def _scan_local_dir(input_dir: Path) -> list[Path]:
    return [p for p in input_dir.rglob("*") if p.is_file()]


def _is_supported_file(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, SKIP_REASON_NOT_FILE

    if path.name.startswith("~$"):
        return False, SKIP_REASON_TEMP_FILE

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return False, SKIP_REASON_UNSUPPORTED_EXT

    try:
        if path.stat().st_size <= 0:
            return False, SKIP_REASON_EMPTY_FILE
        with path.open("rb") as handle:
            handle.read(1)
    except OSError:
        return False, SKIP_REASON_NOT_READABLE

    return True, ""


def _build_document_item(path: Path) -> dict[str, Any]:
    file_stat = path.stat()
    modified_at = datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.utc).astimezone()

    return {
        "doc_id": _make_doc_id(path, file_stat.st_size, file_stat.st_mtime_ns),
        "source": "local_dir",
        "file_path": str(path.resolve()),
        "file_name": path.name,
        "ext": path.suffix.lower(),
        "size_bytes": file_stat.st_size,
        "modified_at": modified_at.isoformat(timespec="seconds"),
        "message_id": None,
        "job_id": None,
    }


def _make_doc_id(path: Path, size_bytes: int, mtime_ns: int) -> str:
    raw = f"{path.resolve()}|{size_bytes}|{mtime_ns}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _count_skip_reason(report: dict[str, Any], reason: str) -> None:
    skip_reasons = report.setdefault("skip_reasons", {})
    skip_reasons[reason] = int(skip_reasons.get(reason, 0)) + 1
