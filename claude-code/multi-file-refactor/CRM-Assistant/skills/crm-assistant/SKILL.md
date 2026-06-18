---
name: crm-assistant
description: 将销售会议 transcript、飞书会议原始 JSON、飞书云文档正文或 Word/DOCX 会议纪要，转换成 CRM 结构化结果，并按客户信息表 + 商机推进快照表两表模型生成/同步飞书多维表格记录时使用。适用于多轮客户推进、客户画像增量更新、商机阶段判断、Lead Score 计算，以及“弱值不覆盖旧值、沟通风格/风险顾虑合并”的客户字段更新规则。
---

# CRM Assistant

在销售会议已经有可读文本后使用本 Skill。当前项目已经收敛为一个 Python CLI：`scripts/crm_assistant.py`。

## 这个 skill 负责什么

把以下任一输入：
- `transcript.txt + context.json`
- 飞书会议原始 JSON
- 飞书云文档导出的会议正文
- Word / DOCX 会议纪要

转换成：
- `meeting_record.json`
- `customer_profile_update.json`
- `opportunity_update.json`
- `follow_up_task.json`
- `pre_meeting_brief.json`
- `customer_table_rows.json`
- `opportunity_snapshot_row.json`
- `crm_packet.json`
- 在具备凭据时，进一步写回飞书多维表格

## 当前项目的关键业务规则

### 1. 固定两表模型
- 客户信息（长期客户画像，按客户身份 upsert）
- 商机快照（每次会议一条快照，保留推进轨迹）

### 2. 客户信息更新规则
对 客户信息的所有字段统一执行：
- 如果本轮值是弱值（如 `未明确` / `未知` / `待确认` / 空值），不要覆盖旧的明确值
- 如果本轮值是新的明确判断，允许更新旧值
- `沟通风格`、`风险顾虑` 采用合并策略：保留旧值并追加新值，去重后写回

### 3. 当前已知注意点
- 项目已经支持 DOCX 直连入口与飞书多维表格同步
- 同一客户多轮推进时，客户信息做增量更新，商机快照表持续追加
- 同一项目不同阶段应优先沿用同一个商机ID，不要每轮都新建商机
- `机会名称` 应优先采用 `客户公司 - 项目主题`，不要把联系人姓名列表拼到最前面

## 优先命令

### A. 直接处理 Word / DOCX 并写 CRM 结果
```bash
python ./scripts/crm_assistant.py ingest-docx-to-bitable \
  --docx-path ./meeting.docx \
  --output-dir ./runtime/your_case
```

### B. 从飞书会议原始 JSON 提取并落 CRM
```bash
python ./scripts/crm_assistant.py ingest-feishu-raw-to-bitable \
  --raw-input-path ./raw.json \
  --output-dir ./runtime/your_case
```

### C. 从飞书云文档正文落 CRM
```bash
python ./scripts/crm_assistant.py ingest-feishu-doc-to-bitable \
  --doc-markdown-path ./source_doc.md \
  --output-dir ./runtime/your_case
```

### D. 仅做规则处理（已有 transcript + context）
```bash
python ./scripts/crm_assistant.py process-transcript \
  --transcript-path ./transcript.txt \
  --context-path ./context.json \
  --output-dir ./runtime/your_case/process
```

## 需要写回飞书时
如果当前环境具备飞书 app 凭据，可在 ingest 命令上追加同步参数，例如：
- `--sync-feishu`
- `--app-token-or-url`
- `--customer-table-id`
- `--opportunity-table-id`
- 以及 app 凭据来源（显式参数、配置文件或环境变量）

若当前环境没有凭据：
- 先完成 CRM 结构化产物生成
- 再返回待写入内容，或由具备飞书工具能力的一侧执行写表

## 按需读取的参考资料
仅在需要时再读：
- `references/input_schemas.md`
- `references/output_schemas.md`
- `references/feishu-bitable-mapping.md`
- `references/llm_prompt_template.md`
- `references/llm_output_schema.md`
- `references/openclaw_user_side_write_prompt.md`
- `references/user_side_feishu_prompt.md`

## 自检建议
在修改脚本或规则后，至少做一项：
```bash
python ./scripts/crm_assistant.py --help
python ./scripts/crm_assistant.py run-sample-tests
python ./scripts/crm_assistant.py run-feishu-pipeline-tests
```

补充：
- 当前仓库默认不保留 `assets/samples/`，因此 `run-sample-tests` 无样本时会直接跳过
- 如果要跑真实样本回归，请先补回脱敏样本与断言文件

## 输出要求
优先保证：
- 中文业务摘要短而准
- 阶段判断、Lead Score、下次动作可解释
- 飞书字段名和当前表结构一致
- 不要让弱值覆盖长期客户已知信息
- 沟通风格 / 风险顾虑按合并策略处理
