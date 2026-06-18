from __future__ import annotations

import argparse
import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from .ingest import load_input_documents
    from .ocr_extract import extract_documents
    from .output_formatter import (
        format_skill_documents,
        format_skill_review_queue,
        format_skill_run_result,
    )
    from .validate import validate_documents
except ImportError:  # pragma: no cover - supports running as a script.
    from ingest import load_input_documents
    from ocr_extract import extract_documents
    from output_formatter import (
        format_skill_documents,
        format_skill_review_queue,
        format_skill_run_result,
    )
    from validate import validate_documents


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "app_config.yaml"


PATH_FIELDS = (
    ("paths", "input_dir"),
    ("paths", "output_dir"),
    ("paths", "runtime_dir"),
    ("ocr", "rapidocr", "model_root_dir"),
    ("validate", "rules_file"),
)


def resolve_path(value: str | Path | None, project_root: Path) -> str | None:
    """Resolve a path-like config value against the project root."""
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return raw

    path_obj = Path(raw).expanduser()
    if path_obj.is_absolute():
        return str(path_obj)
    return str((project_root / path_obj).resolve())


def _get_nested(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _set_nested(mapping: dict[str, Any], keys: tuple[str, ...], value: Any) -> None:
    current: Any = mapping
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def detect_project_root(config_path: Path) -> Path:
    """Pick project root with environment override support."""
    override = os.getenv("OPENCLAW_PROJECT_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return config_path.parent.parent.resolve()


def load_app_config(config_path: str | Path) -> tuple[dict[str, Any], Path]:
    """Load app config and normalize all path-like fields."""
    config_file = Path(config_path).expanduser().resolve()
    with config_file.open("r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file) or {}

    resolved_config = copy.deepcopy(raw_config)
    project_root = detect_project_root(config_file)

    for key_path in PATH_FIELDS:
        current_value = _get_nested(resolved_config, key_path)
        if current_value is None:
            continue
        _set_nested(resolved_config, key_path, resolve_path(current_value, project_root))

    return resolved_config, project_root


def _now_local() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def _make_run_id(now: datetime) -> str:
    return now.strftime("%Y%m%d_%H%M%S")


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_pipeline(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    started_at = _now_local()
    run_id = _make_run_id(started_at)

    output_root = Path(str(config.get("paths", {}).get("output_dir", project_root / "runtime" / "output")))
    run_dir = _ensure_dir(output_root / run_id)
    extracted_dir = _ensure_dir(run_dir / "extracted_json")
    skill_dir = _ensure_dir(run_dir / "skill_json")

    documents, ingest_report = load_input_documents(config)
    extracted_items, extract_report = extract_documents(documents, config)
    validated_items, compliance_report = validate_documents(extracted_items, config)
    skill_documents = format_skill_documents(validated_items)
    skill_review_queue = format_skill_review_queue(validated_items)

    for item in validated_items:
        item_doc_id = str(item.get("doc_id") or "unknown")
        _write_json(extracted_dir / f"{item_doc_id}.json", item)

    for skill_item in skill_documents:
        skill_doc_id = str(skill_item.get("doc_id") or "unknown")
        _write_json(skill_dir / f"{skill_doc_id}.json", skill_item)

    review_queue = [
        {
            "doc_id": item.get("doc_id"),
            "source_file_name": item.get("source_file_name"),
            "needs_review": item.get("needs_review"),
            "review_reasons": item.get("review_reasons", []),
            "ocr_status": item.get("ocr_status"),
            "error": item.get("error"),
            "extraction_confidence": item.get("extraction_confidence"),
            "compliance_status": item.get("compliance_status"),
            "validation_findings": item.get("validation_findings", []),
        }
        for item in validated_items
        if item.get("needs_review")
    ]

    completed_at = _now_local()
    counts = {
        "documents_seen": ingest_report.get("total_seen", 0),
        "documents_accepted": ingest_report.get("accepted", 0),
        "documents_extracted": len(validated_items),
        "documents_for_review": len(review_queue),
        "documents_failed": extract_report.get("failed_docs", 0),
        "documents_pass": compliance_report.get("pass_docs", 0),
        "documents_warning": compliance_report.get("warning_docs", 0),
        "documents_error": compliance_report.get("error_docs", 0),
    }
    skill_result = format_skill_run_result(
        app_name=str(config.get("app", {}).get("name", "financial-automation")),
        run_id=run_id,
        input_dir=config.get("paths", {}).get("input_dir"),
        output_dir=str(run_dir),
        documents=skill_documents,
        review_queue=skill_review_queue,
        counts=counts,
    )
    summary: dict[str, Any] = {
        "app": str(config.get("app", {}).get("name", "financial-automation")),
        "run_id": run_id,
        "project_root": str(project_root),
        "started_at": started_at.isoformat(timespec="seconds"),
        "completed_at": completed_at.isoformat(timespec="seconds"),
        "duration_seconds": round((completed_at - started_at).total_seconds(), 3),
        "input": {
            "input_dir": config.get("paths", {}).get("input_dir"),
        },
        "output": {
            "run_dir": str(run_dir),
            "extracted_json_dir": str(extracted_dir),
            "skill_json_dir": str(skill_dir),
            "skill_payload_file": str(run_dir / "skill_payload.json"),
            "skill_review_queue_file": str(run_dir / "skill_review_queue.json"),
            "skill_result_file": str(run_dir / "skill_result.json"),
            "review_queue_file": str(run_dir / "review_queue.json"),
            "compliance_report_file": str(run_dir / "compliance_report.json"),
            "run_summary_file": str(run_dir / "run_summary.json"),
        },
        "counts": counts,
        "ingest_report": ingest_report,
        "extract_report": extract_report,
        "compliance_report": {
            "status": compliance_report["status"],
            "rules_file": compliance_report.get("rules_file"),
            "pass_docs": compliance_report.get("pass_docs", 0),
            "warning_docs": compliance_report.get("warning_docs", 0),
            "error_docs": compliance_report.get("error_docs", 0),
            "review_docs": compliance_report.get("review_docs", 0),
        },
    }

    _write_json(run_dir / "skill_payload.json", skill_documents)
    _write_json(run_dir / "skill_review_queue.json", skill_review_queue)
    _write_json(run_dir / "skill_result.json", skill_result)
    _write_json(run_dir / "review_queue.json", review_queue)
    _write_json(run_dir / "compliance_report.json", compliance_report)
    _write_json(run_dir / "run_summary.json", summary)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Financial Automation entrypoint.")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to app configuration YAML.",
    )
    parser.add_argument(
        "--print-resolved-paths",
        action="store_true",
        help="Print resolved path fields for troubleshooting.",
    )
    args = parser.parse_args()

    config, project_root = load_app_config(args.config)

    if args.print_resolved_paths:
        payload = {
            "project_root": str(project_root),
            "resolved_paths": {
                ".".join(parts): _get_nested(config, parts) for parts in PATH_FIELDS
            },
        }
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    summary = run_pipeline(config, project_root)
    print(
        json.dumps(
            {
                "run_id": summary["run_id"],
                "run_dir": summary["output"]["run_dir"],
                "documents_accepted": summary["counts"]["documents_accepted"],
                "documents_extracted": summary["counts"]["documents_extracted"],
                "documents_for_review": summary["counts"]["documents_for_review"],
                "documents_failed": summary["counts"]["documents_failed"],
                "documents_warning": summary["counts"]["documents_warning"],
                "documents_error": summary["counts"]["documents_error"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
