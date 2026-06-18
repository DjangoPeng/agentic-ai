# 第 15 节 实验手册：让每一场高价值会议，自动沉淀为可经营的 CRM 资产

> 配套课程：AI 业务流架构师 · 第 15 节《实战：让每一场高价值会议，自动沉淀为可经营的 CRM 资产》
> 预计耗时：45–75 分钟（含飞书多维表格创建与应用配置）
> 操作方式：全程在飞书 DM 里和龙虾对话完成，不需要登录服务器
> 前置条件：OpenClaw 已部署 + 飞书已集成（第 2–4 节内容）

---

## 0. 开始前确认

| # | 物料 | 备注 |
|---|---|---|
| 1 | 龙虾可正常对话 | 飞书 DM 发一句话能回复 |
| 2 | 飞书开发者应用 | 有 App ID / App Secret，并已开通多维表格相关权限（读权限即可，写表走用户权限） |
| 3 | 飞书多维表格 | 可以新建，也可以沿用已有 CRM Demo Base |
| 4 | 课程仓库已 clone | `~/projects/agentic-ai` 存在且可 `git pull` |
| 5 | 一份飞书会议纪要 | 仓库自带 `assets/meeting_docs/*.docx`，不用自己准备 |

> 本实验只走主线：**飞书会议纪要（Word/DOCX）→ CRM Assistant → 飞书客户信息、商机快照两张表**。飞书写表统一使用**用户权限**完成。

---

## 1. 创建飞书多维表格（发给龙虾）

在飞书 DM 里发送以下消息：

```text
请帮我在飞书中创建一个用于 CRM Assistant Demo 的多维表格 Base。

要求：
1. 新建一个 Bitable
2. 创建两张表：客户信息、商机快照
3. 字段名称必须和下面完全一致，先全部按文本字段创建；Lead Score 可用数字字段，高净值优先可用复选框字段，时间字段可用日期时间字段

客户信息字段：
客户ID、客户名称、客户公司、行业、职务、MBTI、是否单身、沟通风格、成交阻力、价格敏感程度、风险顾虑、客户画像摘要、客户负责人、最后更新时间、数据来源

商机快照字段：
商机ID、客户ID、客户名称、客户公司、机会名称、商机描述、当前阶段、Lead Score、意向等级、高净值优先、销售区域、业务价值、推荐动作、最新进展、下次跟进时间、最近会议时间、商机负责人、数据来源

创建完成后请给我：
1. Base 链接
2. app_token
3. 客户信息的 table_id
4. 商机快照的 table_id
```

龙虾会返回 `app_token` 和两张表的 `table_id`，先记下来，后面配置会用到。

---

## 2. 部署项目（发给龙虾）

在飞书 DM 里发送以下消息：

```text
请帮我初始化 CRM-Assistant 项目环境。

仓库已克隆在 ~/projects/agentic-ai，项目在仓库的 CRM-Assistant/ 子目录。

要求：
1. 在 ~/projects/agentic-ai 执行 git pull，拉取最新代码
2. 进入 CRM-Assistant/ 子目录
3. 创建 Python 虚拟环境 .venv（如已存在跳过）
4. 安装 requirements.txt
5. 从 .env.example 复制出 .env.local（如已存在跳过）
6. 确认仓库里存在 assets/meeting_docs 目录，并且里面有 .docx 测试会议纪要
7. 确认 CRM-Assistant 的命令行入口可以正常打开帮助信息

完成后告诉我：
- git pull 是否成功（有无新的提交拉下来）
- .venv 虚拟环境是否已新建或确认可用
- 依赖是否安装成功
- .env.local 是否已存在或已创建
- assets/meeting_docs 下有哪些 .docx 文件
- CRM-Assistant 的帮助信息是否能正常输出
```

龙虾完成后你会收到部署确认。

---

## 3. 配置环境（发给龙虾）

> **⚠️ 发送前先自己填好真实值，不要把占位符发出去。**
> - `FEISHU_APP_ID` / `FEISHU_APP_SECRET`：飞书开放平台 → 应用详情页获取
> - `FEISHU_BITABLE_APP_TOKEN`：第 1 步龙虾返回的 `app_token`
> - `FEISHU_CUSTOMER_TABLE_ID`：客户信息的 `table_id`
> - `FEISHU_OPPORTUNITY_TABLE_ID`：商机快照的 `table_id`

把你的真实值替换进去，发送：

```text
请把 ~/projects/agentic-ai/CRM-Assistant/.env.local 配成：

FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxx
FEISHU_BITABLE_APP_TOKEN=xxxxxxxx
FEISHU_CUSTOMER_TABLE_ID=tblxxxxxxxx
FEISHU_OPPORTUNITY_TABLE_ID=tblxxxxxxxx

要求：
1. .env.local 只保存在本地，不要提交到 git
2. 写完后确认文件存在
3. 不要在回复里完整展示 FEISHU_APP_SECRET
```

---

## 4. 本地样本验证（发给龙虾）

先跑一遍不接飞书的本地链路，确认 CRM 结构化结果可以生成：

```text
请用 CRM-Assistant 项目跑一次本地样本验证。

项目目录：~/projects/agentic-ai/CRM-Assistant

请使用仓库自带的 Word 会议纪要 assets/meeting_docs/中国平安龙虾盒子需求梳理会.docx，执行 ingest-docx-to-bitable，把它解析成 context 和 transcript，再继续生成 CRM 结构化结果。

这一步不要加 --sync-feishu，只做本地处理，不要写入飞书。输出目录请放在 runtime/lab15_probe/ 下面，方便后续继续使用。

执行完后告诉我：
1. 是否生成 source_doc.md、context.json 和 transcript.txt
2. 是否生成 crm_packet.json
3. 是否生成 customer_table_rows.json 和 opportunity_snapshot_row.json
4. 当前商机阶段、Lead Score、意向等级、推荐动作分别是什么
```

> **⚠️ 注意**：这一步只验证本地结构化处理。`ingest-docx-to-bitable` 不带 `--sync-feishu` 时不会写飞书。确认 `crm_packet.json` 和两张表行文件都有内容即可继续。

---

## 5. 检查飞书表结构（发给龙虾）

```text
请用 CRM-Assistant 检查飞书多维表格结构。

项目目录：~/projects/agentic-ai/CRM-Assistant

请先加载 .env.local，然后用 inspect-feishu-bitable 命令的 --app-id、--app-secret、--app-token-or-url 参数传入对应的环境变量值。

检查结果请保存到 runtime/lab15_feishu/ 下面。

完成后告诉我：
1. 是否能拿到 tenant_access_token
2. 是否能列出两张表
3. 客户信息字段是否完整
4. 商机快照字段是否完整
5. 如果字段缺失，请列出缺失字段
```

如果这里失败，先不要继续写表，优先检查 App ID / App Secret、应用权限、Base 链接和 table_id。

---

## 6. 模拟写表验证（发给龙虾）

dry-run 会生成写表计划，但不会真实写入飞书。

> **⚠️ 飞书写表必须使用用户权限（user identity）。** 应用权限（app/bot identity）通常只有读权限，写操作会返回 403 Forbidden。后续第 7、8 步同理。

```text
请用 CRM-Assistant 做一次飞书写表 dry-run。

项目目录：~/projects/agentic-ai/CRM-Assistant

请使用 assets/meeting_docs/中国平安龙虾盒子需求梳理会.docx 和项目根目录的 .env.local，执行 ingest-docx-to-bitable，并加上 --sync-feishu --dry-run。飞书写表请使用用户权限（user identity），不要使用应用权限。这一步只生成写表计划，不要真实写入飞书。输出结果请保存到 runtime/lab15_feishu/dry_run。

执行完后告诉我：
1. feishu_sync_result.json 是否已生成
2. dry_run 是否为 true
3. customer_action 和 opportunity_action 是否都是 preview_only
4. 待写入的客户名称、机会名称、当前阶段、Lead Score、推荐动作分别是什么
```

> **⚠️ 注意**：看到 `feishu_sync_result.json` 不代表已经写入飞书。只有去掉 `--dry-run` 后才会真实写入。

---

## 7. 真实落表验证（发给龙虾）

确认第 5 步表结构正确、第 6 步 dry-run 正常后，再执行真实写入：

```text
请用 CRM-Assistant 把本次 CRM 结果真实写入飞书多维表格。

项目目录：~/projects/agentic-ai/CRM-Assistant

请使用 assets/meeting_docs/中国平安龙虾盒子需求梳理会.docx 和项目根目录的 .env.local，执行 ingest-docx-to-bitable，加上 --sync-feishu（这次不要加 --dry-run）。飞书写表请使用用户权限（user identity），不要使用应用权限：客户信息表按客户 ID 新增或更新，商机快照表追加一条商机推进快照。输出结果请保存到 runtime/lab15_feishu/write_once。

执行完成后告诉我：
1. 是否写入成功
2. 是否确认是用户侧写入
3. 客户信息是新增还是更新
4. 商机快照是否追加成功
5. 本次写入的客户名称、机会名称、当前阶段、Lead Score、意向等级、推荐动作
6. 如果失败，返回失败命令和完整报错
```

写入成功后，打开飞书多维表格确认两张表里都有记录。

---

## 8. 多轮推进验证（可选，发给龙虾）

同一客户跑第二份后续阶段文档，观察客户信息表如何"弱值不覆盖强值"地更新画像、商机快照表如何追加新阶段。

> **⚠️ 避免重复记录**：客户信息表按客户 ID 做 upsert，重复跑只会更新同一行；但商机快照表是 append，每跑一份文档追加一条。这正是用来展示推进轨迹的——但同一份文档不要重复跑。

```text
请用 CRM-Assistant 再处理一份同一客户的后续阶段会议纪要，并真实写入飞书。

项目目录：~/projects/agentic-ai/CRM-Assistant

请使用 assets/meeting_docs/中国平安龙虾盒子方案沟通会.docx 和项目根目录的 .env.local，执行 ingest-docx-to-bitable，加上 --sync-feishu。飞书写表继续使用用户权限（user identity）。输出结果请保存到 runtime/lab15_feishu/write_round2。

完成后告诉我：
1. 是否写入成功
2. 客户信息是否复用了已有客户并更新画像（是更新而非新增）
3. 商机快照是否在同一商机 ID 下追加了新阶段快照
4. 当前阶段、Lead Score、推荐动作和第一份文档相比有什么变化
```

回到飞书表观察：客户信息更新了画像、商机快照体现了"需求确认 → 方案沟通"的阶段推进。

---

## 9. 注册 Skill

### 9.1 拉取最新代码（发给龙虾）

```text
请在 ~/projects/agentic-ai 执行 git pull，拉取 CRM-Assistant 最新版本。
```

### 9.2 复制 Skill 目录（发给龙虾）

```text
请将 crm-assistant Skill 目录复制到 OpenClaw 的 skills 目录：

cp -r ~/projects/agentic-ai/CRM-Assistant/skills/crm-assistant \
  ~/.openclaw/workspace/skills/crm-assistant

完成后确认 ~/.openclaw/workspace/skills/crm-assistant/SKILL.md 已存在。
```

### 9.3 配置环境变量（发给龙虾）

```text
请在 ~/.openclaw/.env 中添加以下环境变量（文件不存在则新建）：

CRM_ASSISTANT_ROOT=~/projects/agentic-ai/CRM-Assistant

完成后确认该行已写入文件。
```

### 9.4 验证 Skill 是否生效（发给龙虾）

```text
请帮我处理这份飞书会议纪要，生成 CRM 结构化结果并用用户权限写入飞书表：
~/projects/agentic-ai/CRM-Assistant/assets/meeting_docs/国家电网分布式光伏并网资料协同需求确认会.docx
```

> 如果 Skill 注册成功，龙虾应自动触发 `crm-assistant`，走完接入 → 理解 → 判断 → 沉淀的完整链路。飞书两张表写入成功即完成第 9 步。

---

## 10. 验收检查清单

- [ ] 龙虾 git pull 并初始化 CRM-Assistant 成功
- [ ] `python scripts/crm_assistant.py --help` 能正常输出
- [ ] `assets/meeting_docs` 中存在 .docx 测试会议纪要
- [ ] 飞书 Base 已创建，包含客户信息和商机快照两张表
- [ ] `.env.local` 已配置真实 FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_BITABLE_APP_TOKEN / table_id
- [ ] 本地样本生成 `context.json`、`transcript.txt`、`crm_packet.json`
- [ ] 本地样本生成 `customer_table_rows.json` 和 `opportunity_snapshot_row.json`
- [ ] `inspect-feishu-bitable` 能读到两张表字段
- [ ] `ingest-docx-to-bitable --sync-feishu --dry-run` 生成写表计划但不真实写入
- [ ] 去掉 `--dry-run` 后通过用户权限真实写入成功
- [ ] 飞书客户信息表能看到客户画像记录
- [ ] 飞书商机快照表能看到商机推进快照记录
- [ ] Skill 已注册到 `~/.openclaw/workspace/skills/`
- [ ] 龙虾能通过 Skill 自动完成会议 → CRM 写入

---

## 11. 常见问题速查

| 龙虾报的错 | 原因 | 你发什么 |
|---|---|---|
| `Missing Feishu app token` | 没加载 .env.local 或变量名不对 | 「请检查 .env.local 里是否有 FEISHU_BITABLE_APP_TOKEN」 |
| `Missing customer table id` | 客户信息表 ID 缺失 | 「请检查 .env.local 里是否有 FEISHU_CUSTOMER_TABLE_ID」 |
| `Missing opportunity snapshot table id` | 商机快照表 ID 缺失 | 「请检查 .env.local 里是否有 FEISHU_OPPORTUNITY_TABLE_ID」 |
| `tenant_access_token missing` | App ID / App Secret 错误或应用未发布 | 「请重新核对 .env.local 里的 FEISHU_APP_ID / FEISHU_APP_SECRET」 |
| `403 Forbidden` / 写表失败 | 使用了应用权限，应用身份无写权限 | 「飞书写表请使用用户权限（user identity），不要使用应用权限」 |
| `Feishu API failed` | 权限、表 ID 或字段类型不匹配 | 「请返回完整报错，并重新执行 inspect-feishu-bitable」 |
| 字段缺失 | 建表时字段名和脚本字段不一致 | 「请按实验手册第 1 步补齐缺失字段，字段名保持完全一致」 |
| 找不到 .docx | 没拉到最新仓库，或路径不对 | 「请 git pull，并列出 assets/meeting_docs 下的文件」 |
| 只生成 JSON 没写表 | 没加 `--sync-feishu` 或带了 `--dry-run` | 「请确认执行的是 ingest-docx-to-bitable 且带了 --sync-feishu、没有 --dry-run」 |
| 客户信息被覆盖了旧画像 | 当前输入有弱值或历史值保护未生效 | 「请返回 crm_packet.json 和 feishu_sync_result.json 里 customer_table_rows 的内容」 |
| Skill 注册后龙虾没触发 | Skill 目录没复制到正确位置 | 「请确认 ~/.openclaw/workspace/skills/crm-assistant/SKILL.md 存在」 |
| 找不到项目目录 | 环境变量未配置 | 「请确认 ~/.openclaw/.env 中 CRM_ASSISTANT_ROOT 已设置」 |

---

## 实验记录

请记录你在实验过程中遇到的任何与预期不符的情况：

| # | 发生在哪一步 | 预期行为 | 实际行为 | 你的解决方法 |
|---|------------|----------|---------|------------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

> 欢迎把你的实验记录和踩坑发现分享到课程社群。
