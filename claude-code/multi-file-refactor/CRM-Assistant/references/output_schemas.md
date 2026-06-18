# 输出结构说明

当前项目的核心输出，是一组稳定的 CRM JSON 产物，以及两张飞书表的写入对象。

---

## 1. 核心输出文件

主处理流程通常会输出这些文件：
- `crm_packet.json`
- `meeting_record.json`
- `customer_profile_update.json`
- `opportunity_update.json`
- `follow_up_task.json`
- `pre_meeting_brief.json`
- `customer_table_rows.json`
- `opportunity_snapshot_row.json`

兼容旧版本时，也可能看到：
- `customer_table_row.json`
- `customer_profile_updates.json`

其中当前更应优先关注的是：
- `customer_table_rows.json`：支持多客户场景
- `opportunity_snapshot_row.json`：本轮商机快照

---

## 2. `crm_packet.json`

总包对象，用于汇总所有下游结果。

常见内容：
- `input`
- `meeting`
- `customer_profile_update` 或 `customer_profile_updates`
- `opportunity_update`
- `follow_up_task`
- `pre_meeting_brief`
- `customer_table_row` 或 `customer_table_rows`
- `opportunity_snapshot_row`
- `feishu_bitable_payload`

说明：
- 单客户老样本里可能还是 `customer_table_row`
- 多客户链路里会更常见 `customer_table_rows`

---

## 3. `meeting_record.json`

会议维度输出，用来表达本次会议本身的结构化结果。

常见字段：
- `meeting_id`
- `customer_id`
- `customer_name`
- `company_name`
- `meeting_time`
- `summary`
- `discussion_points`
- `customer_needs`
- `customer_concerns`
- `next_actions`
- `commitments`

---

## 4. `customer_profile_update.json`

客户画像增量结果。

常见字段：
- `customer_id`
- `company_name`
- `industry`
- `mbti`
- `single_status`
- `resistance_level`
- `price_sensitivity`
- `risk_concerns`
- `communication_style`
- `profile_summary`

说明：
- 这是“模型/规则理解结果”层，不等于最终写入飞书前的最终合并结果
- 真正写 客户信息表前，还会应用“弱值保护”和字段合并规则

---

## 5. `opportunity_update.json`

商机评估结果。

常见字段：
- `opportunity_id`
- `opportunity_name`
- `opportunity_description`
- `sales_region`
- `business_value`
- `lead_score`
- `intent_level`
- `opportunity_stage`
- `high_value_flag`
- `recommended_action`
- `next_follow_up_at`
- `latest_progress`

### 当前阶段枚举
只允许以下 6 个值：
- `初次接触`
- `需求确认`
- `方案沟通`
- `推进中`
- `待成交`
- `已成交`

### 意向等级枚举
只允许：
- `low`
- `medium`
- `high`

---

## 6. `follow_up_task.json`

给销售负责人执行的跟进任务对象。

常见字段：
- `task_title`
- `owner`
- `due_at`
- `channel`
- `draft_message`
- `checklist`

---

## 7. `pre_meeting_brief.json`

会前简报对象。

常见字段：
- `next_meeting_at`
- `trigger_at`
- `headline`
- `opening_script`
- `key_points`
- `watchouts`
- `materials_to_prepare`

说明：
- 即使没有立刻触发提醒，也可以先生成这个结构
- 如果 `next_meeting_at` 为空，则通常不会继续做提醒动作

---

## 8. 客户信息写入对象

当前项目最终落飞书时，更应关注的是 客户信息的最终写入结果。

常见字段：
- `客户ID`
- `客户名称`
- `客户公司`
- `职务`
- `行业`
- `MBTI`
- `是否单身`
- `沟通风格`
- `成交阻力`
- `价格敏感程度`
- `风险顾虑`
- `客户画像摘要`
- `客户负责人`
- `最后更新时间`
- `数据来源`

### 写入规则
- 逻辑主键：客户身份 / `客户ID`
- 写入模式：`upsert`
- 弱值不覆盖强值：
  - `未明确`
  - `未知`
  - `待确认`
  - 空值
- 以下字段采用合并策略：
  - `沟通风格`
  - `风险顾虑`

---

## 9. `opportunity_snapshot_row.json`

写入飞书 商机快照表的一条快照记录。

常见字段：
- `商机ID`
- `客户ID`
- `客户名称`
- `客户公司`
- `机会名称`
- `商机描述`
- `当前阶段`
- `Lead Score`
- `意向等级`
- `高净值优先`
- `销售区域`
- `业务价值`
- `推荐动作`
- `最新进展`
- `下次跟进时间`
- `最近会议时间`
- `商机负责人`
- `数据来源`

### 写入规则
- 写入模式：`append`
- 每次会议一条新快照
- 不覆盖历史，保留推进轨迹

---

## 10. `feishu_bitable_payload`

这是 CRM 结果与飞书写表之间的桥梁对象。

固定两表结构：

### `customer_table`
- `mode`: `upsert`
- `key_field`: `客户ID`
- `key`: 当前客户 ID
- `update_fields`: 客户信息最终写入字段

### `opportunity_snapshot_table`
- `mode`: `append`
- `append_row`: 当前商机快照

---

## 11. 业务解释规则

- 客户信息表用于沉淀长期画像
- 商机推进快照表用于保留每轮会议后的状态切片
- `recommended_action` 应短、准、可执行
- `high_value_flag` / `高净值优先` 用于优先级判断，不等于正式分层标签
- 在没有明确证据时，不要用本轮弱结论覆盖长期客户已知信息
