from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .bitable_attachment_uploader import (
        build_attachment_field_value,
        build_bitable_attachment_upload_request,
        load_user_access_token,
        perform_bitable_attachment_upload,
    )
    from .bitable_session_writer import choose_bitable_write_action
    from .main import DEFAULT_CONFIG_PATH, load_app_config, run_pipeline
    from .sync_bitable import sync_skill_result_with_config
except ImportError:  # pragma: no cover - supports running as a script.
    from bitable_attachment_uploader import (
        build_attachment_field_value,
        build_bitable_attachment_upload_request,
        load_user_access_token,
        perform_bitable_attachment_upload,
    )
    from bitable_session_writer import choose_bitable_write_action
    from main import DEFAULT_CONFIG_PATH, load_app_config, run_pipeline
    from sync_bitable import sync_skill_result_with_config


SUPPORTED_SKILL_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def run_skill_job(
    attachments: list[dict[str, Any]],
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run the finance pipeline from a skill-friendly attachment payload.

    Important:
    - This function completes recognition, formatting, and write-plan generation.
    - `bitable_write_plan` is only an intermediate artifact for downstream real-run.
    - When the current OpenClaw session has Feishu Bitable tools available,
      the caller must continue to execute real create/update instead of treating
      the returned plan as task completion.
    """
    config_file = config_path or DEFAULT_CONFIG_PATH
    config, project_root = load_app_config(config_file)
    workspace = create_job_workspace(config, project_root)
    saved_files = materialize_attachments(attachments, workspace["input_dir"])
    if not saved_files:
        raise ValueError("No supported attachments were provided to the skill job.")

    summary = run_pipeline_for_job(
        config=config,
        project_root=project_root,
        input_dir=workspace["input_dir"],
        output_dir=workspace["output_dir"],
    )
    result = load_skill_result(summary["output"]["run_dir"])
    result["job"] = {
        "job_id": workspace["job_id"],
        "job_dir": str(workspace["job_dir"]),
        "input_dir": str(workspace["input_dir"]),
        "output_dir": str(workspace["output_dir"]),
        "saved_files": [str(path) for path in saved_files],
    }
    result["bitable_sync"] = sync_skill_result_with_config(
        result,
        config,
        attachment_paths=[str(path) for path in saved_files],
    )
    result["bitable_write_plan"] = build_bitable_write_plan(
        result,
        attachment_paths=[str(path) for path in saved_files],
        app_token=_extract_bitable_app_token(config),
        config=config,
    )
    return result


def create_job_workspace(
    config: dict[str, Any],
    project_root: Path,
    job_id: str | None = None,
) -> dict[str, Path | str]:
    """Create an isolated job workspace under runtime/jobs."""
    runtime_root_value = config.get("paths", {}).get("runtime_dir")
    runtime_root = Path(str(runtime_root_value)) if runtime_root_value else project_root / "runtime"
    jobs_root = runtime_root / "jobs"
    resolved_job_id = job_id or _make_job_id()
    job_dir = jobs_root / resolved_job_id
    input_dir = job_dir / "inbox"
    output_dir = job_dir / "output"

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    return {
        "job_id": resolved_job_id,
        "job_dir": job_dir,
        "input_dir": input_dir,
        "output_dir": output_dir,
    }


def materialize_attachments(
    attachments: list[dict[str, Any]],
    input_dir: str | Path,
) -> list[Path]:
    """Write supported attachments into the job inbox."""
    target_dir = Path(input_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []
    for attachment in attachments:
        file_name = _normalize_attachment_name(attachment)
        if not file_name:
            continue

        extension = Path(file_name).suffix.lower()
        if extension not in SUPPORTED_SKILL_EXTENSIONS:
            continue

        payload = _read_attachment_bytes(attachment)
        if payload is None:
            continue

        target_path = _resolve_unique_path(target_dir / file_name)
        target_path.write_bytes(payload)
        saved_paths.append(target_path)

    return saved_paths


def run_pipeline_for_job(
    *,
    config: dict[str, Any],
    project_root: Path,
    input_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Run the shared pipeline against a prepared job workspace."""
    job_config = copy.deepcopy(config)
    job_config.setdefault("paths", {})
    job_config["paths"]["input_dir"] = str(Path(input_dir))
    job_config["paths"]["output_dir"] = str(Path(output_dir))
    return run_pipeline(job_config, project_root)


def load_skill_result(run_dir: str | Path) -> dict[str, Any]:
    """Load the formatted skill result for a completed run."""
    run_path = Path(run_dir)
    skill_result_path = run_path / "skill_result.json"
    return _read_json(skill_result_path)


def build_bitable_write_plan(
    skill_result: dict[str, Any],
    *,
    attachment_paths: list[str] | None = None,
    app_token: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a user-identity write plan for the current OpenClaw session.

    The returned plan is intentionally not the final completion state.
    Real completion requires the caller/session layer to continue with Feishu
    Bitable create/update and confirm the write result.
    """
    try:
        from .sync_bitable import (
            TRANSPORTATION_TYPES,
            build_expense_record,
            build_transport_record,
        )
    except ImportError:  # pragma: no cover - supports running as a script.
        from sync_bitable import (  # type: ignore
            TRANSPORTATION_TYPES,
            build_expense_record,
            build_transport_record,
        )

    documents = skill_result.get("documents", [])
    bitable_config = (config or {}).get("sync", {}).get("bitable", {}) if isinstance(config, dict) else {}
    token_file = bitable_config.get("user_token_file") or "runtime/oauth/feishu_user_token.json"
    access_token = None
    try:
        if app_token and attachment_paths:
            access_token = load_user_access_token(token_file)
    except Exception:
        access_token = None
    attachment_request = build_bitable_attachment_upload_request(
        app_token=app_token or "",
        attachment_paths=attachment_paths,
        access_token=access_token,
        endpoint=str(bitable_config.get("endpoint") or "https://open.feishu.cn"),
    )
    attachment_upload_result = None
    attachment_field_value: list[dict[str, str]] = []
    if attachment_request and access_token:
        try:
            attachment_upload_result = perform_bitable_attachment_upload(attachment_request)
            attachment_field_value = build_attachment_field_value(attachment_upload_result.file_tokens)
        except Exception as exc:
            attachment_upload_result = {
                "ok": False,
                "status": "failed",
                "provider": attachment_request.provider,
                "file_tokens": [],
                "uploaded": [],
                "errors": [{"code": "attachment_upload_failed", "message": str(exc)}],
                "message": str(exc),
            }
    transport_table_id = _extract_bitable_table_id(bitable_config, "transport_table_id")
    expense_table_id = _extract_bitable_table_id(bitable_config, "expense_table_id")

    plan = {
        "mode": "user_identity",
        "include_attachments": False,
        "write_policy": {
            "preferred": "update_first_blank_row_then_create",
            "blank_row_rule": "reuse first record whose doc_id is empty; create only when none found",
        },
        "attachment_strategy": "upload_to_bitable_context_first",
        "attachment_upload_handoff": {
            "required": bool(attachment_request),
            "supported_by_current_project": bool(attachment_request and access_token),
            "status": (
                "ready_with_user_identity"
                if attachment_request and access_token
                else "missing_user_access_token"
                if attachment_request
                else "not_needed"
            ),
            "reason": "Bitable attachment fields reject generic Drive uploads; upload must use user identity and current bitable context before writing file_token.",
            "recommended_tool": "project_builtin_user_identity_uploader",
            "recommended_params": {
                "parent_type": "bitable_image"
            }
        },
        "records": [],
    }
    for document in documents:
        if not isinstance(document, dict):
            continue
        document_type = str(document.get("document_type") or "unknown")
        if document_type in TRANSPORTATION_TYPES:
            plan["records"].append(
                {
                    "target": "transport",
                    "table_id": transport_table_id,
                    "fields": build_transport_record(document, attachment_field_value),
                    "write_action": choose_bitable_write_action([]),
                }
            )
        else:
            plan["records"].append(
                {
                    "target": "expense",
                    "table_id": expense_table_id,
                    "fields": build_expense_record(document, attachment_field_value),
                    "write_action": choose_bitable_write_action([]),
                }
            )
    if attachment_paths:
        plan["attachment_paths"] = list(attachment_paths)
        plan["attachment_upload_handoff"]["attachment_paths"] = list(attachment_paths)
    if attachment_request:
        plan["attachment_upload_handoff"]["request"] = {
            "app_token": attachment_request.app_token,
            "attachment_paths": list(attachment_request.attachment_paths),
            "provider": attachment_request.provider,
            "has_access_token": bool(attachment_request.access_token),
        }
    if attachment_upload_result is not None:
        if hasattr(attachment_upload_result, "__dict__"):
            plan["attachment_upload_result"] = dict(attachment_upload_result.__dict__)
        else:
            plan["attachment_upload_result"] = attachment_upload_result
    return plan


def _extract_bitable_app_token(config: dict[str, Any]) -> str | None:
    bitable = config.get("sync", {}).get("bitable", {}) if isinstance(config, dict) else {}
    raw = bitable.get("app_token")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    env_key = bitable.get("app_token_env")
    if isinstance(env_key, str) and env_key.strip():
        import os
        return os.environ.get(env_key.strip())
    return None


def _extract_bitable_table_id(bitable_config: dict[str, Any], key: str) -> str | None:
    raw = bitable_config.get(key)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    env_key = bitable_config.get(f"{key}_env")
    if isinstance(env_key, str) and env_key.strip():
        import os
        value = os.environ.get(env_key.strip(), "").strip()
        return value or None
    return None


def _make_job_id() -> str:
    return datetime.now(timezone.utc).strftime("job_%Y%m%d_%H%M%S_%f")


def _normalize_attachment_name(attachment: dict[str, Any]) -> str | None:
    raw_name = str(attachment.get("file_name") or "").strip()
    if not raw_name:
        return None
    return Path(raw_name).name


def _read_attachment_bytes(attachment: dict[str, Any]) -> bytes | None:
    if isinstance(attachment.get("content_bytes"), bytes):
        return attachment["content_bytes"]

    source_path = attachment.get("source_path")
    if source_path:
        return Path(str(source_path)).read_bytes()

    return None


def _resolve_unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _read_json(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))
