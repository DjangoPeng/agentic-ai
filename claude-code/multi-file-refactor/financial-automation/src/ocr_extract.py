from __future__ import annotations

import re
import statistics
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class OCRPayload:
    text: str
    confidence: float | None
    source: str
    error: str | None = None


REQUIRED_FIELDS = ("invoice_number", "issue_date", "amount", "invoice_type")
INVOICE_NUMBER_PATTERNS = (
    r"(?:发票号码|票据号码|电子客票号|No\.?)[:：]?\s*([0-9A-Za-z]{8,24})",
    r"(?:发票号|票号)[:：]?\s*([0-9A-Za-z]{8,24})",
)
ISSUE_DATE_PATTERNS = (
    r"(?:开票日期|日期|时间)[:：]?\s*([0-9]{4}\s*[-/.年]\s*[0-9]{1,2}\s*[-/.月]\s*[0-9]{1,2}\s*(?:日)?)",
    r"([0-9]{4}\s*[-/.年]\s*[0-9]{1,2}\s*[-/.月]\s*[0-9]{1,2}\s*(?:日)?)",
)
AMOUNT_PATTERNS = (
    r"(?:价税合计|合计金额|票价|金额|实付金额|支付金额|小写)[:：]?\s*[￥¥]?\s*([0-9]+(?:\.[0-9]{1,2})?)",
    r"[￥¥]\s*([0-9]+(?:\.[0-9]{1,2})?)",
)
INVOICE_TYPE_KEYWORDS = {
    "conference_fee": ("会议", "会务", "注册费", "培训费"),
    "accommodation_fee": ("住宿", "酒店", "房费", "客房"),
    "transportation_fee": ("机票", "车票", "火车", "高铁", "交通", "打车", "滴滴", "铁路", "电子客票"),
}
RAIL_TICKET_KEYWORDS = (
    "铁路电子客票",
    "电子客票",
    "车次",
    "购票方名称",
    "购买方名称",
    "统一社会信用代码",
)
BUYER_NAME_PATTERNS = (
    r"(?:购买方名称|购买方|购买方抬头)[:：]?\s*([^\n]+)",
    r"(?:购买方信息[\s\S]{0,120}?名称)[:：]?\s*([^\n]+)",
)
VENDOR_NAME_PATTERNS = (
    r"(?:销售方名称|销售方|收款方|商户)[:：]?\s*([^\n]+)",
    r"(?:销售方信息[\s\S]{0,120}?名称)[:：]?\s*([^\n]+)",
)
BUYER_TAX_ID_PATTERNS = (
    r"(?:购买方[\s\S]{0,200}?(?:统一社会信用代码|纳税人识别号)\s*/?\s*(?:纳税人识别号)?)[:：]?\s*([0-9A-Z]{15,20})",
    r"(?:购买方税号|购买方纳税人识别号)[:：]?\s*([0-9A-Z]{15,20})",
)
VENDOR_TAX_ID_PATTERNS = (
    r"(?:销售方[\s\S]{0,200}?(?:统一社会信用代码|纳税人识别号)\s*/?\s*(?:纳税人识别号)?)[:：]?\s*([0-9A-Z]{15,20})",
    r"(?:销售方税号|销售方纳税人识别号)[:：]?\s*([0-9A-Z]{15,20})",
)
RAIL_BUYER_NAME_PATTERNS = (
    r"(?:购票方名称|购买方名称)[:：]?\s*([^\n]+)",
    r"(?:购票方名称)[:：]?\s*([^\n]+?)\s+(?:统一社会信用代码|电子客票号|开票日期|$)",
)
RAIL_BUYER_TAX_ID_PATTERNS = (
    r"(?:统一社会信用代码)[:：]?\s*([0-9A-Z]{15,20})",
    r"(?:购票方[\s\S]{0,120}?统一社会信用代码)[:：]?\s*([0-9A-Z]{15,20})",
)
TRANSPORT_NUMBER_PATTERNS = (
    r"(?:车次|列车号|车票号)[:：]?\s*([A-Z]{1,2}\d{1,4})",
    r"\b([GDCZTKSYL]\d{1,4})\b",
)
DEPARTURE_TIME_PATTERNS = (
    r"(\d{1,2}:\d{2})开",
    r"(?:开车时间|发车时间)[:：]?\s*(\d{1,2}:\d{2})",
)
SEAT_NO_PATTERNS = (
    r"(\d{1,2}车\d{1,3}[A-Z]号)",
    r"(\d{1,2}车\d{1,3}[A-Z])",
)
SEAT_CLASS_PATTERNS = (
    r"(商务座|特等座|一等座|二等座|无座|软卧|硬卧|硬座|动卧)",
)
LINE_ITEM_EXPLICIT_PATTERN = re.compile(
    r"(?P<item>\*[^\n]+?\*\s*[^\d\n%￥¥]+?)\s+"
    r"(?P<quantity>\d+(?:\.\d+)?)\s+"
    r"(?P<unit_price>\d+\.\d+)\s+"
    r"(?P<line_amount>\d+\.\d{2})\s+"
    r"(?P<tax_rate>\d+(?:\.\d+)?%)\s+"
    r"(?P<tax_amount>\d+\.\d{2})"
)
LINE_ITEM_COLLAPSED_PATTERN = re.compile(
    r"(?P<item>\*[^\n]+?\*\s*[^\d\n%￥¥]+?)\s*"
    r"(?P<tax_rate>\d+(?:\.\d+)?%)\s*"
    r"(?P<line_amount>\d+\.\d{2})\s*"
    r"(?P<tax_amount>\d+\.\d{2})"
    r"(?P<unit_price>\d+(?:\.\d+)?)$"
)


def extract_documents(
    documents: list[dict[str, Any]],
    app_config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run OCR and field extraction for a normalized document list."""
    extract_conf = app_config.get("extract", {}) if isinstance(app_config, dict) else {}
    default_currency = str(extract_conf.get("default_currency", "CNY"))
    keep_raw_text = bool(extract_conf.get("keep_raw_text", True))

    items: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "total_docs": len(documents),
        "success_docs": 0,
        "failed_docs": 0,
        "review_docs": 0,
        "avg_confidence": 0.0,
        "error_reasons": {},
    }
    confidence_list: list[float] = []

    ocr_reader, init_error = _build_ocr_reader(app_config)
    for document in documents:
        item = _extract_single_document(
            document=document,
            ocr_reader=ocr_reader,
            ocr_init_error=init_error,
            default_currency=default_currency,
            keep_raw_text=keep_raw_text,
        )
        items.append(item)

        if item["ocr_status"] == "success":
            report["success_docs"] += 1
        else:
            report["failed_docs"] += 1
            _count_reason(report["error_reasons"], item.get("error") or "ocr_failed")

        if item["needs_review"]:
            report["review_docs"] += 1

        confidence_value = item.get("extraction_confidence")
        if isinstance(confidence_value, (int, float)):
            confidence_list.append(float(confidence_value))

    if confidence_list:
        report["avg_confidence"] = round(statistics.fmean(confidence_list), 4)
    return items, report


def parse_fields_from_text(text: str, default_currency: str = "CNY") -> dict[str, Any]:
    """Parse invoice fields from OCR text using lightweight regex and keyword rules."""
    normalized = _normalize_text(text)
    invoice_number, invoice_conf = _extract_invoice_number(normalized)
    issue_date, date_conf = _extract_issue_date(normalized)
    amount, amount_conf = _extract_amount(normalized)
    invoice_type, invoice_type_conf = _detect_invoice_type(normalized)

    parties = _extract_party_fields(normalized, invoice_type)
    transport = _extract_transport_fields(normalized, invoice_type)
    detail = _extract_invoice_detail_fields(normalized, invoice_type)
    field_confidence = {
        "invoice_number": invoice_conf,
        "issue_date": date_conf,
        "amount": amount_conf,
        "invoice_type": invoice_type_conf,
        "vendor": parties["vendor_conf"],
        "vendor_tax_id": parties["vendor_tax_id_conf"],
        "buyer_name": parties["buyer_name_conf"],
        "buyer_tax_id": parties["buyer_tax_id_conf"],
        "route": transport["route_conf"],
        "transport_number": transport["transport_number_conf"],
        "from_station": transport["from_station_conf"],
        "to_station": transport["to_station_conf"],
        "passenger_name": transport["passenger_name_conf"],
        "travel_date": transport["travel_date_conf"],
        "departure_time": transport["departure_time_conf"],
        "seat_no": transport["seat_no_conf"],
        "seat_class": transport["seat_class_conf"],
        "item_name": detail["item_name_conf"],
        "quantity": detail["quantity_conf"],
        "unit_price": detail["unit_price_conf"],
        "line_amount": detail["line_amount_conf"],
        "tax_rate": detail["tax_rate_conf"],
        "tax_amount": detail["tax_amount_conf"],
    }
    extraction_confidence = _calculate_extraction_confidence(field_confidence)

    extracted_values = {
        "invoice_number": invoice_number,
        "issue_date": issue_date,
        "amount": amount,
        "invoice_type": invoice_type,
    }
    review_reasons: list[str] = []
    for required in REQUIRED_FIELDS:
        if not _is_field_present(required, extracted_values):
            review_reasons.append(f"missing_{required}")
    if extraction_confidence < 0.75:
        review_reasons.append("low_extraction_confidence")
    if invoice_type == "unknown":
        review_reasons.append("unknown_expense_type")

    return {
        "invoice_number": invoice_number,
        "issue_date": issue_date,
        "amount": amount,
        "currency": default_currency,
        "invoice_type": invoice_type,
        "vendor": parties["vendor"],
        "vendor_tax_id": parties["vendor_tax_id"],
        "buyer_name": parties["buyer_name"],
        "buyer_tax_id": parties["buyer_tax_id"],
        "route": transport["route"],
        "transport_number": transport["transport_number"],
        "from_station": transport["from_station"],
        "to_station": transport["to_station"],
        "passenger_name": transport["passenger_name"],
        "travel_date": transport["travel_date"],
        "departure_time": transport["departure_time"],
        "seat_no": transport["seat_no"],
        "seat_class": transport["seat_class"],
        "item_name": detail["item_name"],
        "specification": detail["specification"],
        "unit": detail["unit"],
        "quantity": detail["quantity"],
        "unit_price": detail["unit_price"],
        "line_amount": detail["line_amount"],
        "tax_rate": detail["tax_rate"],
        "tax_amount": detail["tax_amount"],
        "line_items": detail["line_items"],
        "field_confidence": field_confidence,
        "extraction_confidence": extraction_confidence,
        "needs_review": len(review_reasons) > 0,
        "review_reasons": review_reasons,
    }


def _extract_single_document(
    document: dict[str, Any],
    ocr_reader: Any,
    ocr_init_error: str | None,
    default_currency: str,
    keep_raw_text: bool,
) -> dict[str, Any]:
    source_path = str(document.get("file_path", "")).strip()
    ext = str(document.get("ext", "")).lower().strip()
    if not ext:
        candidate_name = source_path or str(document.get("file_name", "")).strip()
        if candidate_name:
            ext = Path(candidate_name).suffix.lower()

    payload: OCRPayload
    if ocr_init_error:
        payload = OCRPayload(text="", confidence=None, source="rapidocr", error=ocr_init_error)
    elif not source_path:
        payload = OCRPayload("", None, "rapidocr", "missing_file_path")
    else:
        payload = _extract_text_for_document(Path(source_path), ext, ocr_reader)

    parsed = parse_fields_from_text(payload.text, default_currency=default_currency)
    review_reasons = list(parsed["review_reasons"])
    if payload.error:
        review_reasons.append("ocr_error")

    item: dict[str, Any] = {
        "doc_id": document.get("doc_id"),
        "source": document.get("source"),
        "source_file_name": document.get("file_name"),
        "source_file_path": source_path,
        "ocr_engine": "rapidocr",
        "ocr_source": payload.source,
        "ocr_status": "success" if not payload.error else "failed",
        "ocr_confidence": payload.confidence,
        "ocr_text_length": len(payload.text),
        "error": payload.error,
        "invoice_number": parsed["invoice_number"],
        "issue_date": parsed["issue_date"],
        "amount": parsed["amount"],
        "currency": parsed["currency"],
        "invoice_type": parsed["invoice_type"],
        "vendor": parsed["vendor"],
        "vendor_tax_id": parsed["vendor_tax_id"],
        "buyer_name": parsed["buyer_name"],
        "buyer_tax_id": parsed["buyer_tax_id"],
        "route": parsed["route"],
        "transport_number": parsed["transport_number"],
        "from_station": parsed["from_station"],
        "to_station": parsed["to_station"],
        "passenger_name": parsed["passenger_name"],
        "travel_date": parsed["travel_date"],
        "departure_time": parsed["departure_time"],
        "seat_no": parsed["seat_no"],
        "seat_class": parsed["seat_class"],
        "item_name": parsed["item_name"],
        "specification": parsed["specification"],
        "unit": parsed["unit"],
        "quantity": parsed["quantity"],
        "unit_price": parsed["unit_price"],
        "line_amount": parsed["line_amount"],
        "tax_rate": parsed["tax_rate"],
        "tax_amount": parsed["tax_amount"],
        "line_items": parsed["line_items"],
        "field_confidence": parsed["field_confidence"],
        "extraction_confidence": parsed["extraction_confidence"],
        "needs_review": parsed["needs_review"] or bool(payload.error),
        "review_reasons": sorted(set(review_reasons)),
    }
    if keep_raw_text:
        item["raw_text"] = payload.text
    return item


def _extract_text_for_document(path: Path, ext: str, ocr_reader: Any) -> OCRPayload:
    if not path.exists():
        return OCRPayload("", None, "rapidocr", f"file_not_found:{path}")

    if ext == ".pdf":
        pdf_text = _read_pdf_text(path)
        if pdf_text and not _looks_like_garbled_pdf_text(pdf_text):
            return OCRPayload(pdf_text, None, "pdf_text")
        return _ocr_pdf_pages(path, ocr_reader)

    if ext in {".jpg", ".jpeg", ".png"}:
        return _ocr_image(path, ocr_reader)

    return OCRPayload("", None, "rapidocr", f"unsupported_extension:{ext}")


def _build_ocr_reader(app_config: dict[str, Any]) -> tuple[Any, str | None]:
    ocr_conf = app_config.get("ocr", {}) if isinstance(app_config, dict) else {}
    engine = str(ocr_conf.get("engine", "rapidocr")).lower()
    if engine != "rapidocr":
        return None, f"unsupported_ocr_engine:{engine}"

    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception as exc:  # pragma: no cover - import depends on local runtime.
        return None, f"rapidocr_unavailable:{exc}"

    try:
        return RapidOCR(), None
    except Exception as exc:  # pragma: no cover - local runtime init.
        return None, f"rapidocr_init_failed:{exc}"


def _read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception:  # pragma: no cover - import depends on local runtime.
        return ""

    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""

    chunks: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            chunks.append(text.strip())
    return "\n".join(chunks).strip()


def _ocr_pdf_pages(path: Path, ocr_reader: Any) -> OCRPayload:
    if ocr_reader is None:
        return OCRPayload("", None, "rapidocr", "ocr_reader_not_initialized")

    try:
        import fitz
    except Exception as exc:  # pragma: no cover - import depends on local runtime.
        return OCRPayload("", None, "rapidocr", f"pymupdf_unavailable:{exc}")

    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        return OCRPayload("", None, "rapidocr", f"pdf_open_failed:{exc}")

    texts: list[str] = []
    scores: list[float] = []
    error: str | None = None
    for page in doc:
        tmp_path: Path | None = None
        try:
            pix = page.get_pixmap(alpha=False)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                tmp.write(pix.tobytes("png"))
            text, page_scores, run_error = _run_rapidocr(ocr_reader, str(tmp_path))
            if text.strip():
                texts.append(text)
            scores.extend(page_scores)
            if run_error and error is None:
                error = run_error
        finally:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    doc.close()
    all_text = "\n".join(part for part in texts if part.strip()).strip()
    if not all_text and error is None:
        error = "empty_ocr_text"
    return OCRPayload(all_text, _average(scores), "pdf_ocr", error)


def _ocr_image(path: Path, ocr_reader: Any) -> OCRPayload:
    if ocr_reader is None:
        return OCRPayload("", None, "rapidocr", "ocr_reader_not_initialized")
    text, scores, error = _run_rapidocr(ocr_reader, str(path))
    if not text.strip() and error is None:
        error = "empty_ocr_text"
    return OCRPayload(text.strip(), _average(scores), "image_ocr", error)


def _run_rapidocr(reader: Any, image_path: str) -> tuple[str, list[float], str | None]:
    try:
        result, _elapsed = reader(image_path)
    except Exception as exc:
        return "", [], f"rapidocr_failed:{exc}"

    if not result:
        return "", [], None

    lines: list[str] = []
    scores: list[float] = []
    for row in result:
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            continue
        text = str(row[1]).strip()
        try:
            score = float(row[2])
        except Exception:
            score = None
        if text:
            lines.append(text)
        if score is not None:
            scores.append(score)
    return "\n".join(lines).strip(), scores, None


def _normalize_text(text: str) -> str:
    compact = text.replace("\r", "\n")
    compact = re.sub(r"[ \t]+", " ", compact)
    compact = re.sub(r"\n{2,}", "\n", compact)
    return compact.strip()


def _looks_like_garbled_pdf_text(text: str) -> bool:
    """Detect common mojibake patterns from broken PDF text extraction."""
    sample = text.strip()
    if not sample:
        return False

    if sample.count("?") >= 3 or sample.count("\ufffd") >= 1:
        return True

    suspicious_markers = ("锛", "鏈", "鏃", "鐢", "闄", "鍙", "绁")
    suspicious_hits = sum(sample.count(marker) for marker in suspicious_markers)
    return suspicious_hits >= 6


def _extract_invoice_number(text: str) -> tuple[str | None, float]:
    for pattern in INVOICE_NUMBER_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1), 0.9

    generic = re.findall(r"\b[0-9]{10,20}\b", text)
    if generic:
        return generic[0], 0.7
    return None, 0.0


def _extract_issue_date(text: str) -> tuple[str | None, float]:
    for index, pattern in enumerate(ISSUE_DATE_PATTERNS):
        match = re.search(pattern, text)
        if not match:
            continue
        confidence = 0.9 if index == 0 else 0.75
        return _normalize_date_token(match.group(1)), confidence
    return None, 0.0


def _extract_amount(text: str) -> tuple[float | None, float]:
    for index, pattern in enumerate(AMOUNT_PATTERNS):
        matches = re.findall(pattern, text)
        if not matches:
            continue
        values = [float(raw) for raw in matches]
        confidence = 0.9 if index == 0 else 0.75
        return max(values), confidence
    return None, 0.0


def _detect_invoice_type(text: str) -> tuple[str, float]:
    for expense_type, keywords in INVOICE_TYPE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return expense_type, 0.8
    return "unknown", 0.4


def _extract_party_fields(text: str, invoice_type: str) -> dict[str, str | float | None]:
    if invoice_type == "transportation_fee" and _is_rail_ticket(text):
        return _extract_rail_ticket_parties(text)

    buyer_name, buyer_name_conf = _extract_named_value(text, BUYER_NAME_PATTERNS)
    vendor, vendor_conf = _extract_named_value(text, VENDOR_NAME_PATTERNS)
    buyer_tax_id, buyer_tax_id_conf = _extract_tax_id(text, BUYER_TAX_ID_PATTERNS)
    vendor_tax_id, vendor_tax_id_conf = _extract_tax_id(text, VENDOR_TAX_ID_PATTERNS)

    if all(value is not None for value in (buyer_name, buyer_tax_id, vendor, vendor_tax_id)):
        return {
            "buyer_name": buyer_name,
            "buyer_name_conf": buyer_name_conf,
            "buyer_tax_id": buyer_tax_id,
            "buyer_tax_id_conf": buyer_tax_id_conf,
            "vendor": vendor,
            "vendor_conf": vendor_conf,
            "vendor_tax_id": vendor_tax_id,
            "vendor_tax_id_conf": vendor_tax_id_conf,
        }

    fallback = _extract_parties_from_tax_id_pairs(text)
    return {
        "buyer_name": buyer_name or fallback["buyer_name"],
        "buyer_name_conf": buyer_name_conf if buyer_name else fallback["buyer_name_conf"],
        "buyer_tax_id": buyer_tax_id or fallback["buyer_tax_id"],
        "buyer_tax_id_conf": buyer_tax_id_conf if buyer_tax_id else fallback["buyer_tax_id_conf"],
        "vendor": vendor or fallback["vendor"],
        "vendor_conf": vendor_conf if vendor else fallback["vendor_conf"],
        "vendor_tax_id": vendor_tax_id or fallback["vendor_tax_id"],
        "vendor_tax_id_conf": vendor_tax_id_conf if vendor_tax_id else fallback["vendor_tax_id_conf"],
    }


def _extract_transport_fields(text: str, invoice_type: str) -> dict[str, str | float | None]:
    if invoice_type != "transportation_fee":
        return _empty_transport_fields()
    if _is_rail_ticket(text):
        return _extract_rail_ticket_transport(text)
    return _empty_transport_fields()


def _extract_invoice_detail_fields(text: str, invoice_type: str) -> dict[str, Any]:
    if invoice_type == "transportation_fee":
        return _empty_detail_fields()

    lines = _normalized_lines(text)
    candidates = [
        line
        for line in lines
        if "*" in line and "%" in line and re.search(r"\d+\.\d{2}", line)
    ]
    for candidate in reversed(candidates):
        parsed = _parse_line_item_candidate(candidate)
        if parsed:
            return parsed
    return _empty_detail_fields()


def _parse_line_item_candidate(candidate: str) -> dict[str, Any] | None:
    explicit_match = LINE_ITEM_EXPLICIT_PATTERN.search(candidate)
    if explicit_match:
        quantity = _to_float(explicit_match.group("quantity"))
        unit_price = _to_float(explicit_match.group("unit_price"))
        line_amount = _to_float(explicit_match.group("line_amount"))
        tax_amount = _to_float(explicit_match.group("tax_amount"))
        return _build_detail_result(
            item_name=_clean_item_name(explicit_match.group("item")),
            specification=None,
            unit=None,
            quantity=quantity,
            unit_price=unit_price,
            line_amount=line_amount,
            tax_rate=explicit_match.group("tax_rate"),
            tax_amount=tax_amount,
            confidence=0.9,
        )

    collapsed_match = LINE_ITEM_COLLAPSED_PATTERN.search(candidate)
    if not collapsed_match:
        return None

    unit_price = _to_float(collapsed_match.group("unit_price"))
    line_amount = _to_float(collapsed_match.group("line_amount"))
    tax_amount = _to_float(collapsed_match.group("tax_amount"))
    quantity = _infer_quantity(line_amount, unit_price)
    return _build_detail_result(
        item_name=_clean_item_name(collapsed_match.group("item")),
        specification=None,
        unit=None,
        quantity=quantity,
        unit_price=unit_price,
        line_amount=line_amount,
        tax_rate=collapsed_match.group("tax_rate"),
        tax_amount=tax_amount,
        confidence=0.82,
    )


def _build_detail_result(
    item_name: str | None,
    specification: str | None,
    unit: str | None,
    quantity: float | int | None,
    unit_price: float | None,
    line_amount: float | None,
    tax_rate: str | None,
    tax_amount: float | None,
    confidence: float,
) -> dict[str, Any]:
    line_item = {
        "item_name": item_name,
        "specification": specification,
        "unit": unit,
        "quantity": quantity,
        "unit_price": unit_price,
        "line_amount": line_amount,
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
    }
    return {
        "item_name": item_name,
        "item_name_conf": confidence if item_name else 0.0,
        "specification": specification,
        "unit": unit,
        "quantity": quantity,
        "quantity_conf": confidence if quantity is not None else 0.0,
        "unit_price": unit_price,
        "unit_price_conf": confidence if unit_price is not None else 0.0,
        "line_amount": line_amount,
        "line_amount_conf": confidence if line_amount is not None else 0.0,
        "tax_rate": tax_rate,
        "tax_rate_conf": confidence if tax_rate else 0.0,
        "tax_amount": tax_amount,
        "tax_amount_conf": confidence if tax_amount is not None else 0.0,
        "line_items": [line_item],
    }


def _empty_detail_fields() -> dict[str, Any]:
    return {
        "item_name": None,
        "item_name_conf": 0.0,
        "specification": None,
        "unit": None,
        "quantity": None,
        "quantity_conf": 0.0,
        "unit_price": None,
        "unit_price_conf": 0.0,
        "line_amount": None,
        "line_amount_conf": 0.0,
        "tax_rate": None,
        "tax_rate_conf": 0.0,
        "tax_amount": None,
        "tax_amount_conf": 0.0,
        "line_items": [],
    }


def _infer_quantity(line_amount: float | None, unit_price: float | None) -> int | None:
    if line_amount is None or unit_price is None or unit_price <= 0:
        return None

    estimated = line_amount / unit_price
    rounded = int(round(estimated))
    if rounded <= 0:
        return None
    if abs((unit_price * rounded) - line_amount) <= 0.05:
        return rounded
    return None


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _clean_item_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned


def _is_rail_ticket(text: str) -> bool:
    return any(keyword in text for keyword in RAIL_TICKET_KEYWORDS)


def _empty_transport_fields() -> dict[str, str | float | None]:
    return {
        "route": None,
        "route_conf": 0.0,
        "transport_number": None,
        "transport_number_conf": 0.0,
        "from_station": None,
        "from_station_conf": 0.0,
        "to_station": None,
        "to_station_conf": 0.0,
        "passenger_name": None,
        "passenger_name_conf": 0.0,
        "travel_date": None,
        "travel_date_conf": 0.0,
        "departure_time": None,
        "departure_time_conf": 0.0,
        "seat_no": None,
        "seat_no_conf": 0.0,
        "seat_class": None,
        "seat_class_conf": 0.0,
    }


def _extract_rail_ticket_parties(text: str) -> dict[str, str | float | None]:
    buyer_name, buyer_name_conf = _extract_named_value(text, RAIL_BUYER_NAME_PATTERNS)
    buyer_tax_id, buyer_tax_id_conf = _extract_tax_id(text, RAIL_BUYER_TAX_ID_PATTERNS)

    return {
        "buyer_name": buyer_name,
        "buyer_name_conf": buyer_name_conf,
        "buyer_tax_id": buyer_tax_id,
        "buyer_tax_id_conf": buyer_tax_id_conf,
        "vendor": None,
        "vendor_conf": 0.0,
        "vendor_tax_id": None,
        "vendor_tax_id_conf": 0.0,
    }


def _extract_rail_ticket_transport(text: str) -> dict[str, str | float | None]:
    lines = _normalized_lines(text)
    transport_number, transport_number_conf = _extract_transport_number(text)
    from_station, to_station, station_conf = _extract_station_pair_from_lines(lines, transport_number)
    route = f"{from_station}->{to_station}" if from_station and to_station else None
    travel_date, travel_date_conf = _extract_travel_date(text)
    departure_time, departure_time_conf = _extract_departure_time(text)
    seat_no, seat_no_conf = _extract_seat_no(text)
    seat_class, seat_class_conf = _extract_seat_class(text)
    passenger_name, passenger_name_conf = _extract_passenger_name(lines)

    return {
        "route": route,
        "route_conf": station_conf if route else 0.0,
        "transport_number": transport_number,
        "transport_number_conf": transport_number_conf,
        "from_station": from_station,
        "from_station_conf": station_conf if from_station else 0.0,
        "to_station": to_station,
        "to_station_conf": station_conf if to_station else 0.0,
        "passenger_name": passenger_name,
        "passenger_name_conf": passenger_name_conf,
        "travel_date": travel_date,
        "travel_date_conf": travel_date_conf,
        "departure_time": departure_time,
        "departure_time_conf": departure_time_conf,
        "seat_no": seat_no,
        "seat_no_conf": seat_no_conf,
        "seat_class": seat_class,
        "seat_class_conf": seat_class_conf,
    }


def _extract_transport_number(text: str) -> tuple[str | None, float]:
    for pattern in TRANSPORT_NUMBER_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).upper()
        return value, 0.9
    return None, 0.0


def _extract_station_pair_from_lines(
    lines: list[str],
    transport_number: str | None,
) -> tuple[str | None, str | None, float]:
    if not lines:
        return None, None, 0.0

    if transport_number:
        for index, line in enumerate(lines):
            if transport_number == line.upper():
                start = _find_adjacent_station(lines, index, step=-1)
                end = _find_adjacent_station(lines, index, step=1)
                if start and end:
                    return start, end, 0.9

    stations = [line for line in lines if _looks_like_station_name(line)]
    if len(stations) >= 2:
        return stations[0], stations[1], 0.75
    return None, None, 0.0


def _extract_travel_date(text: str) -> tuple[str | None, float]:
    dates = []
    for pattern in ISSUE_DATE_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            normalized = _normalize_date_token(match)
            if normalized not in dates:
                dates.append(normalized)

    if len(dates) >= 2:
        return dates[1], 0.9
    if len(dates) == 1:
        return dates[0], 0.6
    return None, 0.0


def _extract_departure_time(text: str) -> tuple[str | None, float]:
    for pattern in DEPARTURE_TIME_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1), 0.9
    return None, 0.0


def _extract_seat_no(text: str) -> tuple[str | None, float]:
    for pattern in SEAT_NO_PATTERNS:
        match = re.search(pattern, text)
        if match:
            value = match.group(1)
            if not value.endswith("号"):
                value = f"{value}号"
            return value, 0.9
    return None, 0.0


def _extract_seat_class(text: str) -> tuple[str | None, float]:
    for pattern in SEAT_CLASS_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1), 0.9
    return None, 0.0


def _extract_passenger_name(lines: list[str]) -> tuple[str | None, float]:
    for index, line in enumerate(lines):
        if _looks_like_masked_identity(line):
            for next_index in range(index + 1, min(index + 4, len(lines))):
                candidate = lines[next_index]
                if _looks_like_passenger_name(candidate):
                    return candidate, 0.85

    for line in lines:
        if _looks_like_passenger_name(line):
            return line, 0.55
    return None, 0.0


def _find_adjacent_station(lines: list[str], start_index: int, step: int) -> str | None:
    index = start_index + step
    while 0 <= index < len(lines):
        candidate = lines[index]
        if _looks_like_station_name(candidate):
            return candidate
        index += step
    return None


def _looks_like_station_name(value: str) -> bool:
    candidate = value.strip()
    if not candidate.endswith("站"):
        return False
    if len(candidate) < 2 or len(candidate) > 12:
        return False
    if not re.search(r"[\u4e00-\u9fff]", candidate):
        return False
    return True


def _looks_like_masked_identity(value: str) -> bool:
    candidate = value.strip()
    return bool(re.fullmatch(r"\d{6,}[*Xx]{4,}\d{2,}", candidate))


def _looks_like_passenger_name(value: str) -> bool:
    candidate = value.strip()
    if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", candidate):
        return False
    blocked_words = ("大学", "铁路", "中国", "税务", "客票", "站", "日期", "发票", "票价", "名称")
    return not any(word in candidate for word in blocked_words)


def _extract_named_value(text: str, patterns: tuple[str, ...]) -> tuple[str | None, float]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = _clean_line_value(match.group(1))
        if value:
            return value, 0.85
    return None, 0.0


def _extract_tax_id(text: str, patterns: tuple[str, ...]) -> tuple[str | None, float]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = _clean_tax_id(match.group(1))
        if value:
            return value, 0.85
    return None, 0.0


def _extract_parties_from_tax_id_pairs(text: str) -> dict[str, str | float | None]:
    lines = _normalized_lines(text)
    pairs: list[tuple[str | None, str]] = []
    for index, line in enumerate(lines):
        tax_id = _clean_tax_id(line)
        if not tax_id:
            continue
        name = _find_name_before_tax_id(lines, index)
        pairs.append((name, tax_id))

    buyer_name = pairs[0][0] if len(pairs) >= 1 else None
    buyer_tax_id = pairs[0][1] if len(pairs) >= 1 else None
    vendor = pairs[1][0] if len(pairs) >= 2 else None
    vendor_tax_id = pairs[1][1] if len(pairs) >= 2 else None

    return {
        "buyer_name": buyer_name,
        "buyer_name_conf": 0.75 if buyer_name else 0.0,
        "buyer_tax_id": buyer_tax_id,
        "buyer_tax_id_conf": 0.8 if buyer_tax_id else 0.0,
        "vendor": vendor,
        "vendor_conf": 0.75 if vendor else 0.0,
        "vendor_tax_id": vendor_tax_id,
        "vendor_tax_id_conf": 0.8 if vendor_tax_id else 0.0,
    }


def _normalized_lines(text: str) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = _clean_line_value(raw_line)
        if line:
            lines.append(line)
    return lines


def _find_name_before_tax_id(lines: list[str], tax_id_index: int) -> str | None:
    for index in range(tax_id_index - 1, max(tax_id_index - 5, -1), -1):
        candidate = lines[index].strip()
        if not candidate:
            continue
        if _clean_tax_id(candidate):
            continue
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", candidate):
            continue
        if re.search(r"[0-9]{4}\s*[-/.年]", candidate):
            continue
        if any(label in candidate for label in ("开票", "价税", "项目名称", "统一社会信用代码", "纳税人识别号")):
            continue
        if 2 <= len(candidate) <= 80:
            return candidate
    return None


def _clean_tax_id(value: str) -> str | None:
    candidate = re.sub(r"[^0-9A-Za-z]", "", value).upper()
    if len(candidate) < 15 or len(candidate) > 20:
        return None
    if not re.search(r"[A-Z]", candidate):
        return None
    return candidate


def _clean_line_value(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    cleaned = cleaned.lstrip(":：")
    return cleaned[:200]


def _normalize_date_token(token: str) -> str:
    normalized = re.sub(r"\s+", "", token)
    normalized = normalized.replace("年", "-").replace("月", "-").replace("日", "")
    normalized = normalized.replace("/", "-").replace(".", "-")
    parts = [part for part in normalized.split("-") if part]
    if len(parts) != 3:
        return normalized
    year = parts[0].zfill(4)
    month = parts[1].zfill(2)
    day = parts[2].zfill(2)
    return f"{year}-{month}-{day}"


def _is_field_present(field_name: str, values: dict[str, Any]) -> bool:
    value = values.get(field_name)
    if field_name == "amount":
        return isinstance(value, (int, float))
    return value is not None and str(value).strip() != ""


def _calculate_extraction_confidence(field_confidence: dict[str, float]) -> float:
    weighted_keys = ("invoice_number", "issue_date", "amount", "invoice_type")
    scores = [field_confidence.get(key, 0.0) for key in weighted_keys]
    if not scores:
        return 0.0
    return round(float(sum(scores) / len(scores)), 4)


def _average(values: list[float]) -> float | None:
    valid = [v for v in values if isinstance(v, (int, float))]
    if not valid:
        return None
    return round(float(sum(valid) / len(valid)), 4)


def _count_reason(counter: dict[str, int], reason: str) -> None:
    counter[reason] = int(counter.get(reason, 0)) + 1
