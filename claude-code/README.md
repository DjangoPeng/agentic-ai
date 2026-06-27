# Claude Code 深度实战（第五篇）

本目录收录**关于 Claude Code 本身**的课程实操资料。

> 组织原则（与全仓库一致）：**按产物 / 主题命名目录，不按节号**。
> 产出独立 app 的课不放这里，而是按 app 名建顶层目录（与 `financial-automation/`、`xhs-auto-publisher/` 一致）。

| 节 | 主题 | 位置 |
| --- | --- | --- |
| 16 | Claude Code 交互范式革命与安全沙箱 | 概念课；现场演示脚本 `check-env.sh` 见 [`openclaw-infra/scripts/`](../openclaw-infra/scripts) |
| 17 | 多文件协同与终端代码级重构实战 | [`multi-file-refactor/`](multi-file-refactor) |

每节目录自包含：`README.md`（本节说明）+ `lessonNN-lab.md`（学生实验手册）+ `setup.sh`（搭工作区脚本）+ 课中产物。

## 后续几节的落点（同一原则）

| 节 | 产物本质 | 落点 |
| --- | --- | --- |
| 18 · AI Quant CLI 量化投研系统 | 从零造的独立 app | 顶层 `ai-quant-cli/`（套 L12–15 范式，lab 内置） |
| 19 · 夜间代码自愈（OpenClaw × Claude Code） | OpenClaw 经 ACP 调度 Claude Code（多 Agent 协作） | 顶层 `github-secret-auditor/` |
| 20 · 企业级安全审计与生产治理 | 治理清单 / 文档为主 | `openclaw-infra/checklists/`（或新建 `governance/`） |
