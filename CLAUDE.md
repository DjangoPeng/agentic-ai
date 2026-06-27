# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository shape

This is a documentation-heavy course repository for OpenClaw + Claude Code production practice. It is not one buildable application: each runnable lesson project has its own directory, virtualenv, runtime artifacts, and README.

Main areas:

- `openclaw-infra/`, `openclaw-im/`, `openclaw-models/`: deployment, IM integration, model/provider, security, and troubleshooting guides for OpenClaw.
- `openclaw-soul/`, `openclaw-heartbeat/`, `openclaw-skills/`: templates and examples for SOUL/AGENTS behavior files, Heartbeat/Cron automation, and SKILL.md authoring.
- `xhs-auto-publisher/`: Playwright-based Xiaohongshu publisher for authorized accounts, with human QR-login handoff and Lobster/Feishu notification payloads.
- `financial-automation/`: Python OCR/PDF extraction pipeline for invoices, validation, attachment upload, and Feishu Bitable write-back.
- `morning-newspaper/`: Python multi-source news collection pipeline with three LLM editorial gates, static dashboard generation, and Feishu delivery workflow.
- `CRM-Assistant/`: Python standard-library CLI that converts Feishu meeting raw data/transcripts into CRM assets and Feishu Bitable rows.
- `ai-quant-cli/`: Python CLI that parses A-share annual-report PDFs into structured financials; Claude Code itself performs the risk analysis (no LLM API in code), then scripts render charts and a single-page HTML investment report.
- `github-secret-auditor/`: OpenClaw Skill with no runnable code; it drives Claude Code over ACP to audit and remediate leaked secrets in an authorized GitHub repo, with OpenClaw handling review, commit/push, and the Feishu report.

No Cursor rules, `.cursorrules`, or GitHub Copilot instruction file are present at repository root.

## Common commands

There is no repo-wide build, lint, or test command. Work from the relevant subproject directory.

### Financial automation

```bash
cd financial-automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_skill_job.py runtime/sample_run_input/hotel_invoice.pdf
```

Run the available smoke test module:

```bash
cd financial-automation
python -m unittest tests.test_smoke
```

Run one test class or one test method:

```bash
python -m unittest tests.test_smoke.OCRExtractSmokeTest
python -m unittest tests.test_smoke.OCRExtractSmokeTest.test_parse_rail_ticket_fields
```

The smoke tests create temporary files under `financial-automation/.tmp_tests/`.

### Morning Newspaper

```bash
cd morning-newspaper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Local collection checks:

```bash
python scripts/collect_raw.py --dry-run
python scripts/collect_raw.py --skip-tavily
python scripts/enrich_content.py
```

Batch pipeline entry points:

```bash
python scripts/run_daily_pipeline.py
python scripts/run_daily_pipeline.py --skip-tavily
python scripts/run_daily_pipeline.py --rebuild-dashboard-only
python scripts/check_runtime_status.py
```

The full Skill workflow is staged. The three LLM result files must be generated between prepare/apply steps, rather than relying on `run_daily_pipeline.py` to invent them:

```bash
python3 scripts/collect_mailbox.py
python3 scripts/collect_raw.py
python3 scripts/enrich_content.py
python3 scripts/prepare_title_shortlist.py
# produce runtime/title_shortlist_result.json from runtime/title_shortlist_prompt.txt
python3 scripts/apply_title_shortlist.py
python3 scripts/prepare_draft_input.py
# produce runtime/draft_result.json from runtime/draft_prompt.txt
python3 scripts/apply_draft_results.py
python3 scripts/prepare_top10_ranking.py
# produce runtime/top10_ranking_result.json from runtime/top10_ranking_prompt.txt
python3 scripts/apply_top10_ranking.py
python3 scripts/build_dashboard.py
python3 scripts/check_runtime_status.py
```

Dashboard/debug commands:

```bash
./scripts/serve_dashboard_8510.sh
streamlit run scripts/dashboard_app.py
```

### CRM Assistant

```bash
cd CRM-Assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` is intentionally empty of third-party packages; the CLI currently uses the Python standard library.

Local validation without Feishu credentials:

```bash
python scripts/crm_assistant.py build-context-from-feishu \
  --raw-input-path assets/feishu_raw/pingan_longxiahezi_need_confirmation.json \
  --output-dir runtime/quick_start

python scripts/crm_assistant.py process-transcript \
  --transcript-path runtime/quick_start/transcript.txt \
  --context-path runtime/quick_start/context.json \
  --output-dir runtime/quick_start
```

Useful CLI checks:

```bash
python scripts/crm_assistant.py run-sample-tests
python scripts/crm_assistant.py run-feishu-pipeline-tests
python scripts/crm_assistant.py run-model-output-tests
```

Feishu write-back is available through `inspect-feishu-bitable`, `sync-feishu-bitable`, and `ingest-feishu-raw-to-bitable`; prefer `--dry-run` before real writes.

### XHS auto publisher

```bash
cd xhs-auto-publisher
pip install -r requirements.txt
python -m playwright install chromium
cp deploy/env.example .env
bash deploy/run_with_xvfb.sh
```

Cloud setup scripts documented by the project:

```bash
bash deploy/install_system_ubuntu.sh
bash deploy/bootstrap_project.sh
```

Direct CLI example:

```bash
python scripts/publish_xhs.py \
  --content examples/openclaw_business_content.json \
  --mode publish
```

This project is for authorized account publishing with human QR-login. Do not add CAPTCHA/slider bypass, bulk interaction, account farming, or unauthorized-account automation.

### OpenClaw infrastructure

Documented setup starts from:

```bash
cd openclaw-infra/scripts
chmod +x setup-openclaw.sh
./setup-openclaw.sh
```

Operational commands used in the docs:

```bash
systemctl status openclaw
journalctl -u openclaw -f
systemctl restart openclaw
openclaw config get gateway
openclaw dashboard --no-open
openclaw devices list
openclaw devices approve <request-id>
```

The infra docs assume OpenClaw Gateway remains bound to localhost and is exposed through Tailscale Serve. Do not change deployment examples to expose port `18789` publicly.

### AI Quant CLI

```bash
cd ai-quant-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_pipeline.py        # parse → figures → L4 analysis gate → HTML report
```

L4 risk analysis (`analysis/findings_<code>.json`) is produced by Claude Code itself, not by a script; the pipeline gates on it before building the report. See `ai-quant-cli/CLAUDE.md` for the DAG and data contract.

### GitHub Secret Auditor

No runnable code: this is an OpenClaw Skill driven via ACP, not a local CLI, so there is nothing to `pip install`. See `github-secret-auditor/README.md` and `github-secret-auditor/lesson19-lab.md` for the deploy → ACP handshake → orchestrated audit flow, and `github-secret-auditor/CLAUDE.md` for the Skill contract.

## Architecture notes

### Runtime and configuration pattern

Runnable subprojects generally keep checked-in configuration in `config/`, user secrets in `.env` or `.env.local`, and generated artifacts under `runtime/`. Runtime outputs are part of the lesson workflows and are often inspected manually, but should not be treated as source files unless an example fixture is explicitly tracked.

### Skill contracts

Several projects include OpenClaw Skill definitions:

- `xhs-auto-publisher/SKILL.md`
- `financial-automation/skills/financial-expense-automation/SKILL.md`
- `morning-newspaper/skills/morning-newspaper-assistant-skill/SKILL.md`
- `CRM-Assistant/skills/crm-assistant/SKILL.md`
- `openclaw-skills/examples/crypto-monitor/SKILL.md`
- `github-secret-auditor/skills/github-secret-auditor/SKILL.md`

When changing workflow behavior, update both the runnable scripts and the relevant Skill contract if the agent-facing process changes.

### Financial automation pipeline

The main orchestration is `financial-automation/src/skill_entry.py`. The flow is:

1. Materialize uploaded attachments into a job workspace.
2. Ingest supported PDF/image documents.
3. Extract native PDF text or OCR text, then parse invoice fields.
4. Validate required fields, confidence, compliance, deduplication, and review status using `config/rules.yaml`.
5. Format Skill output and prepare Feishu Bitable records.
6. Upload attachments into Bitable context before writing attachment fields.

`sync_bitable.py`, `bitable_attachment_uploader.py`, and `bitable_session_writer.py` are the Feishu write-side modules; changes there can affect real external writes.

### Morning Newspaper pipeline

All intermediate files live in `morning-newspaper/runtime/`. The pipeline is intentionally linear: each stage consumes the previous stage’s file and the apply scripts validate freshness/matching to prevent stale LLM output from being reused.

Data flow:

```text
collect_mailbox / collect_raw → enrich_content → prepare_title_shortlist
→ title_shortlist_result.json → apply_title_shortlist → prepare_draft_input
→ draft_result.json → apply_draft_results → prepare_top10_ranking
→ top10_ranking_result.json → apply_top10_ranking → build_dashboard → check_runtime_status
```

Collectors live under `src/morning_newspaper/collectors/`; dashboard rendering is in `src/morning_newspaper/dashboard.py`; the architecture and cron delivery model are documented in `morning-newspaper/docs/architecture.md`.

### CRM Assistant pipeline

`CRM-Assistant/scripts/crm_assistant.py` is a single CLI with multiple subcommands. The intended business flow is:

```text
Feishu raw meeting data / transcript
→ build context.json + transcript.txt
→ extract customer/opportunity/follow-up/pre-meeting structures
→ convert to customer_table_row.json + opportunity_snapshot_row.json
→ upsert customer table + append opportunity snapshot table
```

Prompt/schema/few-shot assets are part of the implementation contract:

- `references/llm_prompt_template.md`
- `references/llm_output_schema.md`
- `assets/few_shot/`
- `references/feishu-bitable-mapping.md`

The CRM merge logic preserves historical strong values when the current meeting produces weak or missing values.

### XHS publisher flow

The publisher is a single-machine, single-browser, single-task sequence. Runtime evidence is written under `runtime/runs/<run_id>/`, with actions, normalized content, result JSON, screenshots, and DOM snapshots. Login handoff payloads are written under `runtime/lobster-notify/<run_id>/` for Feishu delivery by Lobster/OpenClaw.
