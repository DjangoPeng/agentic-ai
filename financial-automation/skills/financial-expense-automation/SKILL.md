---
name: financial-expense-automation
description: 当用户上传 PDF、JPG、JPEG、PNG 附件，或消息中包含"报销""发票""票据""录入""火车票""机票"等关键词时触发。对附件内容进行识别，若确认为报销票据则提取结构化字段并写入飞书多维表格；若识别后内容不是报销票据，告知用户并终止流程。
---

# Financial Expense Automation

## 目标

运行本地 Financial Automation 流水线，对用户上传的报销票据进行：
- 识别
- 结构化提取
- 校验
- 真实写入飞书多维表格

请始终记住：
- `bitable_write_plan` 只是中间产物
- 识别成功不等于任务完成
- 只有真实调用 Feishu Bitable `create/update` 成功，并完成回读确认，才算完成

## 项目依赖

这个 skill 依赖完整项目仓库，不能只拷贝 `SKILL.md` 单独使用。

按以下顺序定位项目根目录：
1. 环境变量 `FINANCIAL_AUTOMATION_ROOT`
2. `~/projects/agentic-ai/financial-automation`
3. `~/.openclaw/workspace/financial-automation`

若这些路径都不存在，应明确告诉用户：当前环境尚未部署完整项目仓库，请先完成部署。

主要入口与配置：
- `<repo_root>/src/skill_entry.py`
- `<repo_root>/config/app_config.yaml`

## 支持输入

附件输入格式：

```python
[
    {"file_name": "hotel_invoice.pdf", "content_bytes": b"..."},
    {"file_name": "ticket.jpg", "source_path": "/path/to/ticket.jpg"},
]
```

支持文件类型：
- `.pdf`
- `.jpg`
- `.jpeg`
- `.png`

若过滤后没有可处理附件，应直接告知用户：没有收到可处理的报销附件。

## 非报销内容处理

识别完成后，若内容不是报销票据（如普通图片、截图、合同等），应：
1. 告知用户：该附件不是可识别的报销票据
2. 简述识别到的内容类型
3. 终止流程，不继续写表

## 唯一入口

必须通过：

```python
from src.skill_entry import run_skill_job
result = run_skill_job(attachments)
```

如有需要可显式传配置：

```python
result = run_skill_job(
    attachments,
    config_path=f"{repo_root}/config/app_config.yaml",
)
```

不要手工拼接 ingest / OCR / validate / formatter 流程。

## 正式执行流程

1. 定位 repo root
2. 将用户上传文件整理成 `run_skill_job(...)` 所需的附件 payload
3. 调用 `run_skill_job(...)`
4. 使用返回的 `skill_result` 作为识别结果主对象
5. 生成真实写表输入
6. 若当前会话具备 Feishu Bitable 工具能力，继续执行真实写表
7. 写入后回读确认，再向用户回复结果

## 写表强制规则

1. `bitable_write_plan` 只是中间产物，不是最终结果
2. 只要当前会话可用飞书多维表格工具，就必须继续真实写表
3. 禁止停留在“建议写入 / 准备写入 / 可写入”状态
4. 只有真正调用 `create/update` 成功，才算完成
5. 如果没有真实写入成功，必须明确说明失败点
6. 禁止把“已识别 / 已生成 plan / 已生成 handoff”描述成已经完成落表

## 目标表路由规则

- `transportation_fee` → `交通报销表`
- 其他费用类票据 → `费用报销表`

## 写入策略

默认采用：
- `update_first_blank_row_then_create`

具体规则：
1. 先查询目标表
2. 若存在可复用空白行（优先判断 `doc_id` 为空），优先 `update`
3. 若不存在可复用空白行，再 `create`
4. 不要盲目追加新记录

## 附件写入规则

附件字段必须遵守以下规则：

1. 禁止直接使用通用 Drive upload token 作为 Bitable 附件
2. 必须先上传到当前 **bitable attachment context**
3. 再将返回的合法 `file_token` 写入附件字段
4. 图片走 `bitable_image`
5. PDF/其他文件走 `bitable_file`

### 降级规则

如果当前环境附件链路不可用：
- 不要伪造 `file_token`
- 不要把通用 Drive token 冒充 bitable 附件
- 可以先真实写入非附件字段
- 并明确告诉用户：附件尚未成功挂载

注意：
- 如果附件失败但非附件字段已落表，必须把两件事分开说清楚
- 如果连真实 `create/update` 都没发起，也必须明确说明尚未完成真实写表

## PDF / 图片识别规则

- 图片走 OCR
- PDF 优先走原生文本抽取
- 如果 PDF 原生抽取结果不足或不可用，应继续走 OCR fallback
- 不能因为某个提取分支失败就直接把整单描述成“不可识别”

## 返回对象重点字段

最重要字段：
- `user_summary`
- `summary`
- `highlights`
- `documents`
- `review_queue`
- `job`
- `bitable_write_plan`

说明：
- `documents` 是标准化结构化结果
- `review_queue` 表示需要人工复核的项目
- `bitable_write_plan` 是真实写表的中间输入，不是完成态

## 完成标准

以下情况才算完成：
- 已成功识别票据
- 已成功判断目标表
- 已真实调用 Feishu Bitable `create/update`
- 已明确回读或确认写入结果

以下情况都不算完成：
- 只输出结构化字段
- 只输出 `bitable_write_plan`
- 只说“待写入 / 准备写入 / 建议写入”
- 只生成 handoff/prompt 但没有真实 create/update

## 回复用户规则

回复用户时：
1. 先用 `user_summary.headline` 概括结果
2. 若有 `review_queue`，明确列出复核项与原因
3. 发票场景总结购方、销方、金额、项目名称等关键字段
4. 火车票场景总结购买方、路线、日期、乘客、席位等关键字段
5. 不要只汇报识别结果，必须汇报真实写表结果，或明确失败点

## 当前业务范围

当前优先支持：
- 普通电子发票
- 铁路电子客票

重点提取字段包括：
- 发票号码
- 开票日期
- 金额
- 币种
- 购方与销方信息
- 行项目 / 税率 / 税额
- 铁路票路线 / 车次 / 乘客 / 出行日期 / 席位
- 校验结论与复核原因
