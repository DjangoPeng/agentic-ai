# LLM 输出 Schema

大模型输出时，建议直接对齐以下结构：

```json
{
  "meeting": {
    "meeting_id": null,
    "customer_id": null,
    "customer_name": null,
    "company_name": null,
    "meeting_time": null,
    "summary": null,
    "discussion_points": [],
    "customer_needs": [],
    "customer_concerns": [],
    "next_actions": [],
    "commitments": []
  },
  "customer_profile_update": {
    "customer_id": null,
    "company_name": null,
    "industry": null,
    "mbti": null,
    "single_status": "未明确",
    "resistance_level": "未明确",
    "price_sensitivity": "未明确",
    "risk_concerns": [],
    "communication_style": [],
    "profile_summary": null
  },
  "opportunity_update": {
    "opportunity_id": null,
    "opportunity_name": null,
    "opportunity_description": null,
    "sales_region": null,
    "business_value": null,
    "lead_score": 0,
    "intent_level": "low",
    "opportunity_stage": "初次接触",
    "high_value_flag": false,
    "recommended_action": null,
    "next_follow_up_at": null,
    "latest_progress": null
  },
  "follow_up_task": {
    "task_title": null,
    "owner": null,
    "due_at": null,
    "channel": null,
    "draft_message": null,
    "checklist": []
  },
  "pre_meeting_brief": {
    "next_meeting_at": null,
    "trigger_at": null,
    "headline": null,
    "opening_script": null,
    "key_points": [],
    "watchouts": [],
    "materials_to_prepare": []
  }
}
```

## 字段补充说明

### `intent_level`
可选值：
- `low`
- `medium`
- `high`

### `opportunity_stage`
可选值：
- `初次接触`
- `需求确认`
- `方案沟通`
- `推进中`
- `待成交`
- `已成交`

### `channel`
建议值：
- `微信`
- `邮件`
- `飞书消息`

### `high_value_flag`
常见判定场景：
- 明显高价值客户
- 预算较高
- 客户价值高且推进明确
- 高净值客户或企业级重点商机

### `company_name`
表示客户所属公司、机构或主体名称。例如：
- 高网信息科技
- 陈氏家族办公室
- 华东智造集团

### `opportunity_name`
建议采用“客户名 + 项目/需求方向 + 阶段/范围”的简短命名方式。例如：
- 刘子航 - CRM 一期试点
- 陈思敏 - 美元资产配置方案沟通
- 张天成 - 华东工厂售后巡检试点

### `opportunity_description`
建议是一句业务化短描述，说明当前商机的推进状态。例如：
- 客户希望先以华北团队做一期试点，并要求与飞书多维表格协同。
- 客户已进入双方案对比阶段，重点关注流动性与合规路径。

### `sales_region`
优先来源：
1. context 中已有的区域信息
2. transcript 中提到的区域范围
3. 无法判断时返回 `null`

示例：
- 华北地区
- 华东地区
- 全国

### `business_value`
表示商机的业务价值，可以是：
- 预算金额
- 预计成交金额
- 金额区间

如果 transcript 只给出范围，也可以输出区间文本，例如：
- `80-120万`
- `50万以内`
- `约 100 万`
