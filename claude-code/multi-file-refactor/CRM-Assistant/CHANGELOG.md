# Changelog

### 输入换代：JSON → 飞书 DOCX 会议纪要

- 输入层从飞书原始 JSON 改造为飞书会议纪要 Word 文档（`.docx`），更贴近真实使用方式
- 新增 DOCX 解析与端到端 ingest（`ingest-docx-to-bitable`、`build-context-from-feishu-doc`），仅用标准库 `zipfile` + `xml`，保持零第三方依赖
- 商机 ID 跨会议连续性、客户字段弱值保护与"沟通风格/风险顾虑"合并规则增强
- 飞书写表新增字段类型转换（日期时间 → 毫秒时间戳）与用户权限写入路径
- 样本从 `assets/feishu_raw/*.json` 改为 `assets/meeting_docs/*.docx`（含中国平安龙虾盒子 5 轮推进）
- 脱敏：清除上游 README 中的真实 `app_token` / `table_id` / 客户数据

### 课程定制保留（在上游新版基础上重新施加）

- **中文表名**：`Customers → 客户信息`、`OpportunitySnapshots → 商机快照`，覆盖 README / 实验手册 / references / SKILL
- **用户权限写表**：实验手册第 6/7/8 步 prompt 明确要求使用用户权限（user identity），新增 403 Forbidden 速查条目
- **`.env.local` 约定**：还原带注释的 `.env.example`，与第 13/14 节统一（`cp .env.example .env.local`）
- **SKILL 位置**：保留 `skills/crm-assistant/SKILL.md`（上游在根目录）
- **README** 以四段式架构（接入→理解→判断→沉淀）为主线重写，接入段改为 DOCX，新增"商机 ID 继承规则"，客户信息表新增 `职务` 字段
- **实验手册** 保留课程 9 步结构，第 4–8 步改用 `ingest-docx-to-bitable`，第 8 步改为"多轮推进验证"展示历史强值保护与商机快照追加
