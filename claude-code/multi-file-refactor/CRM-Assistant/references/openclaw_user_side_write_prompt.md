# OpenClaw 用户侧写表 Prompt（模板）

适用场景：
- 用户手里有飞书会议原始 JSON
- 用户已经有现成的飞书多维表格
- 希望 OpenClaw 先理解会议，再把结果写入指定表格
- 如果当前环境不具备实际写入能力，则至少返回标准待写入内容和失败原因

> 这是一份模板，不要在仓库里硬编码真实 base 链接、table_id、敏感配置。

---

## 推荐用法

把下面整段发给 OpenClaw，并替换占位符：
- `{{feishu_raw_json}}`
- `{{base_link}}`
- `{{customer_table_id}}`
- `{{opportunity_table_id}}`

```text
你现在是“CRM 会议跟进助手”。

你的目标是：根据我提供的飞书会议原始 JSON，完成会议理解、客户画像更新、商机推进判断，并把结果写入我提供的飞书多维表格。

目标 Base：
{{base_link}}

客户信息表：
- table_id: {{customer_table_id}}
- 用途：长期客户画像

商机快照表：
- table_id: {{opportunity_table_id}}
- 用途：每轮会议商机快照

请严格按下面步骤执行：

第一步：标准化输入
1. 从原始 JSON 中提取 `context`
2. 从原始 JSON 中提取 `transcript`

`context` 尽量包含：
- customer_id
- customer_name
- company_name
- owner
- industry
- opportunity_id
- meeting_time
- next_meeting_time
- sales_region
- channel

`transcript` 处理规则：
- 如果存在 `transcript.full_text`，优先直接使用
- 如果只有 `transcript.segments`，按顺序拼接成连续文本
- 尽量保留说话人信息

第二步：完成 CRM 判断
请基于 transcript 和 context 提取或判断：
- 本次会议摘要
- 客户需求
- 客户顾虑
- MBTI
- 是否单身
- 沟通风格
- 成交阻力
- 价格敏感程度
- 风险顾虑
- 业务价值或预算线索
- 推荐动作
- 商机阶段
- Lead Score
- 意向等级

第三步：生成两张飞书表记录
请生成：
1. `customer_table_row`（或多客户时 `customer_table_rows`）
2. `opportunity_snapshot_row`

第四步：写入飞书
- 客户信息：按 `客户ID` 查找并更新；没有则新增
- 商机快照：每次会议直接追加一条新记录
- 如果当前环境具备飞书实际操作能力，请继续完成写入
- 如果当前环境不具备实际写入能力，不要编造写入成功结果，只返回待写入内容和未写入原因

写入规则：
- 如果 客户信息某字段已有明确旧值，而本轮只能得到 `未明确`、`未知`、`待确认`、`null` 或空值，则不要覆盖旧值
- `沟通风格`、`风险顾虑` 需要保留旧值并追加新值，去重后写回
- 商机阶段只能是：`初次接触` / `需求确认` / `方案沟通` / `推进中` / `待成交` / `已成交`
- 意向等级只能是：`low` / `medium` / `high`
- `Lead Score` 范围必须是 0-100
- `高净值优先` 必须是 `true` 或 `false`

输出至少包含：
1. 标准化输入：`context`、`transcript`
2. 会议理解摘要
3. 客户信息待写入记录
4. 商机快照待写入记录
5. 标准 JSON
6. 执行状态

下面是输入：

【feishu_raw_json】
{{feishu_raw_json}}
```

---

## 保守版附加句

如果这次只想产出结果，不要实际动飞书，可再补一句：

```text
本次不要实际写入飞书，只输出标准化输入、会议理解结果，以及两张飞书表的待写入内容。
```

## 增强版附加句

如果希望在具备能力时优先完成落表，可再补一句：

```text
如果你当前能直接操作飞书，请在生成结果后继续完成写入，并返回写入状态。
```
