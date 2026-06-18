from __future__ import annotations

from typing import Any


def format_skill_document(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a validated flat item into a skill-friendly document payload."""
    invoice_type = str(item.get("invoice_type") or "unknown")

    payload = {
        "doc_id": item.get("doc_id"),
        "document_type": invoice_type,
        "source_file_name": item.get("source_file_name"),
        "source_file_path": item.get("source_file_path"),
        "extraction": _build_extraction_payload(item, invoice_type),
        "validation": {
            "status": item.get("compliance_status"),
            "findings": item.get("validation_findings", []),
            "extraction_confidence": item.get("extraction_confidence"),
            "ocr_status": item.get("ocr_status"),
        },
        "review": {
            "needs_review": bool(item.get("needs_review")),
            "reasons": item.get("review_reasons", []),
        },
    }
    return payload


def format_skill_documents(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format a batch of validated items for skill output."""
    return [format_skill_document(item) for item in items]


def format_skill_review_queue(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format only the documents that require manual review."""
    queue: list[dict[str, Any]] = []
    for item in items:
        if not item.get("needs_review"):
            continue
        queue.append(
            {
                "doc_id": item.get("doc_id"),
                "document_type": item.get("invoice_type"),
                "source_file_name": item.get("source_file_name"),
                "review": {
                    "needs_review": True,
                    "reasons": item.get("review_reasons", []),
                },
                "validation": {
                    "status": item.get("compliance_status"),
                    "findings": item.get("validation_findings", []),
                },
                "summary": _build_review_summary(item),
            }
        )
    return queue


def format_skill_run_result(
    *,
    app_name: str,
    run_id: str,
    input_dir: str | None,
    output_dir: str,
    documents: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
    counts: dict[str, Any],
) -> dict[str, Any]:
    """Create a single batch payload suitable for a skill response."""
    user_summary = _build_user_summary(counts)
    review_highlights = [
        _build_review_highlight(item) for item in review_queue
    ]
    return {
        "app": app_name,
        "run_id": run_id,
        "status": "completed",
        "user_summary": user_summary,
        "summary": {
            "input_dir": input_dir,
            "output_dir": output_dir,
            "documents_seen": counts.get("documents_seen", 0),
            "documents_accepted": counts.get("documents_accepted", 0),
            "documents_extracted": counts.get("documents_extracted", 0),
            "documents_for_review": counts.get("documents_for_review", 0),
            "documents_pass": counts.get("documents_pass", 0),
            "documents_warning": counts.get("documents_warning", 0),
            "documents_error": counts.get("documents_error", 0),
        },
        "highlights": {
            "review_queue_count": len(review_queue),
            "review_items": review_highlights,
        },
        "documents": documents,
        "review_queue": review_queue,
    }


def _build_extraction_payload(item: dict[str, Any], invoice_type: str) -> dict[str, Any]:
    base_document = {
        "document": {
            "invoice_number": item.get("invoice_number"),
            "issue_date": item.get("issue_date"),
            "amount": item.get("amount"),
            "currency": item.get("currency"),
            "invoice_type": invoice_type,
        }
    }

    if invoice_type == "transportation_fee":
        base_document["buyer"] = {
            "name": item.get("buyer_name"),
            "tax_id": item.get("buyer_tax_id"),
        }
        base_document["travel"] = {
            "transport_number": item.get("transport_number"),
            "from_station": item.get("from_station"),
            "to_station": item.get("to_station"),
            "route": item.get("route"),
            "travel_date": item.get("travel_date"),
            "departure_time": item.get("departure_time"),
        }
        base_document["passenger"] = {
            "name": item.get("passenger_name"),
            "seat_no": item.get("seat_no"),
            "seat_class": item.get("seat_class"),
        }
        return base_document

    base_document["buyer"] = {
        "name": item.get("buyer_name"),
        "tax_id": item.get("buyer_tax_id"),
    }
    base_document["seller"] = {
        "name": item.get("vendor"),
        "tax_id": item.get("vendor_tax_id"),
    }
    base_document["line_items"] = item.get("line_items", [])
    return base_document


def _build_review_summary(item: dict[str, Any]) -> dict[str, Any]:
    invoice_type = str(item.get("invoice_type") or "unknown")
    document = {
        "invoice_number": item.get("invoice_number"),
        "issue_date": item.get("issue_date"),
        "amount": item.get("amount"),
        "invoice_type": invoice_type,
    }

    if invoice_type == "transportation_fee":
        return {
            "document": document,
            "buyer_name": item.get("buyer_name"),
            "transport_number": item.get("transport_number"),
            "route": item.get("route"),
            "travel_date": item.get("travel_date"),
            "passenger_name": item.get("passenger_name"),
        }

    return {
        "document": document,
        "buyer_name": item.get("buyer_name"),
        "seller_name": item.get("vendor"),
        "item_name": item.get("item_name"),
    }


def _build_user_summary(counts: dict[str, Any]) -> dict[str, Any]:
    documents_extracted = int(counts.get("documents_extracted", 0) or 0)
    documents_for_review = int(counts.get("documents_for_review", 0) or 0)
    documents_pass = int(counts.get("documents_pass", 0) or 0)
    documents_warning = int(counts.get("documents_warning", 0) or 0)
    documents_error = int(counts.get("documents_error", 0) or 0)

    if documents_extracted == 0:
        headline = "No documents were extracted."
    elif documents_error > 0:
        headline = (
            f"Processed {documents_extracted} documents: "
            f"{documents_error} error, {documents_warning} warning, "
            f"{documents_for_review} need review."
        )
    elif documents_warning > 0:
        headline = (
            f"Processed {documents_extracted} documents: "
            f"{documents_pass} passed, {documents_warning} warning, "
            f"{documents_for_review} need review."
        )
    else:
        headline = (
            f"Processed {documents_extracted} documents: "
            f"{documents_pass} passed, {documents_for_review} need review."
        )

    next_actions: list[str] = []
    if documents_for_review > 0:
        next_actions.append("Review the documents listed in review_queue.")
    if documents_error > 0:
        next_actions.append("Fix extraction or validation errors before auto-sync.")
    if not next_actions:
        next_actions.append("Documents are ready for downstream sync or approval.")

    return {
        "headline": headline,
        "next_actions": next_actions,
    }


def _build_review_highlight(item: dict[str, Any]) -> dict[str, Any]:
    summary = item.get("summary", {}) if isinstance(item, dict) else {}
    document = summary.get("document", {}) if isinstance(summary, dict) else {}
    return {
        "doc_id": item.get("doc_id"),
        "source_file_name": item.get("source_file_name"),
        "document_type": item.get("document_type"),
        "invoice_number": document.get("invoice_number"),
        "amount": document.get("amount"),
        "reasons": item.get("review", {}).get("reasons", []),
    }
