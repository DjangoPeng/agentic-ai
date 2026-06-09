# Changelog

## 2026-06-09 Tavily 直连、来源多样性与流程稳定性修复

### Tavily REST API 直连

- `src/morning_newspaper/collectors/tavily.py`
  - 新增 `execute_tavily_plan()` 函数，直接调用 Tavily REST API（POST `https://api.tavily.com/search`），不再依赖外部 OpenClaw Skill 两步式执行
  - source_id 统一为 `tavily_search`，source_type 统一为 `tavily_api`
- `src/morning_newspaper/collectors/orchestrator.py`
  - collect 阶段自动调用 `execute_tavily_plan()`，有 API Key 时直接执行搜索
- `scripts/collect_raw.py`
  - 入口加载 `.env` 文件确保 `TAVILY_API_KEY` 可用
- `config/sources.yaml`
  - GitHub / HN 的 `max_items` 从 4 调高至 6，Tavily `max_items_per_topic` 从 5 降至 3，平衡各来源初始配额

### 来源多样性硬约束

- `scripts/apply_top10_ranking.py`
  - 新增 `_enforce_source_diversity()`：Tavily 最多占 Top10 的 50%，GitHub 和 HN 各至少 2 条
  - 砍掉超额 Tavily 后自动从已成稿候选中补入 GitHub/HN 条目（优先选 AI 相关标题）
  - 修复补位后总数不足 10 条的问题：加入 shortfall 填充逻辑，从剩余候选池补满

### 流程稳定性

- `scripts/apply_title_shortlist.py`
  - 修复致命 bug：`selected_map` 未定义导致 NameError 崩溃，补上 `ranked_titles` → `{title: rank}` 字典构建
  - mtime 校验：结果文件必须比输入文件新，否则拒绝执行
- `scripts/apply_draft_results.py`
  - mtime 校验：结果文件必须比输入文件新
- `scripts/apply_top10_ranking.py`
  - mtime 校验：结果文件必须比输入文件新

### 统一 runtime 目录

- `scripts/run_daily_pipeline.py`
  - 移除 `--results-dir` 参数和所有 `_validate_*` 函数
  - 所有文件统一读写 `runtime/` 目录，去掉 `runtime_results/` 依赖
- `scripts/cron_generate_morning_newspaper.py`
  - 移除 `--results-dir runtime_results` 参数

### Dashboard 时区修复

- `src/morning_newspaper/dashboard.py`
  - 更新时间从 UTC ISO 格式转为北京时间显示（`2026-06-09 14:03 CST`）

### SKILL.md 重写

- `skills/morning-newspaper-assistant-skill/SKILL.md`
  - 主流程从"直接执行 `run_daily_pipeline.py`"改为三阶段逐步执行 + 3 个 LLM 关口
  - 每个关口明确标注：必须读取当前 prompt、基于本轮输入生成结果、不能复用旧文件
  - 新增"防串轮次机制"说明 mtime 校验规则

### 实验手册微调

- `lesson14-lab.md`
  - Step 4 移除 `serve_dashboard_8510.sh` 执行（第 5 步才开放端口）
  - Step 9/10 将建议消息格式移入 prompt 块内

## 2026-06-08 早报稳定性修复与命名清理

### 流程一致性与结果隔离

- `scripts/run_daily_pipeline.py`
  - 新增结果文件一致性校验：`title_shortlist_result.json`、`draft_result.json`、`top10_ranking_result.json` 必须和本轮输入匹配，避免旧回填结果串轮次复用
  - 新增 `--results-dir` 参数，并默认改为从 `runtime_results/` 读取结果文件
  - apply 阶段显式传入结果文件路径，不再隐式依赖 `runtime/` 中的临时文件
- `scripts/cron_generate_morning_newspaper.py`
  - cron 调用改为显式走 `--results-dir runtime_results`
  - 失败归因可区分 `shortlist / draft / ranking / quality`，不再把串轮次问题误报成 collect
- 新增 `runtime_results/` 目录约定，用于隔离 LLM / 人工回填结果与正式运行时产物

### shortlist 策略增强

- `scripts/prepare_title_shortlist.py`
  - 标题粗筛 Prompt 增加来源多样性约束，避免单一来源占满候选池
  - 候选标题预去重，避免重复标题挤占 shortlist 配额
- `scripts/apply_title_shortlist.py`
  - shortlist 再按标题去重
  - 若 GitHub / Hacker News 被完全挤出，补入少量代表项，保证基础来源多样性

### draft / ranking 稳定性修复

- `scripts/apply_draft_results.py`
  - 增加当前输入匹配校验，避免旧 draft 结果直接套到新一轮输入
- `scripts/apply_top10_ranking.py`
  - 增加 ranking 结果和当前 `top10_ranking_input.json` 的一致性校验，避免旧 rank_id 混入

### 质量检查与交付标准调整

- `scripts/check_runtime_status.py`
  - 增加 `draft_input_count`、`ranking_input_count`、`shortlist_titles`、`drafted_titles`、`publishable_titles` 等诊断字段
  - 交付标准从“必须凑满 10 条”调整为“只要 publishable 非空、页面正常、无占位摘要即可交付”；若高质量候选不足 10 条，允许按实际 publishable 条数交付
- `README.md`
  - 同步更新 `runtime/` 与 `runtime_results/` 的职责说明
  - 明确 `Top10` 是发布目标上限，不是硬性凑数目标

### Tavily REST API 命名清理与发布时间补齐

- `config/sources.yaml`
  - 配置段从 `openclaw_tavily` 统一为 `tavily_search`
- `src/morning_newspaper/collectors/orchestrator.py`
  - Tavily source_id 统一为 `tavily_search`
- `src/morning_newspaper/collectors/tavily.py`
  - 展示命名从 `OpenClaw Tavily` / `tavily_skill` 统一为 `Tavily Search` / `tavily_api`
  - 保留对旧配置键的兼容读取
  - 记录 `published_date_raw` 以便排查上游返回
- `src/morning_newspaper/dashboard.py`
  - 图标逻辑兼容 `tavily_api`
- `src/morning_newspaper/content_fetch.py`
  - Tavily 条目若 API 未返回发布时间，会在抓正文时尝试从 HTML 元标签补齐
  - 若二次尝试仍拿不到，回退为 `fetched_at`
  - 即使正文抓取失败，也会回退为抓取时间，避免页面出现空发布时间


## 实验手册重写与 Skill 注册对齐

- `lesson14-lab.md` — 全文重写，对齐第 13 节 financial-automation 的飞书对话驱动模式：
  - 部署方式从 clone 独立仓库改为 `git pull` 课程仓库 + 进入子目录
  - 所有路径从 `/root/projects/Morning-Newspaper-Assistant` 统一为 `~/projects/agentic-ai/morning-newspaper`
  - 新增第 2 步环境变量配置（GitHub Token + Tavily API Key + IMAP）
  - 新增第 3 步采集验证（`--skip-tavily` 单步验证）
  - 新增第 7 步 Skill 注册（复制目录 + 配置 `MORNING_NEWSPAPER_ROOT`）
  - 移除所有 Morning-Newspaper-Manager 混用警告
- `SKILL.md` — 新增项目依赖段（三级路径查找），移除 Manager 引用和硬编码 IP

## 补充 Tavily 搜索配置文档

- `.env.example` — 新增 `TAVILY_API_KEY` 条目及注册说明
- `README.md` — 前置条件表新增 Tavily API Key，新增"Tavily 搜索配置"段（API Key、主题配置示例、不配置时的降级行为）

## 移除百度搜索采集器

移除 `cn_media_search` / `baidu_search` 相关的全部内容，本节课程不再使用该采集器。

### 删除文件

| 文件 | 说明 |
|---|---|
| `src/morning_newspaper/collectors/baidu_search.py` | 百度搜索子进程调用 |
| `src/morning_newspaper/collectors/cn_media.py` | 中文媒体搜索采集器 |

### 代码变更

- `collectors/orchestrator.py` — 移除 `cn_media` 导入和通道型采集器调度逻辑
- `scripts/collect_raw.py` — `--dry-run` 输出不再包含 `cn_media_search_enabled`
- `config/sources.yaml` — 移除 `cn_media_search` 配置段

### 文档变更

- `README.md` — 核心模块表和目录树中移除 `cn_media.py`、`baidu_search.py`
- `docs/source_strategy.md` — 来源总览表移除 `cn_media_search` 行，移除"外部脚本搜索"小节，调度步骤从五步缩为四步

## README 快速开始优化

- 新增"前置条件"段，列出 Python 版本、OpenClaw、GitHub Token、IMAP 授权码的依赖关系和可选性
- "快速开始"拆分为三步递进：环境准备 → 单步采集验证 → 完整流水线
- 第二步增加 `--skip-tavily` 采集和 `enrich_content.py` 正文抓取，让学生在不依赖 OpenClaw 的情况下看到真实数据
- 第三步改用 `run_daily_pipeline.py` 替代深层嵌套的 skill 入口脚本
- 明确说明三个 LLM 回填文件缺失时的报错行为，不再用"停住"这种模糊描述

## 项目重命名

将遗留的 `v2` / `Morning-Newspaper-Manager` 命名统一为 `morning-newspaper`。

### 目录与文件重命名

| 原始路径 | 变更后路径 |
|---|---|
| `src/morning_v2/` | `src/morning_newspaper/` |
| `skills/.../scripts/run_morning_report_v2.py` | `skills/.../scripts/run_morning_report.py` |

### Python 代码

- 所有 `from morning_v2.xxx import` → `from morning_newspaper.xxx import`（涉及 19 个文件）
- `USER_AGENT` 从 `"Morning-Newspaper-Manager-v2/0.1"` → `"Morning-Newspaper-Assistant/1.0"`（`src/morning_newspaper/common.py`）
- `scripts/collect_raw.py` argparse description 和报告标题去掉 `v2`
- `scripts/enrich_content.py` 报告标题去掉 `v2`

### 文档与配置

- `config/sources.yaml` — `paused_sources` 注释去掉 `v2`
- `skills/.../SKILL.md` — 移除 `Morning-Newspaper-Manager` 相关描述
- `scripts/serve_dashboard_8510.sh` — 移除 kill 旧 Manager 进程的行

## 邮箱配置泛化

将邮箱从限定 163 调整为支持任意 IMAP/POP3 邮箱（以 163 为例）。

- `README.md` — 邮箱配置段说明支持任意 IMAP 邮箱，增加 163/QQ/Gmail/Outlook 服务器地址对照表
- `.env.example` — 注释说明支持多种邮箱，示例地址改为 `your_email@example.com`
- `skills/.../SKILL.md` — 章节标题从 `163 邮箱配置` → `邮箱配置`，说明支持任意 IMAP/POP3 邮箱
- `lesson14-lab.md` — 保持不动（实验手册以 163 为具体操作示例）

## 文档重写

- `docs/source_strategy.md` — 基于 `src/morning_newspaper/collectors/` 实际代码全文重写为信息源策略文档，涵盖三种采集范式的实现细节、配置示例、调度与去重机制、统一数据模型
- `README.md` — 按课程规范全文重写，增加 Dashboard 效果截图

## 新增文件

| 文件 | 说明 |
|---|---|
| `.env.example` | 环境变量模板（邮箱 + GitHub Token） |
| `docs/screenshots/dashboard-demo.png` | 早报 Dashboard 运行效果截图 |
| `CHANGELOG.md` | 本文件 |

## 删除文件

| 文件 | 原因 |
|---|---|
| `docs/rewrite_plan.md` | 内部开发规划文档，不属于课程交付物 |
| `docs/pipeline_rebuild_plan.md` | 内部开发规划文档，不属于课程交付物 |
| `run_dashboard.cmd` | Windows 批处理脚本，课程以 Linux 服务器为主 |

## .gitignore 完善

补齐 `.env` / `.env.local` / `.venv/` / `.idea/` / `.vscode/` 等条目。

## requirements.txt 补全

补充 `streamlit>=1.30`（`dashboard_app.py` 的依赖）。
