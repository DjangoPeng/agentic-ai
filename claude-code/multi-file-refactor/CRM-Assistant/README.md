# CRM Assistant

> 配套课程：AI 业务流架构师 · 第 15 节《实战：让每一场高价值会议，自动沉淀为可经营的 CRM 资产》

把飞书会议纪要（Word/DOCX）经过四段式架构（接入 → 理解 → 判断 → 沉淀），转换成客户画像、商机推进判断、跟进任务与会前简报，最终写入飞书多维表格两张表。

```
飞书会议纪要（.docx）
  → 接入：从 Word 文档解析出 context.json + transcript.txt
  → 理解：从对话里提取需求、顾虑、MBTI、沟通风格等经营信号
  → 判断：生成阶段、Lead Score、意向等级、推荐动作
  → 沉淀：upsert 客户信息表 + append 商机快照表
```

## 与课程的关系

本项目是第 15 节的实战代码，服务于课程的三个核心留存物：

| 留存物 | 在本项目中的体现 |
|---|---|
| **四段式架构** | 接入（标准化输入）→ 理解（信号提取）→ 判断（策略生成）→ 沉淀（CRM 写入）——不是一个 Prompt，是一套业务能力 |
| **Prompt + Schema + few-shot 三件套** | `llm_prompt_template.md` 定判断标准 + `llm_output_schema.md` 约束输出结构 + 两份 few-shot 示例强化难点字段（MBTI、是否单身、风险顾虑） |
| **历史强值保护** | `merge_row_preserving_existing_values` —— 本轮弱值不覆盖历史强值，多轮画像越跑越准而非越跑越空 |

## 前置条件

| 条件 | 说明 |
|---|---|
| Python 3.10+ | 无第三方依赖，标准库即可运行（DOCX 解析用 `zipfile` + `xml`） |
| 飞书开发者应用 | 有 App ID / App Secret，已开通多维表格相关权限（读权限即可，写表走用户权限） |
| 飞书多维表格 | 包含客户信息和商机快照两张表 |

## 快速开始

```bash
# 1. 进入项目
cd CRM-Assistant

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖（标准库项目，requirements 为空占位）
pip install -r requirements.txt

# 4. 本地验证（不需要飞书配置）：把仓库自带的 Word 会议纪要跑成 CRM 结构化结果
python scripts/crm_assistant.py ingest-docx-to-bitable \
  --docx-path assets/meeting_docs/中国平安龙虾盒子需求梳理会.docx \
  --output-dir runtime/quick_start
```

不带 `--sync-feishu` 时只做本地结构化处理，不会写飞书。跑通即可掌握本节 80% 的内容。真实写表需要飞书配置，详见下方"飞书写表"章节或 [lesson15-lab.md](lesson15-lab.md)。

环境变量模板：

```bash
cp .env.example .env.local
# 填入真实值后：
set -a && source .env.local && set +a
```

## 四段式架构

### 第一段 · 接入：标准化输入

把飞书会议纪要 Word 文档解析成两个文件，让下游所有处理吃同一种"标准化输入"：

- `context.json`：客户 ID、商机 ID、负责人、会议时间、销售区域……
- `transcript.txt`（纯文本）：整段会议对话

```bash
python scripts/crm_assistant.py build-context-from-feishu-doc \
  --docx-path assets/meeting_docs/your_meeting.docx \
  --output-dir runtime/your_case
```

> 文档纪要要求三段结构：**一、会议基本信息 / 二、参会人员 / 三、文字记录**。仓库自带样本即按此格式组织。除了 Word 文档，项目也保留了从飞书会议原始 JSON（`build-context-from-feishu`）和飞书云文档正文（`build-context-from-feishu-doc --doc-markdown-path`）接入的入口。

### 第二段 · 理解：经营信号提取

从对话原文中提炼结构化经营信号：

- 客户画像：MBTI、是否单身、职务、沟通风格
- 风险顾虑：价格敏感、交付风险、合规与数据安全
- 决策角色：客户本人拍板？配偶参与？技术决策人引入？

### 第三段 · 判断：策略生成

把经营信号翻译成销售动作：

| 输出字段 | 示例值 | 经营含义 |
|---|---|---|
| 当前阶段 | 需求确认 | 这单走到哪了 |
| Lead Score | 82 | 推进成熟度（0-100） |
| 意向等级 | high | 飞书表快速筛选 |
| 推荐动作 | 补齐关键需求并推动方案 | 下一步该做什么 |
| 下次跟进 | 2026-05-21 15:00 | 什么时候约下次会 |

### 第四段 · 沉淀：写入飞书两张表

| 飞书表 | 写入方式 | 回答的问题 |
|---|---|---|
| 客户信息（长期画像） | upsert（同 ID 更新） | 这个客户是谁？该怎么跟他沟通？ |
| 商机快照（每轮追加） | append（每轮追加） | 这单现在在哪？下一步该怎么推？ |

## 核心模块

| 模块 | 职责 |
|---|---|
| `scripts/crm_assistant.py` | Python CLI 主入口，覆盖接入/理解/判断/沉淀完整链路 |
| `references/llm_prompt_template.md` | Prompt 模板：每个字段的判断标准、证据来源、边界条件 |
| `references/llm_output_schema.md` | Schema 约束：输出 JSON 结构、字段名、枚举值、类型 |
| `assets/few_shot/` | few-shot 示范：覆盖 MBTI、是否单身、风险顾虑等难点字段 |
| `assets/meeting_docs/` | 飞书会议纪要 Word 样本（含中国平安龙虾盒子 5 轮推进完整数据） |
| `references/feishu-bitable-mapping.md` | 飞书两表字段映射与写入规则 |
| `skills/crm-assistant/SKILL.md` | OpenClaw Skill 入口契约 |

## 8 类结构化产出

一次处理生成 8 类文件，每一类对应一个具体动作：

| 产出文件 | 回答什么 |
|---|---|
| `meeting_record.json` | 这次会谈了什么 |
| `customer_profile_update.json` | 客户是个什么样的人 |
| `opportunity_update.json` | 这单推进到哪一步了 |
| `follow_up_task.json` | 下一步该做什么 |
| `pre_meeting_brief.json` | 下次开会前看什么 |
| `customer_table_rows.json` | 直接写进飞书客户信息表 |
| `opportunity_snapshot_row.json` | 直接写进飞书商机快照表 |
| `crm_packet.json` | 以上全部打包 |

## 历史强值保护

多轮经营的核心难题：本轮没提到 ≠ 不存在。

```python
# 本轮弱值 + 历史强值 → 保留历史；沟通风格/风险顾虑则合并去重
def merge_row_preserving_existing_values(current_row, existing_fields):
    merged = OrderedDict()
    preserved_fields = []
    merge_fields = {"沟通风格", "风险顾虑"}
    for field_name, current_value in current_row.items():
        existing_value = (existing_fields or {}).get(field_name)
        if field_name in merge_fields and not is_weak(existing_value) and not is_weak(current_value):
            merged[field_name] = merge_multi_value_text(current_value, existing_value)  # 合并去重
        elif is_weak(current_value) and not is_weak(existing_value):
            merged[field_name] = existing_value                                          # 保留历史强值
            preserved_fields.append(field_name)
        else:
            merged[field_name] = current_value
    return merged, preserved_fields
```

弱值包括：`None`、空字符串、`"未明确"`、`"暂无"`、`"未知"`、`"待确认"`、`"待补充"`、空列表/字典。`沟通风格`、`风险顾虑` 两个字段额外采用"保留旧值 + 补充新值 + 去重"的合并策略。

## 商机 ID 继承规则

同一客户、同一项目、只是推进到不同阶段时，应**沿用同一个商机 ID**，在商机快照表追加新阶段快照；只有在以下情况才生成新商机 ID：

- 同一客户下的全新项目
- 不同预算包 / 不同采购线
- 已明确是另一条独立需求线

简记：**阶段变化 → 同一商机 ID，不同快照；新项目 → 新商机 ID。**

## 多轮客户推进

同一客户跨多轮会议持续推进，可查看阶段变化和得分轨迹：

```bash
python scripts/crm_assistant.py run-customer-journey \
  --manifest-path your_journey_manifest.json \
  --output-dir runtime/your_case_journey
```

仓库自带的中国平安龙虾盒子样本提供了完整 5 轮推进（需求梳理 → 方案沟通 → 内部推进 → 签约前确认 → 项目签约完成），可用来演示阶段与 Lead Score 的变化轨迹。

## 飞书配置

飞书凭证支持三种传入方式，优先级从高到低：CLI 参数 > `feishu_config.json` > 环境变量。

推荐使用环境变量（与第 13/14 节一致）：

```bash
cp .env.example .env.local
# 填入真实值后：
set -a && source .env.local && set +a
```

> `.env.local` 和 `feishu_config.json` 都已在 `.gitignore` 中，不会被误提交。两种方式不要混用。

## 飞书写表

> ⚠️ **飞书写表必须使用用户权限（user identity）。** 应用权限（app/bot identity）通常只有读权限，写操作会返回 `403 Forbidden`。应用凭证主要用于定位和检查 Base / 表结构。

### 检查表结构

```bash
python scripts/crm_assistant.py inspect-feishu-bitable \
  --app-id $FEISHU_APP_ID \
  --app-secret $FEISHU_APP_SECRET \
  --app-token-or-url $FEISHU_BITABLE_APP_TOKEN \
  --output-dir runtime/inspect
```

### dry-run 模拟写表

```bash
python scripts/crm_assistant.py ingest-docx-to-bitable \
  --docx-path assets/meeting_docs/中国平安龙虾盒子需求梳理会.docx \
  --output-dir runtime/dry_run \
  --sync-feishu --dry-run
```

### 真实写入

```bash
python scripts/crm_assistant.py ingest-docx-to-bitable \
  --docx-path assets/meeting_docs/中国平安龙虾盒子需求梳理会.docx \
  --output-dir runtime/write_once \
  --sync-feishu
```

> 不带 `--sync-feishu` 只做本地结构化；带 `--sync-feishu --dry-run` 生成写表计划但不真写；带 `--sync-feishu` 不带 `--dry-run` 才真实写入。

## 飞书表字段

### 客户信息表（长期画像）

客户ID、客户名称、客户公司、行业、职务、MBTI、是否单身、沟通风格、成交阻力、价格敏感程度、风险顾虑、客户画像摘要、客户负责人、最后更新时间、数据来源

### 商机快照表（商机推进快照）

商机ID、客户ID、客户名称、客户公司、机会名称、商机描述、当前阶段、Lead Score、意向等级、高净值优先、销售区域、业务价值、推荐动作、最新进展、下次跟进时间、最近会议时间、商机负责人、数据来源

## 完成标准

一次完整成功必须同时满足：

1. `context.json` 和 `transcript.txt` 已生成
2. `crm_packet.json` 包含 8 类结构化结果
3. `customer_table_rows.json` 弱值已被历史强值保护
4. 飞书客户信息表有客户画像记录（upsert 成功）
5. 飞书商机快照表有商机推进快照（append 成功）

## 目录结构

```
CRM-Assistant/
├── agents/
│   └── openai.yaml                              # Agent 配置
├── assets/
│   ├── meeting_docs/                            # 飞书会议纪要 Word 样本
│   │   ├── 中国平安龙虾盒子需求梳理会.docx
│   │   ├── 中国平安龙虾盒子方案沟通会.docx
│   │   ├── 中国平安龙虾盒子内部推进会.docx
│   │   ├── 中国平安龙虾盒子签约前确认会.docx
│   │   ├── 中国平安龙虾盒子项目签约完成与启动确认会.docx
│   │   ├── 国家电网分布式光伏并网资料协同需求确认会.docx
│   │   └── 上海宝武钢铁集团企业大模型微调服务初步了解会.docx
│   └── few_shot/                                # few-shot 示例
│       ├── zhongguoyidong_ops_rich.json
│       └── ningdeshidai_service_rich.json
├── references/
│   ├── llm_prompt_template.md                   # Prompt 模板（证据口径 + 判断标准）
│   ├── llm_output_schema.md                     # 输出 JSON Schema
│   ├── feishu-bitable-mapping.md                # 飞书两表字段映射
│   ├── input_schemas.md                         # 输入数据结构
│   ├── output_schemas.md                        # 输出数据结构
│   ├── openclaw_user_side_write_prompt.md       # 用户侧 Prompt（飞书写表）
│   └── user_side_feishu_prompt.md               # 用户侧 Prompt（完整说明）
├── runtime/                                     # 运行产物（git ignored）
├── scripts/
│   └── crm_assistant.py                         # Python CLI 主入口
├── skills/
│   └── crm-assistant/
│       └── SKILL.md                             # OpenClaw Skill 入口契约
├── .env.example                                 # 环境变量模板（飞书凭证 + Bitable 表配置）
├── lesson15-lab.md                              # 第 15 节实验手册
├── requirements.txt
└── README.md
```

## 相关课程章节

| 前置 | 内容 |
|---|---|
| 第 4 节 | 飞书原生深度集成（Bitable 基础操作） |
| 第 9 节 | SDL 语法与 Skill 开发（SKILL.md 编写） |
| 第 13 节 | 五步拆解心法与完成态公式 |
| 第 14 节 | 信号分诊 + 三关口编辑 → 早报管家 |

| 后续 | 复用 |
|---|---|
| 第 18 节 | 四段式架构 + 历史强值保护 → 量化投研 |
