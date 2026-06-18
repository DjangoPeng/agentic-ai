# 输入结构说明

当前项目支持 4 类入口，但都会归一到同一套内部处理输入：
- `transcript.txt`
- `context.json`

也就是说，不管上游是飞书原始 JSON、飞书文档正文还是 DOCX，最终都会先转换成这两份内部输入，再进入核心处理链路。

---

## 1. 核心内部输入

这是 `python scripts/crm_assistant.py process-transcript` 直接消费的输入。

### 1.1 `transcript.txt`
会议转录正文。

要求：
- 纯文本
- 尽量保留说话人信息
- 可包含时间提示，但不是必需
- 不要求严格结构化，只要可读即可

### 1.2 `context.json`
业务绑定与基础上下文。

建议字段：
- `customer_id`
- `customer_name`
- `company_name`
- `owner`
- `industry`
- `opportunity_id`
- `meeting_time`
- `next_meeting_time`
- `sales_region`
- `channel`

补充说明：
- `current_stage` **不建议**在源输入中提前给定
- 当前阶段应优先根据会议内容推断，而不是由上游硬塞
- 如果已有历史 CRM 信息，建议通过 context 提供“绑定信息”，不要直接提供推理结论

---

## 2. 飞书会议原始 JSON 输入

对应入口：

```bash
python scripts/crm_assistant.py build-context-from-feishu \
  --raw-input-path ./raw.json \
  --output-dir ./runtime/your_case
```

或直接：

```bash
python scripts/crm_assistant.py ingest-feishu-raw-to-bitable \
  --raw-input-path ./raw.json \
  --output-dir ./runtime/your_case
```

推荐原始文件名：`feishu_meeting_raw.json`

### 2.1 顶层建议字段
- `source`
- `meeting`
- `participants`
- `transcript`
- `calendar`
- `crm_binding`

### 2.2 `meeting`
建议字段：
- `meeting_id`
- `title`
- `start_time`
- `end_time`
- `host_user_id`
- `meeting_url`
- `calendar_event_id`

### 2.3 `participants`
数组元素建议字段：
- `user_id`
- `name`
- `role`
- `company`
- `industry`

其中 `role` 常见值可为：
- `internal`
- `external`
- `guest`
- `host`

### 2.4 `transcript`
至少提供一种：
- `full_text`
- `segments`

如果是 `segments`，元素建议字段：
- `speaker`
- `text`
- `start_ms`
- `end_ms`

### 2.5 `calendar`
建议字段：
- `next_meeting_time`

### 2.6 `crm_binding`
这是“业务绑定补充层”，用于把飞书会议与 CRM 上下文关联起来。

建议字段：
- `customer_id`
- `customer_name`
- `company_name`
- `owner`
- `industry`
- `opportunity_id`
- `sales_region`

说明：
- `crm_binding` 用于补充客户、公司、负责人、商机等绑定信息
- 不建议在这里直接给 `current_stage`

### 2.7 转换关系

```text
feishu_meeting_raw.json
  -> transcript.txt
  -> context.json
  -> process-transcript
```

---

## 3. 飞书文档 Markdown 输入

对应入口：

```bash
python scripts/crm_assistant.py build-context-from-feishu-doc \
  --doc-markdown-path ./source_doc.md \
  --output-dir ./runtime/your_case/build
```

或直接：

```bash
python scripts/crm_assistant.py ingest-feishu-doc-to-bitable \
  --doc-markdown-path ./source_doc.md \
  --output-dir ./runtime/your_case
```

适用场景：
- 上游已经把飞书云文档正文导出为 Markdown
- 文档中通常包含会议基本信息、参会人、文字记录等分段内容

转换关系：

```text
feishu_doc_markdown.md
  -> feishu_meeting_raw.json
  -> transcript.txt
  -> context.json
  -> process-transcript
```

常见来源区块：
- `会议基本信息`
- `参会人员`
- `文字记录`

---

## 4. Word / DOCX 输入

对应入口：

```bash
python scripts/crm_assistant.py ingest-docx-to-bitable \
  --docx-path ./meeting.docx \
  --output-dir ./runtime/your_case
```

适用场景：
- 用户直接上传会议纪要 Word 文件
- 本地已有 DOCX 版会议记录

转换关系通常为：

```text
meeting.docx
  -> source_doc.md
  -> feishu_meeting_raw.json
  -> transcript.txt
  -> context.json
  -> process-transcript
```

---

## 5. LLM 输出回灌输入

如果“理解与判断”交给大模型，当前项目也支持把模型输出再转换回 CRM 结果。

对应命令：

```bash
python scripts/crm_assistant.py validate-model-output \
  --model-output-path ./model_output.json

python scripts/crm_assistant.py convert-model-output \
  --model-output-path ./model_output.json \
  --context-path ./context.json \
  --output-dir ./runtime/from_model/your_case
```

这条链路要求模型输出结构对齐 `references/llm_output_schema.md`。
