# CLAUDE.md - Financial Automation

This is the Claude Code working guide for the **financial-automation** project.

---

## 📋 Project Overview

**Purpose**: 全自动财务报销票据识别与飞书 Bitable 同步系统

**Capabilities**:
- PDF/图片票据自动摄入
- OCR 文本提取（RapidOCR 本地模型）
- 结构化字段解析（发票号码、金额、日期、购销方、行程等）
- 规则校验（必填字段、置信度、合规性、去重）
- 飞书 Bitable 双向同步
- 票据附件自动上传

**Pipeline Flow**:
```
票据图片/PDF → OCR/原生文本抽取 → 结构化 → 校验 → 附件上传 → Bitable 创建/更新 → 回读确认
```

---

## 📁 Directory Structure

```
financial-automation/
├── config/
│   ├── app_config.yaml      # 应用主配置
│   └── rules.yaml          # 校验规则（业务人员可读）
├── src/
│   ├── skill_entry.py       # Skill 主入口，串起全链路
│   ├── ingest.py           # 文件摄入与过滤
│   ├── ocr_extract.py      # OCR 文本提取 + 字段解析
│   ├── validate.py         # 校验引擎
│   ├── sync_bitable.py     # 飞书 Bitable 同步（主逻辑）
│   ├── bitable_attachment_uploader.py  # 附件上传
│   ├── bitable_session_writer.py       # 写策略选择
│   ├── output_formatter.py # Skill 输出格式化
│   ├── main.py             # 配置加载
│   └── webhook.py          # Webhook 模式（可选）
├── scripts/
│   ├── run_skill_job.py    # 单文件/批量运行入口
│   └── get_user_access_token.py  # 获取飞书 User Token
├── tests/
│   └── test_smoke.py       # 冒烟测试（10+ 测试类）
├── skills/
│   └── financial-expense-automation/
│       └── SKILL.md        # OpenClaw Skill 定义
├── runtime/
│   ├── inbox/              # 输入目录
│   ├── output/             # 输出目录
│   ├── jobs/               # Job 隔离工作区
│   ├── models/rapidocr/    # OCR 模型
│   └── oauth/              # User Token 缓存
├── docs/
│   ├── scope.md
│   └── runbook.md
├── lesson13-lab.md         # 课程实验指南
├── .env.example            # 环境变量模板
├── requirements.txt
└── README.md
```

---

## 🚀 How to Run

### Local Test (No Feishu Config Needed)

```bash
cd financial-automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 单文件测试
python scripts/run_skill_job.py runtime/sample_run_input/hotel_invoice.pdf
```

### Run Tests

```bash
# 运行全部冒烟测试
python -m unittest tests.test_smoke

# 运行特定测试类
python -m unittest tests.test_smoke.OCRExtractSmokeTest
python -m unittest tests.test_smoke.BitableSyncSmokeTest

# 运行单个测试方法
python -m unittest tests.test_smoke.OCRExtractSmokeTest.test_parse_rail_ticket_fields
```

测试会在 `.tmp_tests/` 目录下创建临时文件，自动清理。

---

## 📊 Test Coverage

| Test Class | Coverage Area | Key Tests |
|---|---|---|
| `PathResolutionSmokeTest` | 配置路径解析 | 相对路径转绝对、环境变量覆盖 |
| `IngestSmokeTest` | 文件摄入 | 扩展名过滤、空文件跳过、临时文件过滤 |
| `OCRExtractSmokeTest` | OCR 解析 | 住宿费发票、会议费发票、火车票字段 |
| `ValidateSmokeTest` | 校验 | 必填字段缺失、合规状态、复核触发 |
| `FormatterSmokeTest` | 输出格式化 | Skill Document、Review Queue、Run Result |
| `SkillEntrySmokeTest` | 主流程 | Workspace 创建、附件物化、Job 运行 |
| `BitableAttachmentUploaderSmokeTest` | 附件上传 | 请求构建、Token 校验、字段组装 |
| `BitableWritePlanSmokeTest` | 写计划 | 附件 Token 注入、User Identity Handoff |
| `BitableSyncSmokeTest` | Bitable 同步 | 配置加载、字段映射、Dry Run |
| `BitableSessionWriterSmokeTest` | 写策略 | 空白行复用、Update/Create 选择 |
| `SyncBitableSmokeTest` | 同步集成 | 环境变量优先、映射验证、Dry Run |

---

## 🔗 Feishu Bitable Integration

### Key Files

| File | Responsibility |
|---|---|
| `src/sync_bitable.py` | 主同步逻辑、认证、字段映射、API 调用 |
| `src/bitable_attachment_uploader.py` | Bitable Context 附件上传 |
| `src/bitable_session_writer.py` | 写策略选择（空白行复用 vs 创建） |

### Two Sync Modes

1. **`user_identity` 模式（默认）**
   - 使用 User Access Token（OAuth 登录用户身份）
   - 附件通过 `bitable_context_upload_user_identity` 上传
   - 需要先运行 `python scripts/get_user_access_token.py` 获取 Token
   - Token 缓存在 `runtime/oauth/feishu_user_token.json`

2. **`app_identity` 模式**
   - 使用 Tenant Access Token（应用身份）
   - 通过 `FEISHU_APP_ID` + `FEISHU_APP_SECRET` 自动获取
   - 无需用户登录，但权限受应用范围限制

### Environment Variables

```bash
# 飞书应用凭证
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx

# Bitable 配置（从 URL 提取）
FEISHU_BITABLE_APP_TOKEN=xxx          # base/... 部分
FEISHU_BITABLE_TRANSPORT_TABLE=tbl_xxx  # 交通报销表 ID
FEISHU_BITABLE_EXPENSE_TABLE=tbl_xxx    # 费用报销表 ID
```

**How to extract IDs from URL**:
```
https://xxx.feishu.cn/base/<APP_TOKEN>?table=<TABLE_ID>&view=...
                                                      ↑
                                                提取 TABLE_ID（不要 &view=...）
```

### Dry Run Mode (Safety First)

```bash
# 在 .env.local 中设置
FEISHU_BITABLE_DRY_RUN=true

# 或通过 config/app_config.yaml
sync:
  bitable:
    dry_run: true
```

Dry Run 模式下：
- 不会真实调用飞书 API
- 会生成完整的写入计划预览
- 附件字段显示占位符：`🖼️ 原图已接收：filename.jpg`

### Field Mapping

**交通报销表** (`transportation_fee`):
- 报销类型 → 🚄 交通报销
- 票据号码 → invoice_number
- 金额 → amount
- 购票主体 → buyer_name
- 车次 → transport_number
- 出发站/到达站 → from_station/to_station
- 乘车日期 → travel_date (Unix 毫秒时间戳)
- 票据附件 → [{"file_token": "..."}]
- 校验状态 → ✅ 通过 / ⚠️ 待复核 / ❌ 异常
- 是否复核 → 是/否

**费用报销表** (`conference_fee`, `accommodation_fee`, etc.):
- 报销类型 → 🧾 费用报销
- 票据号码 → invoice_number
- 开票日期 → issue_date (Unix 毫秒时间戳)
- 金额 → amount
- 购买方/销售方名称 → buyer_name/seller_name
- 项目名称 → item_name (取第一个行项目)
- 数量/单价/税率 → quantity/unit_price/tax_rate
- 票据附件 → [{"file_token": "..."}]
- 校验状态、是否复核 → 同上

### Attachment Upload Strategy

```
附件路径列表
    ↓
build_bitable_attachment_upload_request()
    ↓
perform_bitable_attachment_upload()  # 逐个上传
    ↓
获取 file_tokens 列表
    ↓
build_attachment_field_value()  →  [{"file_token": "tok1"}, ...]
    ↓
注入 Bitable 记录的 "票据附件" 字段
```

**关键限制**: Bitable 附件必须先上传到 Bitable Context 获取 `file_token`，不能直接嵌入记录。

### Write Policy

优先策略：`update_first_blank_row_then_create`

1. 先读取表中所有记录
2. 查找 `doc_id` 字段为空的行
3. 找到则 **Update** 复用该行
4. 未找到则 **Create** 新记录

**Why**: 避免表行数无限增长，复用预填充的模板行。

---

## ⚙️ Configuration Reference

### `config/app_config.yaml`

```yaml
app:
  name: financial-automation
  env: dev
  timezone: Asia/Shanghai

paths:
  input_dir: runtime/inbox      # 批量输入目录
  output_dir: runtime/output    # 输出根目录
  runtime_dir: runtime          # 运行时文件根目录

ocr:
  engine: rapidocr              # rapidocr | api
  rapidocr:
    enabled: true
    model_root_dir: runtime/models/rapidocr
  api:
    enabled: false
    url: ""                     # 外部 OCR API 地址
    token_env: OCR_API_TOKEN

validate:
  rules_file: config/rules.yaml  # 校验规则文件

sync:
  bitable:
    enabled: true
    dry_run: false              # 生产环境设为 false
    endpoint: https://open.feishu.cn
    batch_size: 200
    include_attachments: true
    user_token_file: runtime/oauth/feishu_user_token.json
    app_id_env: FEISHU_APP_ID
    app_secret_env: FEISHU_APP_SECRET
    app_token_env: FEISHU_BITABLE_APP_TOKEN
    transport_table_id_env: FEISHU_BITABLE_TRANSPORT_TABLE
    expense_table_id_env: FEISHU_BITABLE_EXPENSE_TABLE

webhook:
  enabled: false
  port: 8008
  route: /webhook/feishu
  auto_sync_bitable: true
```

### `config/rules.yaml`

校验规则采用业务人员可读格式，包含：
- 必填字段定义（按费用类型区分）
- 最低置信度阈值
- 金额限制
- 合规严重级别映射
- 复核策略
- 去重策略
- 一致性检查（发票总额 vs 行项目求和）

---

## 🧩 Skill Contract

Skill 定义在 `skills/financial-expense-automation/SKILL.md`，输出格式：

```json
{
  "summary": {
    "documents_seen": 5,
    "documents_accepted": 3,
    "documents_pass": 2,
    "documents_for_review": 1
  },
  "highlights": {
    "review_queue_count": 1
  },
  "documents": [...],
  "review_queue": [...],
  "bitable_sync": {
    "status": "completed",
    "mode": "user_identity",
    "tables": {...}
  }
}
```

---

## 🚨 Common Issues & Troubleshooting

1. **Attachment upload fails with missing token**
   - Ensure User Token is cached: `ls runtime/oauth/`
   - Re-run: `python scripts/get_user_access_token.py`

2. **Bitable API returns 403 Permission Denied**
   - Check App has Bitable scopes enabled in Feishu Open Platform
   - Verify User has edit permission on the target table

3. **Date fields show wrong value**
   - Bitable expects Unix milliseconds timestamp (not seconds)
   - Check `build_transport_record()` and `build_expense_record()`

4. **Dry run works but real sync fails**
   - Verify environment variables are correctly loaded
   - Check `dry_run: false` in active config

---

## ✅ Success Criteria (Completion State)

A full successful run must satisfy **all** of:
1. ✅ Document OCR extraction succeeds
2. ✅ `attachment_upload_result.ok = true`
3. ✅ "票据附件" field gets real `file_token` values
4. ✅ Bitable create/update API returns success
5. ✅ Read-back confirms record exists with attachments visible

**Important**: `bitable_write_plan` is just an intermediate artifact, **NOT** completion.
