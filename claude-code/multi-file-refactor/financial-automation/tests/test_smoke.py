from __future__ import annotations

import os
import shutil
import textwrap
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from src.bitable_attachment_uploader import (
    BitableAttachmentUploadError,
    build_attachment_field_value,
    build_bitable_attachment_upload_request,
    perform_bitable_attachment_upload,
)
from src.ingest import load_input_documents
from src.main import load_app_config
from src.ocr_extract import parse_fields_from_text
from src.output_formatter import (
    format_skill_document,
    format_skill_review_queue,
    format_skill_run_result,
)
from src.skill_entry import (
    build_bitable_write_plan,
    create_job_workspace,
    materialize_attachments,
    run_skill_job,
)
from src.sync_bitable import (
    BitableSettings,
    build_expense_record,
    build_transport_record,
    load_bitable_settings,
    sync_skill_result_to_bitable,
)
from src.bitable_session_writer import choose_bitable_write_action, pick_reusable_record_id
from src.validate import DEFAULT_RULES_PATH, validate_documents


def _make_test_workspace() -> Path:
    sandbox_root = Path(__file__).resolve().parent.parent / ".tmp_tests"
    sandbox_root.mkdir(parents=True, exist_ok=True)
    workspace = sandbox_root / f"test_{uuid.uuid4().hex}"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


class PathResolutionSmokeTest(unittest.TestCase):
    def test_relative_paths_are_resolved_from_project_root(self) -> None:
        project_root = _make_test_workspace()
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))
        config_dir = project_root / "config"
        config_dir.mkdir()

        config_path = config_dir / "app_config.yaml"
        config_path.write_text(
            textwrap.dedent(
                """
                paths:
                  input_dir: runtime/inbox
                  output_dir: runtime/output
                  runtime_dir: runtime
                ocr:
                  rapidocr:
                    model_root_dir: runtime/models/rapidocr
                validate:
                  rules_file: config/rules.yaml
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        config, detected_root = load_app_config(config_path)
        self.assertEqual(detected_root, project_root.resolve())
        self.assertEqual(
            config["paths"]["input_dir"],
            str((project_root / "runtime/inbox").resolve()),
        )
        self.assertEqual(
            config["ocr"]["rapidocr"]["model_root_dir"],
            str((project_root / "runtime/models/rapidocr").resolve()),
        )

    def test_openclaw_project_root_override(self) -> None:
        workspace = _make_test_workspace()
        self.addCleanup(lambda: shutil.rmtree(workspace, ignore_errors=True))
        config_dir = workspace / "proj" / "config"
        config_dir.mkdir(parents=True)
        override_root = workspace / "override_root"
        override_root.mkdir()

        config_path = config_dir / "app_config.yaml"
        config_path.write_text(
            "paths:\n  input_dir: runtime/inbox\n",
            encoding="utf-8",
        )

        old_value = os.environ.get("OPENCLAW_PROJECT_ROOT")
        os.environ["OPENCLAW_PROJECT_ROOT"] = str(override_root)
        try:
            config, detected_root = load_app_config(config_path)
        finally:
            if old_value is None:
                os.environ.pop("OPENCLAW_PROJECT_ROOT", None)
            else:
                os.environ["OPENCLAW_PROJECT_ROOT"] = old_value

        self.assertEqual(detected_root, override_root.resolve())
        self.assertEqual(
            config["paths"]["input_dir"],
            str((override_root / "runtime/inbox").resolve()),
        )


class IngestSmokeTest(unittest.TestCase):
    def test_ingest_filters_and_collects_metadata(self) -> None:
        root = _make_test_workspace()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        inbox = root / "runtime" / "inbox"
        inbox.mkdir(parents=True)

        (inbox / "ok_invoice.pdf").write_bytes(b"fake-pdf")
        (inbox / "ok_image.JPG").write_bytes(b"fake-image")
        (inbox / "note.txt").write_text("not supported", encoding="utf-8")
        (inbox / "empty.png").write_bytes(b"")
        (inbox / "~$tmp.pdf").write_bytes(b"temp")

        config = {"paths": {"input_dir": str(inbox)}}
        documents, report = load_input_documents(config)

        self.assertEqual(report["total_seen"], 5)
        self.assertEqual(report["accepted"], 2)
        self.assertEqual(report["skipped"], 3)
        self.assertEqual(report["skip_reasons"]["unsupported_ext"], 1)
        self.assertEqual(report["skip_reasons"]["empty_file"], 1)
        self.assertEqual(report["skip_reasons"]["temp_file"], 1)

        self.assertEqual(len(documents), 2)
        self.assertIn("doc_id", documents[0])
        self.assertIn("file_path", documents[0])
        self.assertIn("modified_at", documents[0])

    def test_ingest_handles_missing_input_dir(self) -> None:
        documents, report = load_input_documents({"paths": {"input_dir": "/nonexistent/path"}})
        self.assertEqual(documents, [])
        self.assertEqual(report["accepted"], 0)
        self.assertEqual(report["total_seen"], 0)
        self.assertTrue(report["errors"])


class OCRExtractSmokeTest(unittest.TestCase):
    def test_parse_accommodation_invoice_detail_fields(self) -> None:
        text = textwrap.dedent(
            """
            电子发票（普通发票）
            发票号码：24122000000046417589
            开票日期：2024 年 08 月 05 日
            购买方名称：复旦大学
            统一社会信用代码/纳税人识别号：12100000425006117P
            销售方名称：天津滨海一号酒店管理有限公司
            销售方统一社会信用代码/纳税人识别号：9112011656269768XB
            价税合计（小写）：￥924.00
            * 住宿服务 * 住宿费 6%871.70 52.30290.5660377358493
            """
        ).strip()

        parsed = parse_fields_from_text(text, default_currency="CNY")
        self.assertEqual(parsed["invoice_number"], "24122000000046417589")
        self.assertEqual(parsed["issue_date"], "2024-08-05")
        self.assertEqual(parsed["amount"], 924.0)
        self.assertEqual(parsed["currency"], "CNY")
        self.assertEqual(parsed["invoice_type"], "accommodation_fee")
        self.assertEqual(parsed["buyer_name"], "复旦大学")
        self.assertEqual(parsed["buyer_tax_id"], "12100000425006117P")
        self.assertEqual(parsed["vendor"], "天津滨海一号酒店管理有限公司")
        self.assertEqual(parsed["vendor_tax_id"], "9112011656269768XB")
        self.assertEqual(parsed["item_name"], "* 住宿服务 * 住宿费")
        self.assertEqual(parsed["quantity"], 3)
        self.assertAlmostEqual(parsed["unit_price"], 290.5660377358493)
        self.assertEqual(parsed["line_amount"], 871.7)
        self.assertEqual(parsed["tax_rate"], "6%")
        self.assertEqual(parsed["tax_amount"], 52.3)
        self.assertEqual(len(parsed["line_items"]), 1)
        self.assertFalse(parsed["needs_review"])

    def test_parse_conference_invoice_detail_fields(self) -> None:
        text = textwrap.dedent(
            """
            电子发票（普通发票）
            发票号码：24112000000114409809
            开票日期：2024年08月26日
            购买方名称：复旦大学
            统一社会信用代码/纳税人识别号：12100000425006117P
            销售方名称：北京冠大文化传播有限公司
            销售方统一社会信用代码/纳税人识别号：91110115MADQ08DP3H
            价税合计（小写）：￥5570.80
            * 会展服务 * 注册费 1%5515.64 55.165515.643564356441
            """
        ).strip()

        parsed = parse_fields_from_text(text, default_currency="CNY")
        self.assertEqual(parsed["invoice_type"], "conference_fee")
        self.assertEqual(parsed["item_name"], "* 会展服务 * 注册费")
        self.assertEqual(parsed["quantity"], 1)
        self.assertAlmostEqual(parsed["unit_price"], 5515.643564356441)
        self.assertEqual(parsed["line_amount"], 5515.64)
        self.assertEqual(parsed["tax_rate"], "1%")
        self.assertEqual(parsed["tax_amount"], 55.16)

    def test_parse_rail_ticket_fields(self) -> None:
        text = textwrap.dedent(
            """
            电子发票
            铁路电子客票
            发票号码：25339190041005476782
            开票日期：2025年10月16日
            杭州东站
            G240
            上海虹桥站
            2025年10月12日
            19:34开
            05车14F号
            二等座
            票价：￥87.00
            3607022001****0013
            林泓
            购票方名称：复旦大学
            统一社会信用代码：12100000425006117P
            """
        ).strip()

        parsed = parse_fields_from_text(text, default_currency="CNY")
        self.assertEqual(parsed["invoice_type"], "transportation_fee")
        self.assertEqual(parsed["buyer_name"], "复旦大学")
        self.assertEqual(parsed["buyer_tax_id"], "12100000425006117P")
        self.assertEqual(parsed["transport_number"], "G240")
        self.assertEqual(parsed["route"], "杭州东站->上海虹桥站")
        self.assertEqual(parsed["from_station"], "杭州东站")
        self.assertEqual(parsed["to_station"], "上海虹桥站")
        self.assertEqual(parsed["passenger_name"], "林泓")
        self.assertEqual(parsed["travel_date"], "2025-10-12")
        self.assertEqual(parsed["departure_time"], "19:34")
        self.assertEqual(parsed["seat_no"], "05车14F号")
        self.assertEqual(parsed["seat_class"], "二等座")
        self.assertIsNone(parsed["vendor"])
        self.assertIsNone(parsed["vendor_tax_id"])
        self.assertEqual(parsed["line_items"], [])


class ValidateSmokeTest(unittest.TestCase):
    def test_validate_documents_flags_missing_transport_fields(self) -> None:
        items = [
            {
                "doc_id": "doc-1",
                "source_file_name": "ticket.jpg",
                "invoice_number": "25339190041005476782",
                "issue_date": "2025-10-16",
                "amount": 87.0,
                "invoice_type": "transportation_fee",
                "buyer_name": "复旦大学",
                "buyer_tax_id": "12100000425006117P",
                "vendor": None,
                "vendor_tax_id": None,
                "route": None,
                "transport_number": None,
                "from_station": None,
                "to_station": None,
                "passenger_name": None,
                "travel_date": None,
                "departure_time": None,
                "seat_no": None,
                "seat_class": None,
                "field_confidence": {
                    "invoice_number": 0.99,
                    "issue_date": 0.98,
                    "amount": 0.97,
                    "invoice_type": 0.95,
                },
                "extraction_confidence": 0.97,
                "needs_review": False,
                "review_reasons": [],
            }
        ]
        rules = {
            "required_fields": ["invoice_number", "issue_date", "amount", "invoice_type"],
            "confidence": {"minimum_confidence": 0.75, "low_confidence_requires_review": True},
            "expense_type_rules": {
                "transportation_fee": {
                    "required_fields": [
                        "buyer_name",
                        "route",
                        "transport_number",
                        "from_station",
                        "to_station",
                        "travel_date",
                        "passenger_name",
                    ],
                    "max_amount": 2000,
                }
            },
            "compliance": {
                "severity_map": {
                    "missing_required_field": "error",
                    "amount_exceeds_limit": "warning",
                    "low_confidence": "warning",
                    "duplicate_invoice_number": "error",
                    "unknown_expense_type": "warning",
                    "line_item_mismatch": "warning",
                    "invoice_total_mismatch": "warning",
                }
            },
            "review_policy": {
                "image_ocr_requires_review": False,
                "missing_required_field_requires_review": True,
                "amount_exceeds_limit_requires_review": True,
                "duplicate_invoice_requires_review": True,
                "consistency_requires_review": True,
            },
            "consistency": {"check_invoice_total": True, "check_line_items": True, "amount_tolerance": 0.05},
            "dedup": {"strategy": "invoice_number_first", "fallback_fields": ["issue_date", "amount", "vendor", "source_file_name"]},
        }

        validated, report = validate_documents(items, {"validate": {"rules_file": str(DEFAULT_RULES_PATH)}})
        self.assertEqual(validated[0]["compliance_status"], "error")
        finding_codes = {f["code"] for f in validated[0]["validation_findings"]}
        self.assertIn("missing_required_field", finding_codes)
        self.assertTrue(validated[0]["needs_review"])


class FormatterSmokeTest(unittest.TestCase):
    def test_formatter_outputs_expected_skill_payloads(self) -> None:
        validated_item = {
            "doc_id": "doc-1",
            "invoice_type": "conference_fee",
            "source_file_name": "invoice.pdf",
            "invoice_number": "24112000000114409809",
            "issue_date": "2024-08-26",
            "amount": 5570.8,
            "currency": "CNY",
            "buyer_name": "复旦大学",
            "buyer_tax_id": "12100000425006117P",
            "vendor": "北京冠大文化传播有限公司",
            "vendor_tax_id": "91110115MADQ08DP3H",
            "item_name": "* 会展服务 * 注册费",
            "quantity": 1,
            "unit_price": 5515.643564356441,
            "line_amount": 5515.64,
            "tax_rate": "1%",
            "tax_amount": 55.16,
            "line_items": [
                {
                    "item_name": "* 会展服务 * 注册费",
                    "quantity": 1,
                    "unit_price": 5515.643564356441,
                    "line_amount": 5515.64,
                    "tax_rate": "1%",
                    "tax_amount": 55.16,
                }
            ],
            "field_confidence": {"invoice_number": 0.99, "issue_date": 0.98, "amount": 0.97, "invoice_type": 0.96},
            "extraction_confidence": 0.975,
            "compliance_status": "pass",
            "validation_findings": [],
            "needs_review": False,
            "review_reasons": [],
        }

        skill_doc = format_skill_document(validated_item)
        self.assertEqual(skill_doc["document_type"], "conference_fee")
        self.assertEqual(skill_doc["extraction"]["buyer"]["name"], "复旦大学")
        self.assertEqual(skill_doc["extraction"]["seller"]["name"], "北京冠大文化传播有限公司")
        self.assertEqual(skill_doc["extraction"]["line_items"][0]["line_amount"], 5515.64)

        skill_review = format_skill_review_queue([validated_item])
        self.assertEqual(skill_review, [])

        result = format_skill_run_result(
            app_name="financial-expense-automation",
            run_id="run_001",
            input_dir="runtime/inbox",
            output_dir="runtime/output/run_001",
            documents=[skill_doc],
            review_queue=[],
            counts={
                "documents_seen": 1,
                "documents_accepted": 1,
                "documents_extracted": 1,
                "documents_for_review": 0,
                "documents_pass": 1,
                "documents_warning": 0,
                "documents_error": 0,
            },
        )
        self.assertEqual(result["summary"]["documents_pass"], 1)
        self.assertEqual(result["highlights"]["review_queue_count"], 0)


class SkillEntrySmokeTest(unittest.TestCase):
    def test_create_job_workspace_uses_runtime_root(self) -> None:
        root = _make_test_workspace()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        config = {"paths": {"runtime_dir": str(root / "custom_runtime")}}
        workspace = create_job_workspace(config, root, job_id="job_test")
        self.assertEqual(Path(workspace["job_dir"]), root / "custom_runtime" / "jobs" / "job_test")
        self.assertTrue(Path(workspace["input_dir"]).exists())
        self.assertTrue(Path(workspace["output_dir"]).exists())

    def test_materialize_attachments_filters_unsupported_files(self) -> None:
        root = _make_test_workspace()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        input_dir = root / "inbox"
        source_file = root / "invoice.pdf"
        source_file.write_bytes(b"pdf-bytes")

        attachments = [
            {"file_name": "invoice.pdf", "source_path": str(source_file)},
            {"file_name": "note.txt", "content_bytes": b"ignore me"},
        ]

        saved = materialize_attachments(attachments, input_dir)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].name, "invoice.pdf")
        self.assertEqual(saved[0].read_bytes(), b"pdf-bytes")

    @patch("src.skill_entry.sync_skill_result_with_config")
    @patch("src.skill_entry.load_skill_result")
    @patch("src.skill_entry.run_pipeline_for_job")
    @patch("src.skill_entry.materialize_attachments")
    @patch("src.skill_entry.create_job_workspace")
    @patch("src.skill_entry.load_app_config")
    def test_run_skill_job_appends_job_and_bitable_sync(
        self,
        mock_load_config,
        mock_workspace,
        mock_materialize,
        mock_run_pipeline,
        mock_load_result,
        mock_sync,
    ) -> None:
        root = _make_test_workspace()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        config = {"sync": {"bitable": {"enabled": False}}}
        mock_load_config.return_value = (config, root)
        mock_workspace.return_value = {
            "job_id": "job-1",
            "job_dir": root / "runtime/jobs/job-1",
            "input_dir": root / "runtime/jobs/job-1/inbox",
            "output_dir": root / "runtime/jobs/job-1/output",
        }
        saved_file = root / "runtime/jobs/job-1/inbox/invoice.pdf"
        saved_file.parent.mkdir(parents=True, exist_ok=True)
        saved_file.write_bytes(b"pdf")
        mock_materialize.return_value = [saved_file]
        mock_run_pipeline.return_value = {"output": {"run_dir": str(root / "runtime/output/run_001")}}
        mock_load_result.return_value = {"documents": []}
        mock_sync.return_value = {"enabled": False, "status": "disabled"}

        result = run_skill_job([{"file_name": "invoice.pdf", "source_path": str(saved_file)}])
        self.assertEqual(result["job"]["job_id"], "job-1")
        self.assertEqual(result["job"]["saved_files"], [str(saved_file)])
        self.assertEqual(result["bitable_sync"]["status"], "disabled")
        mock_sync.assert_called_once()


class BitableAttachmentUploaderSmokeTest(unittest.TestCase):
    def test_build_bitable_attachment_upload_request(self) -> None:
        request = build_bitable_attachment_upload_request(
            app_token="app_token_xxx",
            attachment_paths=["/tmp/a.jpg", "/tmp/b.pdf"],
        )
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.app_token, "app_token_xxx")
        self.assertEqual(request.provider, "bitable_context_upload_user_identity")
        self.assertEqual(request.attachment_paths, ["/tmp/a.jpg", "/tmp/b.pdf"])

    def test_build_bitable_attachment_upload_request_returns_none_when_empty(self) -> None:
        request = build_bitable_attachment_upload_request(app_token="app_token_xxx", attachment_paths=[])
        self.assertIsNone(request)

    def test_perform_bitable_attachment_upload_requires_user_token(self) -> None:
        request = build_bitable_attachment_upload_request(
            app_token="app_token_xxx",
            attachment_paths=["/tmp/a.jpg"],
        )
        assert request is not None
        with self.assertRaises(BitableAttachmentUploadError):
            perform_bitable_attachment_upload(request)

    def test_build_attachment_field_value(self) -> None:
        self.assertEqual(
            build_attachment_field_value(["tok1", "tok2"]),
            [{"file_token": "tok1"}, {"file_token": "tok2"}],
        )


class BitableWritePlanSmokeTest(unittest.TestCase):
    @patch("src.skill_entry.perform_bitable_attachment_upload")
    @patch("src.skill_entry.load_user_access_token")
    def test_build_bitable_write_plan_includes_uploaded_attachment_tokens(self, mocked_load_token, mocked_upload) -> None:
        mocked_load_token.return_value = "u-token"
        class UploadResult:
            def __init__(self) -> None:
                self.ok = True
                self.status = "completed"
                self.provider = "bitable_context_upload_user_identity"
                self.file_tokens = ["file_tok_1"]
                self.uploaded = [{"file_token": "file_tok_1"}]
                self.errors = []
                self.message = "ok"
        mocked_upload.return_value = UploadResult()
        skill_result = {
            "documents": [
                {
                    "doc_id": "doc-expense",
                    "document_type": "conference_fee",
                    "source_file_name": "invoice.jpg",
                    "extraction": {
                        "document": {"invoice_number": "123", "issue_date": "2024-08-26", "amount": 100.0, "currency": "CNY"},
                        "buyer": {"name": "复旦大学", "tax_id": "12100000425006117P"},
                        "seller": {"name": "供应商", "tax_id": "taxid"},
                        "line_items": [{"item_name": "测试项目", "quantity": 1, "unit_price": 100.0, "line_amount": 100.0, "tax_rate": "0%", "tax_amount": 0.0}],
                    },
                    "validation": {"status": "pass"},
                    "review": {"needs_review": False, "reasons": []},
                }
            ]
        }
        plan = build_bitable_write_plan(
            skill_result,
            attachment_paths=["/tmp/invoice.jpg"],
            app_token="app_token_xxx",
            config={"sync": {"bitable": {"endpoint": "https://open.feishu.cn"}}},
        )
        upload_result = plan["attachment_upload_result"]
        if hasattr(upload_result, "get"):
            self.assertEqual(upload_result["file_tokens"], ["file_tok_1"])
        else:
            self.fail("attachment_upload_result should be materialized as a dict")
        self.assertEqual(plan["records"][0]["fields"]["票据附件"], [{"file_token": "file_tok_1"}])

    def test_build_bitable_write_plan_includes_attachment_handoff(self) -> None:
        skill_result = {
            "documents": [
                {
                    "doc_id": "doc-transport",
                    "document_type": "transportation_fee",
                    "source_file_name": "ticket.jpg",
                    "extraction": {
                        "document": {"invoice_number": "253", "amount": 87.0, "currency": "CNY"},
                        "buyer": {"name": "复旦大学", "tax_id": "12100000425006117P"},
                        "travel": {
                            "transport_number": "G240",
                            "from_station": "杭州东站",
                            "to_station": "上海虹桥站",
                            "travel_date": "2025-10-12",
                            "departure_time": "19:34",
                        },
                        "passenger": {"name": "林泓", "seat_no": "05车14F号", "seat_class": "二等座"},
                    },
                    "validation": {"status": "pass"},
                    "review": {"needs_review": False, "reasons": []},
                }
            ]
        }
        with patch("src.skill_entry.load_user_access_token") as mock_load_token:
            mock_load_token.return_value = "test_user_token_123"
            plan = build_bitable_write_plan(
                skill_result,
                attachment_paths=["/tmp/ticket.jpg"],
                app_token="app_token_xxx",
                config={
                    "sync": {
                        "bitable": {
                            "transport_table_id": "tbl_transport",
                            "expense_table_id": "tbl_expense",
                        }
                    }
                },
            )
        self.assertEqual(plan["mode"], "user_identity")
        self.assertFalse(plan["include_attachments"])
        self.assertEqual(plan["write_policy"]["preferred"], "update_first_blank_row_then_create")
        self.assertEqual(plan["attachment_strategy"], "upload_to_bitable_context_first")
        self.assertTrue(plan["attachment_upload_handoff"]["required"])
        self.assertEqual(plan["attachment_upload_handoff"]["status"], "ready_with_user_identity")
        self.assertEqual(plan["attachment_upload_handoff"]["request"]["app_token"], "app_token_xxx")
        self.assertTrue(plan["attachment_upload_handoff"]["request"]["has_access_token"])
        self.assertEqual(plan["attachment_upload_handoff"]["attachment_paths"], ["/tmp/ticket.jpg"])
        self.assertEqual(plan["records"][0]["table_id"], "tbl_transport")
        self.assertEqual(plan["records"][0]["write_action"], {"action": "create"})


class BitableSyncSmokeTest(unittest.TestCase):
    def test_load_bitable_settings_from_env(self) -> None:
        env_patch = {
            "FEISHU_BITABLE_APP_TOKEN": "app_token_xxx",
            "FEISHU_BITABLE_TRANSPORT_TABLE": "tbl_transport",
            "FEISHU_BITABLE_EXPENSE_TABLE": "tbl_expense",
        }
        with patch.dict(os.environ, env_patch, clear=False):
            settings = load_bitable_settings(
                {
                    "sync": {
                        "bitable": {
                            "enabled": True,
                            "dry_run": False,
                            "endpoint": "https://open.feishu.cn",
                            "batch_size": 50,
                            "app_token_env": "FEISHU_BITABLE_APP_TOKEN",
                            "transport_table_id_env": "FEISHU_BITABLE_TRANSPORT_TABLE",
                            "expense_table_id_env": "FEISHU_BITABLE_EXPENSE_TABLE",
                        }
                    }
                }
            )

        self.assertTrue(settings.enabled)
        self.assertFalse(settings.dry_run)
        self.assertEqual(settings.batch_size, 50)
        self.assertEqual(settings.transport_table_id, "tbl_transport")
        self.assertEqual(settings.expense_table_id, "tbl_expense")

    def test_build_transport_record(self) -> None:
        document = {
            "doc_id": "doc-transport",
            "document_type": "transportation_fee",
            "source_file_name": "ticket.jpg",
            "extraction": {
                "document": {
                    "invoice_number": "25339190041005476782",
                    "amount": 87.0,
                    "currency": "CNY",
                },
                "buyer": {"name": "复旦大学", "tax_id": "12100000425006117P"},
                "travel": {
                    "transport_number": "G240",
                    "from_station": "杭州东站",
                    "to_station": "上海虹桥站",
                    "travel_date": "2025-10-12",
                    "departure_time": "19:34",
                },
                "passenger": {"name": "林泓", "seat_no": "05车14F号", "seat_class": "二等座"},
            },
            "validation": {"status": "pass"},
            "review": {"needs_review": False, "reasons": []},
        }
        record = build_transport_record(document, [{"file_token": "file_transport"}])
        self.assertEqual(record["doc_id"], "doc-transport")
        self.assertEqual(record["报销类型"], "🚄 交通报销")
        self.assertEqual(record["票据附件"], [{"file_token": "file_transport"}])
        self.assertEqual(record["金额"], 87.0)
        self.assertEqual(record["购票主体"], "复旦大学")
        self.assertEqual(record["车次"], "G240")
        self.assertEqual(record["乘车日期"], 1760198400000)
        self.assertEqual(record["校验状态"], "✅ 通过")
        self.assertEqual(record["是否复核"], "否")

    def test_build_expense_record(self) -> None:
        document = {
            "doc_id": "doc-expense",
            "document_type": "conference_fee",
            "source_file_name": "invoice.pdf",
            "extraction": {
                "document": {
                    "invoice_number": "24112000000114409809",
                    "issue_date": "2024-08-26",
                    "amount": 5570.8,
                    "currency": "CNY",
                },
                "buyer": {"name": "复旦大学", "tax_id": "12100000425006117P"},
                "seller": {"name": "北京冠大文化传播有限公司", "tax_id": "91110115MADQ08DP3H"},
                "line_items": [
                    {
                        "item_name": "* 会展服务 * 注册费",
                        "quantity": 1,
                        "unit_price": 5515.643564356441,
                        "line_amount": 5515.64,
                        "tax_rate": "1%",
                        "tax_amount": 55.16,
                    }
                ],
            },
            "validation": {"status": "pass"},
            "review": {"needs_review": False, "reasons": []},
        }
        record = build_expense_record(document, [{"file_token": "file_expense"}])
        self.assertEqual(record["doc_id"], "doc-expense")
        self.assertEqual(record["报销类型"], "🧾 费用报销")
        self.assertEqual(record["票据附件"], [{"file_token": "file_expense"}])
        self.assertEqual(record["金额"], 5570.8)
        self.assertEqual(record["购买方名称"], "复旦大学")
        self.assertEqual(record["销售方名称"], "北京冠大文化传播有限公司")
        self.assertEqual(record["项目名称"], "* 会展服务 * 注册费")
        self.assertEqual(record["开票日期"], 1724601600000)
        self.assertEqual(record["校验状态"], "✅ 通过")
        self.assertEqual(record["是否复核"], "否")

    def test_sync_skill_result_to_bitable_dry_run(self) -> None:
        settings = BitableSettings(
            enabled=True,
            dry_run=True,
            endpoint="https://open.feishu.cn",
            batch_size=200,
            mode="user_identity",
            include_attachments=False,
            app_id="",
            app_secret="",
            app_token="app_token_xxx",
            transport_table_id="tbl_transport",
            expense_table_id="tbl_expense",
        )
        skill_result = {
            "documents": [
                {
                    "doc_id": "doc-transport",
                    "document_type": "transportation_fee",
                    "source_file_name": "ticket.jpg",
                    "extraction": {
                        "document": {"invoice_number": "25339190041005476782", "amount": 87.0, "currency": "CNY"},
                        "buyer": {"name": "复旦大学", "tax_id": "12100000425006117P"},
                        "travel": {
                            "transport_number": "G240",
                            "from_station": "杭州东站",
                            "to_station": "上海虹桥站",
                            "travel_date": "2025-10-12",
                            "departure_time": "19:34",
                        },
                        "passenger": {"name": "林泓", "seat_no": "05车14F号", "seat_class": "二等座"},
                    },
                    "validation": {"status": "pass"},
                    "review": {"needs_review": False, "reasons": []},
                },
                {
                    "doc_id": "doc-expense",
                    "document_type": "conference_fee",
                    "source_file_name": "invoice.pdf",
                    "extraction": {
                        "document": {
                            "invoice_number": "24112000000114409809",
                            "issue_date": "2024-08-26",
                            "amount": 5570.8,
                            "currency": "CNY",
                        },
                        "buyer": {"name": "复旦大学", "tax_id": "12100000425006117P"},
                        "seller": {"name": "北京冠大文化传播有限公司", "tax_id": "91110115MADQ08DP3H"},
                        "line_items": [
                            {
                                "item_name": "* 会展服务 * 注册费",
                                "quantity": 1,
                                "unit_price": 5515.643564356441,
                                "line_amount": 5515.64,
                                "tax_rate": "1%",
                                "tax_amount": 55.16,
                            }
                        ],
                    },
                    "validation": {"status": "pass"},
                    "review": {"needs_review": False, "reasons": []},
                },
            ]
        }
        summary = sync_skill_result_to_bitable(
            skill_result,
            settings,
            attachment_paths=["/tmp/ticket.jpg", "/tmp/invoice.pdf"],
        )
        self.assertEqual(summary["status"], "dry_run")
        self.assertEqual(summary["tables"]["transport"]["records_prepared"], 1)
        self.assertEqual(summary["tables"]["expense"]["records_prepared"], 1)
        self.assertEqual(summary["mode"], "user_identity")
        self.assertFalse(summary["include_attachments"])
        self.assertEqual(summary["tables"]["transport"]["preview"][0]["票据附件"], "🖼️ 原图已接收：ticket.jpg")
        self.assertEqual(summary["tables"]["expense"]["preview"][0]["票据附件"], "🖼️ 原图已接收：invoice.pdf")


class BitableSessionWriterSmokeTest(unittest.TestCase):
    def test_pick_reusable_record_id_prefers_blank_doc_id(self) -> None:
        records = [
            {"record_id": "rec1", "fields": {"doc_id": [{"text": "filled", "type": "text"}]}},
            {"record_id": "rec2", "fields": {}},
            {"record_id": "rec3", "fields": {"doc_id": "other"}},
        ]
        self.assertEqual(pick_reusable_record_id(records), "rec2")

    def test_choose_bitable_write_action_uses_update_when_blank_row_exists(self) -> None:
        action = choose_bitable_write_action([
            {"record_id": "rec2", "fields": {}},
        ])
        self.assertEqual(action, {"action": "update", "record_id": "rec2"})

    def test_choose_bitable_write_action_falls_back_to_create(self) -> None:
        action = choose_bitable_write_action([
            {"record_id": "rec1", "fields": {"doc_id": [{"text": "filled", "type": "text"}]}}
        ])
        self.assertEqual(action, {"action": "create"})


class SyncBitableSmokeTest(unittest.TestCase):
    def test_load_bitable_settings_prefers_environment_overrides(self) -> None:
        old_values = {
            "FEISHU_APP_ID": os.environ.get("FEISHU_APP_ID"),
            "FEISHU_APP_SECRET": os.environ.get("FEISHU_APP_SECRET"),
            "FEISHU_BITABLE_APP_TOKEN": os.environ.get("FEISHU_BITABLE_APP_TOKEN"),
            "FEISHU_BITABLE_TRANSPORT_TABLE": os.environ.get("FEISHU_BITABLE_TRANSPORT_TABLE"),
            "FEISHU_BITABLE_EXPENSE_TABLE": os.environ.get("FEISHU_BITABLE_EXPENSE_TABLE"),
        }
        os.environ["FEISHU_APP_ID"] = "cli_app_id"
        os.environ["FEISHU_APP_SECRET"] = "cli_secret"
        os.environ["FEISHU_BITABLE_APP_TOKEN"] = "cli_app_token"
        os.environ["FEISHU_BITABLE_TRANSPORT_TABLE"] = "cli_transport"
        os.environ["FEISHU_BITABLE_EXPENSE_TABLE"] = "cli_expense"
        try:
            settings = load_bitable_settings(
                {
                    "sync": {
                        "bitable": {
                            "enabled": True,
                            "dry_run": True,
                            "app_id_env": "FEISHU_APP_ID",
                            "app_secret_env": "FEISHU_APP_SECRET",
                            "app_token_env": "FEISHU_BITABLE_APP_TOKEN",
                            "transport_table_id_env": "FEISHU_BITABLE_TRANSPORT_TABLE",
                            "expense_table_id_env": "FEISHU_BITABLE_EXPENSE_TABLE",
                        }
                    }
                }
            )
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(settings.app_id, "cli_app_id")
        self.assertEqual(settings.transport_table_id, "cli_transport")
        self.assertEqual(settings.expense_table_id, "cli_expense")

    def test_build_transport_record_maps_fields(self) -> None:
        document = {
            "doc_id": "doc-rail",
            "document_type": "transportation_fee",
            "source_file_name": "ticket.jpg",
            "extraction": {
                "document": {
                    "invoice_number": "25339190041005476782",
                    "amount": 87.0,
                    "currency": "CNY",
                },
                "buyer": {"name": "Fudan", "tax_id": "12100000425006117P"},
                "travel": {
                    "transport_number": "G240",
                    "from_station": "Hangzhou East",
                    "to_station": "Shanghai Hongqiao",
                    "travel_date": "2025-10-12",
                    "departure_time": "19:34",
                },
                "passenger": {
                    "name": "Lemon",
                    "seat_no": "05车14F号",
                    "seat_class": "二等座",
                },
            },
            "validation": {"status": "pass"},
            "review": {"needs_review": True, "reasons": ["image_ocr_requires_review"]},
        }

        fields = build_transport_record(document, [{"file_token": "file-token"}])

        self.assertEqual(fields["报销类型"], "🚄 交通报销")
        self.assertEqual(fields["票据号码"], "25339190041005476782")
        self.assertEqual(fields["购票主体"], "Fudan")
        self.assertEqual(fields["车次"], "G240")
        self.assertEqual(fields["票据附件"][0]["file_token"], "file-token")
        self.assertEqual(fields["是否复核"], "是")

    def test_build_expense_record_maps_first_line_item_and_json(self) -> None:
        document = {
            "doc_id": "doc-expense",
            "document_type": "conference_fee",
            "source_file_name": "invoice.pdf",
            "extraction": {
                "document": {
                    "invoice_number": "24112000000114409809",
                    "issue_date": "2024-08-26",
                    "amount": 5570.80,
                    "currency": "CNY",
                },
                "buyer": {"name": "Fudan", "tax_id": "12100000425006117P"},
                "seller": {"name": "Vendor", "tax_id": "911111111111111111"},
                "line_items": [
                    {
                        "item_name": "会议费",
                        "quantity": 1,
                        "unit_price": 5515.64,
                        "line_amount": 5515.64,
                        "tax_rate": "1%",
                        "tax_amount": 55.16,
                    },
                    {
                        "item_name": "服务费",
                        "quantity": 1,
                        "unit_price": 10.00,
                        "line_amount": 10.00,
                        "tax_rate": "0%",
                        "tax_amount": 0.00,
                    },
                ],
            },
            "validation": {"status": "warning"},
            "review": {"needs_review": False, "reasons": []},
        }

        fields = build_expense_record(document, [{"file_token": "file-token"}])

        self.assertEqual(fields["报销类型"], "🧾 费用报销")
        self.assertEqual(fields["项目名称"], "会议费")
        self.assertEqual(fields["税率"], 0.01)
        self.assertNotIn("项目明细JSON", fields)

    def test_sync_skill_result_to_bitable_supports_dry_run(self) -> None:
        settings = BitableSettings(
            enabled=True,
            dry_run=True,
            endpoint="https://open.feishu.cn",
            batch_size=200,
            mode="user_identity",
            include_attachments=False,
            app_id="app_id",
            app_secret="app_secret",
            app_token="app_token",
            transport_table_id="transport_table",
            expense_table_id="expense_table",
        )
        skill_result = {
            "documents": [
                {
                    "doc_id": "doc-rail",
                    "document_type": "transportation_fee",
                    "source_file_name": "ticket.jpg",
                    "extraction": {
                        "document": {"invoice_number": "123", "amount": 87.0, "currency": "CNY"},
                        "buyer": {"name": "Fudan", "tax_id": "tax"},
                        "travel": {"transport_number": "G240"},
                        "passenger": {"name": "Lemon"},
                    },
                    "validation": {"status": "pass"},
                    "review": {"needs_review": False, "reasons": []},
                },
                {
                    "doc_id": "doc-expense",
                    "document_type": "conference_fee",
                    "source_file_name": "invoice.pdf",
                    "extraction": {
                        "document": {
                            "invoice_number": "456",
                            "issue_date": "2024-08-26",
                            "amount": 100.0,
                            "currency": "CNY",
                        },
                        "buyer": {"name": "Fudan", "tax_id": "tax"},
                        "seller": {"name": "Vendor", "tax_id": "tax2"},
                        "line_items": [{"item_name": "会议费"}],
                    },
                    "validation": {"status": "warning"},
                    "review": {"needs_review": True, "reasons": ["manual_review"]},
                },
            ]
        }

        summary = sync_skill_result_to_bitable(skill_result, settings)

        self.assertEqual(summary["status"], "dry_run")
        self.assertEqual(summary["tables"]["transport"]["records_prepared"], 1)
        self.assertEqual(summary["tables"]["expense"]["records_prepared"], 1)
        self.assertEqual(summary["tables"]["transport"]["preview"][0]["报销类型"], "🚄 交通报销")


if __name__ == "__main__":
    unittest.main()
