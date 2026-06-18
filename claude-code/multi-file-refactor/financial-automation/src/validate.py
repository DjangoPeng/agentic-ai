from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml


DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"


def load_rules(config: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    """Load validation rules from config or fallback to the default rules file."""
    configured_path = None
    if isinstance(config, dict):
        configured_path = config.get("validate", {}).get("rules_file")

    rules_path = Path(str(configured_path)).expanduser() if configured_path else DEFAULT_RULES_PATH
    rules_file = rules_path.resolve()
    with rules_file.open("r", encoding="utf-8") as handle:
        rules = yaml.safe_load(handle) or {}
    return rules, rules_file


def validate_documents(
    extracted_items: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate extracted items against configured finance rules."""
    rules, rules_file = load_rules(config)
    severity_map = rules.get("compliance", {}).get("severity_map", {})
    expense_type_rules = rules.get("expense_type_rules", {})
    minimum_confidence = float(rules.get("confidence", {}).get("minimum_confidence", 0.75))
    review_policy = rules.get("review_policy", {})
    low_confidence_requires_review = bool(
        rules.get("confidence", {}).get("low_confidence_requires_review", True)
    )
    consistency = rules.get("consistency", {})

    duplicate_index = _build_duplicate_index(extracted_items, rules)
    validated_items: list[dict[str, Any]] = []
    counts = {"pass": 0, "warning": 0, "error": 0}
    review_docs = 0
    results: list[dict[str, Any]] = []

    for item in extracted_items:
        findings = _validate_single_item(
            item=item,
            rules=rules,
            expense_type_rules=expense_type_rules,
            severity_map=severity_map,
            minimum_confidence=minimum_confidence,
            duplicate_index=duplicate_index,
            consistency=consistency,
        )
        compliance_status = _derive_compliance_status(findings)
        validation_review_reasons = _derive_validation_review_reasons(
            item=item,
            findings=findings,
            review_policy=review_policy,
            low_confidence_requires_review=low_confidence_requires_review,
        )

        merged_item = copy.deepcopy(item)
        merged_item["compliance_status"] = compliance_status
        merged_item["validation_findings"] = findings
        merged_item["validation_review_reasons"] = validation_review_reasons
        merged_item["needs_review"] = bool(item.get("needs_review")) or bool(validation_review_reasons)
        merged_item["review_reasons"] = sorted(
            set(item.get("review_reasons", [])) | set(validation_review_reasons)
        )

        validated_items.append(merged_item)
        counts[compliance_status] += 1
        if merged_item["needs_review"]:
            review_docs += 1

        results.append(
            {
                "doc_id": merged_item.get("doc_id"),
                "source_file_name": merged_item.get("source_file_name"),
                "invoice_type": merged_item.get("invoice_type"),
                "compliance_status": compliance_status,
                "needs_review": merged_item["needs_review"],
                "review_reasons": merged_item["review_reasons"],
                "findings": findings,
            }
        )

    report = {
        "status": "completed",
        "rules_file": str(rules_file),
        "schema_version": rules.get("schema_version"),
        "total_docs": len(validated_items),
        "pass_docs": counts["pass"],
        "warning_docs": counts["warning"],
        "error_docs": counts["error"],
        "review_docs": review_docs,
        "results": results,
    }
    return validated_items, report


def _validate_single_item(
    item: dict[str, Any],
    rules: dict[str, Any],
    expense_type_rules: dict[str, Any],
    severity_map: dict[str, str],
    minimum_confidence: float,
    duplicate_index: dict[str, int],
    consistency: dict[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    invoice_type = str(item.get("invoice_type") or "unknown")
    type_rules = expense_type_rules.get(invoice_type) or expense_type_rules.get("unknown", {})

    for field_name in rules.get("required_fields", []):
        if not _is_field_present(item, field_name):
            findings.append(
                _make_finding(
                    code="missing_required_field",
                    severity=severity_map.get("missing_required_field", "error"),
                    message=f"Missing required field: {field_name}",
                    field=field_name,
                )
            )

    for field_name in type_rules.get("required_fields", []):
        if not _is_field_present(item, field_name):
            findings.append(
                _make_finding(
                    code="missing_required_field",
                    severity=severity_map.get("missing_required_field", "error"),
                    message=f"Missing expense-type field: {field_name}",
                    field=field_name,
                )
            )

    if invoice_type == "unknown":
        findings.append(
            _make_finding(
                code="unknown_expense_type",
                severity=severity_map.get("unknown_expense_type", "warning"),
                message="Expense type could not be determined.",
            )
        )

    amount = item.get("amount")
    max_amount = type_rules.get("max_amount")
    if isinstance(amount, (int, float)) and isinstance(max_amount, (int, float)):
        if float(amount) > float(max_amount):
            findings.append(
                _make_finding(
                    code="amount_exceeds_limit",
                    severity=severity_map.get("amount_exceeds_limit", "warning"),
                    message=f"Amount {amount} exceeds configured limit {max_amount}.",
                    field="amount",
                )
            )

    findings.extend(
        _validate_consistency(
            item=item,
            severity_map=severity_map,
            consistency=consistency,
        )
    )

    confidence = item.get("extraction_confidence")
    if isinstance(confidence, (int, float)) and float(confidence) < minimum_confidence:
        findings.append(
            _make_finding(
                code="low_confidence",
                severity=severity_map.get("low_confidence", "warning"),
                message=f"Extraction confidence {confidence} is below threshold {minimum_confidence}.",
            )
        )

    dedup_key = _build_dedup_key(item, rules)
    if dedup_key and duplicate_index.get(dedup_key, 0) > 1:
        findings.append(
            _make_finding(
                code="duplicate_invoice_number",
                severity=severity_map.get("duplicate_invoice_number", "error"),
                message="Potential duplicate document detected within the batch.",
            )
        )

    return findings


def _validate_consistency(
    item: dict[str, Any],
    severity_map: dict[str, str],
    consistency: dict[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    tolerance = float(consistency.get("amount_tolerance", 0.05))

    if bool(consistency.get("check_line_items", True)):
        quantity = _as_float(item.get("quantity"))
        unit_price = _as_float(item.get("unit_price"))
        line_amount = _as_float(item.get("line_amount"))
        if quantity is not None and unit_price is not None and line_amount is not None:
            expected_line_amount = quantity * unit_price
            if abs(expected_line_amount - line_amount) > tolerance:
                findings.append(
                    _make_finding(
                        code="line_item_mismatch",
                        severity=severity_map.get("line_item_mismatch", "warning"),
                        message=(
                            f"Quantity * unit_price mismatch: expected about "
                            f"{expected_line_amount:.2f}, got {line_amount:.2f}."
                        ),
                        field="line_amount",
                        expected=round(expected_line_amount, 2),
                        actual=round(line_amount, 2),
                    )
                )

    if bool(consistency.get("check_invoice_total", True)):
        amount = _as_float(item.get("amount"))
        line_amount_total = _sum_line_item_field(item, "line_amount")
        tax_amount_total = _sum_line_item_field(item, "tax_amount")

        if amount is not None and line_amount_total is not None and tax_amount_total is not None:
            expected_total = line_amount_total + tax_amount_total
            if abs(expected_total - amount) > tolerance:
                findings.append(
                    _make_finding(
                        code="invoice_total_mismatch",
                        severity=severity_map.get("invoice_total_mismatch", "warning"),
                        message=(
                            f"line_amount + tax_amount mismatch: expected about "
                            f"{expected_total:.2f}, got {amount:.2f}."
                        ),
                        field="amount",
                        expected=round(expected_total, 2),
                        actual=round(amount, 2),
                    )
                )

    return findings


def _sum_line_item_field(item: dict[str, Any], field_name: str) -> float | None:
    line_items = item.get("line_items")
    if isinstance(line_items, list) and line_items:
        values = [_as_float(line.get(field_name)) for line in line_items if isinstance(line, dict)]
        numeric_values = [value for value in values if value is not None]
        if numeric_values:
            return float(sum(numeric_values))

    return _as_float(item.get(field_name))


def _derive_compliance_status(findings: list[dict[str, Any]]) -> str:
    severities = {finding.get("severity") for finding in findings}
    if "error" in severities:
        return "error"
    if "warning" in severities:
        return "warning"
    return "pass"


def _derive_validation_review_reasons(
    item: dict[str, Any],
    findings: list[dict[str, Any]],
    review_policy: dict[str, Any],
    low_confidence_requires_review: bool,
) -> list[str]:
    reasons: list[str] = []
    finding_codes = {finding.get("code") for finding in findings}

    if item.get("ocr_source") == "image_ocr" and review_policy.get("image_ocr_requires_review", False):
        reasons.append("image_ocr_requires_review")
    if "missing_required_field" in finding_codes and review_policy.get("missing_required_field_requires_review", False):
        reasons.append("validation_missing_required_field")
    if "amount_exceeds_limit" in finding_codes and review_policy.get("amount_exceeds_limit_requires_review", False):
        reasons.append("validation_amount_exceeds_limit")
    if "duplicate_invoice_number" in finding_codes and review_policy.get("duplicate_invoice_requires_review", False):
        reasons.append("validation_duplicate_invoice")
    if "low_confidence" in finding_codes and low_confidence_requires_review:
        reasons.append("validation_low_confidence")
    if (
        {"line_item_mismatch", "invoice_total_mismatch"} & finding_codes
        and review_policy.get("consistency_requires_review", False)
    ):
        reasons.append("validation_consistency_check_failed")

    return reasons


def _make_finding(
    code: str,
    severity: str,
    message: str,
    field: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    finding = {
        "code": code,
        "severity": severity,
        "message": message,
    }
    if field:
        finding["field"] = field
    finding.update(extra)
    return finding


def _is_field_present(item: dict[str, Any], field_name: str) -> bool:
    value = item.get(field_name)
    if field_name in {
        "amount",
        "quantity",
        "unit_price",
        "line_amount",
        "tax_amount",
    }:
        return isinstance(value, (int, float))
    return value is not None and str(value).strip() != ""


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _build_duplicate_index(items: list[dict[str, Any]], rules: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = _build_dedup_key(item, rules)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def _build_dedup_key(item: dict[str, Any], rules: dict[str, Any]) -> str | None:
    dedup_conf = rules.get("dedup", {})
    strategy = str(dedup_conf.get("strategy", "invoice_number_first"))
    invoice_number = str(item.get("invoice_number") or "").strip()

    if strategy == "invoice_number_first" and invoice_number:
        return f"invoice_number:{invoice_number}"

    fallback_fields = dedup_conf.get(
        "fallback_fields",
        ["issue_date", "amount", "vendor", "source_file_name"],
    )
    values = [str(item.get(field) or "").strip() for field in fallback_fields]
    if not any(values):
        return None
    return f"fallback:{json.dumps(values, ensure_ascii=True)}"
