---
name: github-secret-auditor
description: 当用户希望让 OpenClaw 通过 ACP 调度 Claude Code，对 GitHub 仓库进行 API Key、Token、密码、私钥、Webhook URL 等敏感信息泄露巡检、自动修复、验收、推送修复 commit，并通过飞书发送巡检报告时使用。
---

# GitHub 密钥泄露巡检 Skill

## 目标

本 Skill 用于让 OpenClaw 通过 ACP 调度 Claude Code，对授权 GitHub 仓库执行密钥泄露巡检、安全修复、验收、推送修复 commit，并通过飞书发送巡检报告。

核心原则：

- OpenClaw 负责任务编排、ACP 调度、仓库准备、验收、commit、push 和飞书报告。
- Claude Code 负责在目标仓库内执行代码级搜索、修复和验证。
- 不允许 OpenClaw 跳过 Claude Code 手工替代巡检或修复。
- 本 Skill 的默认且唯一调度通道是 ACP。不要把 Claude Code CLI 作为本 Skill 的常规降级路径。
- Claude Code 只负责巡检、修改和本地验证；默认禁止 Claude Code 在子会话内执行 `git commit`、`git push`、创建 PR 或其他发布动作。commit 与 push 只能由 OpenClaw 在验收通过后执行。

## 适用场景

当用户提出以下需求时使用本 Skill：

- 巡检某个 GitHub 仓库是否存在 API Key、Token、密码、Webhook URL、私钥等泄露风险。
- 根据仓库实际泄露面自动修复，例如删除误提交凭证、改为环境变量/配置注入、替换为安全占位符或补充忽略规则。
- 只在修复确实需要时更新 `.env.example`、`.gitignore`、README 或同类配置说明文件。
- 验收通过后自动推送普通修复 commit 到授权 GitHub 仓库。
- 通过飞书发送巡检报告。
- 通过 ACP 让 OpenClaw 调度 Claude Code 完成代码级任务。

## 快速启动

给 OpenClaw/龙虾的一句话启动模板见 `templates/run_skill_prompt.md`。

用户只需提供目标 GitHub 仓库，OpenClaw 必须自动按默认任务流完成巡检、修复、验收、commit、push 和飞书报告。不要要求用户手动复制 session、手动执行 ACP 命令、手动拼接 prompt 或手动验收。

最小用户入口示例：

```text
请使用 github-secret-auditor Skill 全自动巡检并修复 https://github.com/DjangoPeng/agentic-ai.git
```

OpenClaw 必须先读取本 `SKILL.md`，再执行默认任务流。后台自动化默认使用 OpenClaw Sessions API：

```text
sessions_spawn(runtime="acp", agentId="claude", mode="run", thread=false, cwd=<repo_path>, prompt=<task_prompt>)
sessions_send(sessionKey=<childSessionKey>, prompt=<contextual_followup_prompt>)
```

飞书交互演示可使用 `/acp ...` slash command；后台自动化不要依赖聊天命令，也不要把 `/acp ...` 当 shell 命令执行。

除非任务失败或用户明确要求调试细节，最终回复只展示巡检结果、修复结果、commit、push 状态、风险摘要和风险备注；不要把 `sessions_spawn`、`sessions_send` 参数作为用户需要操作的步骤暴露出来。

## 用户入口与默认行为

当用户只提供 `repo_url` 或说“巡检这个仓库”时，OpenClaw 不要反问执行细节，直接使用以下默认值：

```json
{
  "branch": "main",
  "mode": "audit_fix_push_report",
  "allow_auto_fix": true,
  "allow_push": true,
  "runner": "acp_sessions",
  "repo_path": "/srv/openclaw-runner/repos/<repo-name>"
}
```

只有缺少仓库授权、ACP runtime 不可用、GitHub 权限不足、工作区存在未提交修改或安全边界不明确时，才返回 `failed` 并说明阻塞原因。

用户面向的完成标准是看到飞书巡检报告和最终结果；OpenClaw 内部负责完整执行以下动作：

```text
读取 Skill -> 准备仓库 -> 生成任务包 -> sessions_spawn 调度 Claude Code -> 等待输出 -> 必要时 sessions_send 补漏 -> 验收 Diff -> commit -> push -> 飞书报告
```

## ACP 调用 Claude Code 规范

OpenClaw 必须通过 ACP 调用 Claude Code。后台自动化与飞书交互演示使用不同入口，但底层都应调度 ACP runtime 的 Claude agent。

### 后台自动化调用

后台任务、Heartbeat 或定时任务默认使用 OpenClaw Sessions API，不使用 `/acp ...` 聊天命令：

```text
sessions_spawn({
  runtime: "acp",
  agentId: "claude",
  mode: "run",
  thread: false,
  cwd: "/srv/openclaw-runner/repos/agentic-ai",
  prompt: "<完整巡检修复任务 prompt>"
})
```

> **任务 prompt 要命令式、强制用工具。** 遇到较弱或经中转的非 Claude 模型（如火山 `ark-code-latest`），一大段开放式任务容易被"只输出计划就判定完成"。prompt 要写成"现在立刻用 Read/Grep/Edit 动手做，不要只回计划"，并把步骤拆明确（找 → 读 → 改 → 复核 → diff）。

`sessions_spawn` 成功后应返回：

```json
{
  "status": "accepted",
  "childSessionKey": "agent:claude:acp:...",
  "mode": "run"
}
```

OpenClaw 必须保存 `childSessionKey`，并把它作为后续轮次的 `sessionKey`。

如果需要多轮补漏，使用：

```text
sessions_send({
  sessionKey: "<childSessionKey>",
  prompt: "<显式包含上一轮输出、当前 git diff、验收缺失项的 follow-up prompt>"
})
```

注意：`sessions_send` 可以把消息继续投递到同一个 `childSessionKey`，但不要假设 Claude Code 会自动记住上一轮上下文。OpenClaw 必须在每一轮 prompt 中显式带上必要上下文，例如上一轮输出、Git Diff、验收缺失项和本轮目标。

后台多轮能力依赖以下配置：

```bash
openclaw config set tools.sessions.visibility all
openclaw config set tools.agentToAgent.enabled true
```

如果 `sessions_send` 返回 visibility 或 agent-to-agent forbidden，说明上述配置未生效或 gateway 需要重启。

### 飞书交互演示调用

`/acp doctor`、`/acp spawn`、`/acp steer` 是 OpenClaw/飞书对话框 slash command，不是服务器 shell 命令，不能在 bash、zsh、PowerShell 或 SSH 终端里执行。

在飞书/OpenClaw 对话框中，按顺序发送以下聊天消息：

```text
/acp doctor
```

如果返回 `healthy: yes`，继续在同一个对话框中发送以下聊天消息，创建 Claude Code 会话：

```text
/acp spawn claude --mode persistent --thread on --cwd /srv/openclaw-runner/repos/agentic-ai
```

返回示例：

```text
Spawned ACP session agent:claude:acp:258c3125-77df-42ab-90e6-207af58ceef6
```

OpenClaw 必须记录完整 `session-key`：

```text
agent:claude:acp:258c3125-77df-42ab-90e6-207af58ceef6
```

然后继续在对话框中发送以下聊天消息，投递任务：

```text
/acp steer --session <session-key> 读取 /srv/openclaw-runner/tasks/agentic-ai-secret-audit.json，并严格按照 /root/projects/agentic-ai/github-secret-auditor/templates/acp_steer_prompt.md 执行。
```

如果验收发现缺失项，继续使用同一个 `session-key` 追加 steer：

```text
/acp steer --session <session-key> 上一轮输出如下：<上一轮输出>。当前 git diff 如下：<git diff>。OpenClaw 验收缺失项如下：<具体缺失项>。请只修复这些缺失项，完成后重新输出修改文件清单、风险摘要、测试/静态检查结果和 git diff 摘要。
```

### Session 保存

OpenClaw 应把 session 信息保存到当前任务状态：

```json
{
  "runner": "acp",
  "agent": "claude",
  "session_key": "agent:claude:acp:258c3125-77df-42ab-90e6-207af58ceef6",
  "repo_path": "/srv/openclaw-runner/repos/agentic-ai",
  "task_path": "/srv/openclaw-runner/tasks/agentic-ai-secret-audit.json"
}
```

后台自动化中，`session_key` 来自 `sessions_spawn` 的 `childSessionKey`。如果任务重试且 session 仍可用，优先复用现有 `session_key` 并通过 `sessions_send` 继续投递；如果 session 丢失或不可解析，重新 `sessions_spawn`。

## 前置条件

使用本 Skill 前，OpenClaw 应确认：

- OpenClaw 所在服务器已安装 Claude Code，并完成认证或 API 中转配置。
- ACP runtime 可用；后台可调用 `sessions_spawn(runtime="acp", agentId="claude", mode="run", thread=false, ...)`。
- 如需后台多轮，`tools.sessions.visibility=all` 且 `tools.agentToAgent.enabled=true`。
- `configuredBackend` 和 `registeredBackend` 均为 `acpx`。
- `sessions_spawn` 能返回 `childSessionKey: agent:claude:acp:...`。
- OpenClaw 运行用户具备目标 GitHub 仓库的 clone、commit 和 **push 权限**：服务器配了可写该仓库的凭据（fine-grained PAT 勾 Contents: Read and write，或 SSH deploy key）。缺凭据时 push 报 `403`，巡检 + 修复 + 本地 commit + 报告仍完成、报告标 `pushed: no`。
- 目标仓库已获得用户授权。
- 默认工作根目录为 `/srv/openclaw-runner`。

如果 ACP runtime 不可用或无法创建 Claude Code child session，会话状态为 `failed`，并返回具体阻塞原因。不要改用 OpenClaw 自己手工巡检。

## 输入契约

用户至少应提供：

- `repo_url`：GitHub 仓库地址，例如 `https://github.com/DjangoPeng/agentic-ai.git`。
- `branch`：目标分支，默认 `main`。
- `mode`：默认 `audit_fix_push_report`。

如果用户未提供 `repo_path`，默认使用：

```text
/srv/openclaw-runner/repos/<repo-name>
```

默认策略：

```json
{
  "allow_auto_fix": true,
  "allow_push": true,
  "push_strategy": "commit_to_current_branch",
  "runner": "acp"
}
```

## 输出契约

任务完成后，OpenClaw 应返回：

```json
{
  "status": "passed | failed",
  "repo": "DjangoPeng/agentic-ai",
  "runner": "acp",
  "session_key": "agent:claude:acp:...",
  "report_path": "/srv/openclaw-runner/reports/agentic-ai-security-report.md",
  "changed_files": [],
  "risk_summary": "",
  "completed_fixes": [],
  "residual_risks": [],
  "risk_notes": [],
  "pushed": false,
  "commit": "",
  "notified": false,
  "next_action": ""
}
```

状态含义：

- `passed`：Claude Code 已完成代码修复，OpenClaw 验收通过，并已按配置完成 commit、push 和飞书报告。
- `failed`：ACP 调度失败、仓库不可访问、Claude Code 未完成任务、验收不通过或 push 失败。

Git 历史泄露、疑似外部凭证风险或无法自动判定的凭证归属，不改变本 Skill 的自动化完成状态；这些内容写入飞书报告的 `risk_notes`。

## 默认任务流

1. 确认输入：`repo_url`、`repo_path`、`branch`、`mode`、`allow_auto_fix`、`allow_push`。
2. 准备工作目录：`/srv/openclaw-runner/repos`、`/srv/openclaw-runner/tasks`、`/srv/openclaw-runner/reports`。
3. 如果本地没有仓库，clone 到 `repo_path`。
4. 如果本地已有仓库，先执行 `git status --short`；如有未提交修改，停止并报告 `failed`，避免覆盖用户工作。
5. 工作区干净时执行 `git pull --ff-only`。
6. 基于 `templates/openclaw_task.secret_audit.json` 生成任务包到 `/srv/openclaw-runner/tasks/<repo>-secret-audit.json`。
7. 使用 `sessions_spawn(runtime="acp", agentId="claude", mode="run", thread=false, cwd=<repo_path>, prompt=<完整任务 prompt>)` 创建并启动 Claude Code child session。
8. 记录返回的 `childSessionKey`，格式为 `agent:claude:acp:...`。
9. 等待 Claude Code 输出修改文件清单、风险摘要、测试/静态检查结果和 Git Diff 摘要。
10. OpenClaw 保存 Claude 输出、`git status --short`、`git diff` 和验收结果。
11. 如验收缺失项，使用 `sessions_send(sessionKey=<childSessionKey>, prompt=<显式上下文 follow-up prompt>)` 定向补漏。follow-up prompt 必须包含上一轮输出、当前 Git Diff、验收缺失项和本轮目标。
12. OpenClaw 再次验收 Git Diff 和残余风险，并额外检查当前分支是否出现 Claude Code 提前生成的本地 commit。
13. 如果 Claude Code 已提前执行本地 `git commit`，OpenClaw 不立即 push；先核实该 commit 的修改范围、diff、是否包含禁止文件、是否满足验收标准。只有核实通过后，才允许继续 push；如未通过，则要求 Claude Code 回到未提交状态或重新修复。
14. 验收通过后，OpenClaw 执行 `git add`、`git commit`、`git push`。如本地已存在且通过验收的修复 commit，OpenClaw 可以直接复用该 commit 执行 push，并在报告中注明“Claude 已先本地 commit，OpenClaw 已验收后推送”。
15. OpenClaw 生成飞书报告；报告不得提交到 GitHub 仓库。
16. 返回最终状态、commit、风险摘要、后续动作和飞书通知结果。

第一轮 `<完整任务 prompt>` 应包含：任务包路径、`templates/acp_steer_prompt.md` 的任务要求、目标仓库路径、禁止读取范围、输出格式要求，以及显式的 Git 边界：`不要执行 git commit / git push / PR 创建；只做巡检、修改和本地验证`。不要只发送一句“去巡检”，也不要把修复限定成固定文件模板。

## OpenClaw 与 Claude Code 分工

OpenClaw 负责：

- 拉取或更新目标仓库。
- 生成任务包。
- 使用 `sessions_spawn` 创建 Claude Code ACP child session。
- 使用 `sessions_send` 多轮投递显式上下文，让 Claude Code 完成巡检、修复和补漏。
- 在每一轮提示里明确声明：Claude Code 不得执行 `git commit` / `git push` / PR 创建；这些动作保留给 OpenClaw。
- 验收 Git Diff、修复合理性、敏感信息是否已移除，以及必要的配置/文档补充是否到位。
- 验收通过后执行 commit 和 push。
- 发送飞书报告，必要时写入 `/srv/openclaw-runner/reports`。

Claude Code 负责：

- 只在 `repo_path` 内工作。
- 搜索疑似 API Key、Token、密码、Webhook URL、私钥片段、数据库连接串等风险。
- 根据仓库语言、框架和配置方式选择最小安全修复：删除误提交凭证、改为环境变量读取、改为配置注入、替换为安全占位符，或补充安全模板。
- 如果修复引入或依赖环境变量，才创建或更新 `.env.example`、README 或项目已有配置说明；内容只能包含占位符和配置说明。
- 如果发现 `.gitignore` 缺少会导致同类泄露的忽略规则，才补充 `.env`、本地密钥文件、私钥文件或项目特定敏感配置的忽略规则。
- 输出修改文件清单、风险摘要、测试/静态检查结果和 Git Diff 摘要。
- 不执行 `git commit`、不 push、不创建 PR、不输出完整密钥。

## 安全规则

- 只处理用户明确授权的仓库路径。
- 不读取 `.env`、真实环境配置、SSH Key、私钥、Cookie、生产配置和用户个人目录；`.env.example`、示例配置和公开模板可读取/创建/更新，但不得包含真实密钥。
- 不在报告中输出完整密钥，只允许输出脱敏片段，例如 `sk-...abcd`。
- 不强推、不清理 Git 历史、不自动合并分支。
- 不把 `security-report.md` 作为仓库文件提交。
- 所有自动修复都必须留下 Git Diff 摘要。
- Claude Code 会话内不得执行 `git commit` 或 push；commit/push 只由 OpenClaw 在验收后执行。

## 历史泄露风险记录

如果发现疑似真实密钥已进入 Git 历史：

- Claude Code 继续完成当前代码修复，不要因为历史风险停止自动化流程。
- OpenClaw 仍可在验收通过后提交并推送普通修复 commit。
- 验收、commit、push 和飞书报告完成后，最终状态仍可为 `passed`。
- 飞书报告中的 `risk_notes` 必须记录风险类型、疑似文件、脱敏片段和建议动作。
- 不要声称已经完成外部平台凭证处理，除非任务包明确提供了可调用的外部接口。

## 验收标准

OpenClaw 必须检查：

- 仓库 diff 中没有 `security-report.md`。
- 当前代码和被修改文件中不再出现明显完整硬编码密钥。
- 修复方式符合仓库实际结构，不为了凑模板强行新增无关文件。
- 如果修复引入或依赖环境变量，`.env.example`、README 或项目已有配置说明必须包含必要占位符/说明，且不包含真实密钥。
- 如果发现本地密钥、私钥、`.env`、生产配置或项目特定敏感文件有再次误提交风险，`.gitignore` 或同类忽略规则必须补齐。
- Claude Code 输出了修改文件清单、风险摘要、测试/静态检查结果和 Git Diff 摘要。
- 若有历史泄露或外部凭证风险，报告中有 `risk_notes`。

验收通过后，OpenClaw 可执行：

```bash
cd /srv/openclaw-runner/repos/agentic-ai
git status --short
git add <authorized_changed_files>
git commit -m "fix: remediate leaked secret configuration"
git push origin HEAD
```

实际 `git add` 文件清单应以 Git Diff 中的授权修复文件为准，不要添加报告文件或禁止文件。

## 飞书报告

飞书报告必须包含：

- 状态：`passed` 或 `failed`。
- 目标仓库与分支。
- 是否已 push。
- commit hash。
- 修改文件清单。
- 风险摘要。
- 已完成修复。
- 残余风险。
- 风险备注 `risk_notes`。
- 下一步动作。

OpenClaw 任务状态必须记录 ACP session-key；用户面向的飞书报告默认不展示 session-key，除非任务失败、排查调度问题，或用户明确要求调试细节。

报告可归档到：

```text
/srv/openclaw-runner/reports/agentic-ai-security-report.md
```

归档报告不得提交到 GitHub 仓库。

## 失败处理

如果后台 `sessions_spawn` 失败：

- 检查 `runtime` 是否为 `acp`、`agentId` 是否为 `claude`、`mode` 是否为 `run`、`thread` 是否为 `false`。
- 如果返回 `thread_required`，通常说明误用了 `mode=session`；按本 Skill 改回 `mode=run`、`thread=false`。
- 如果返回 visibility 或 agent-to-agent 权限错误，报告具体配置问题。
- 不要改用 OpenClaw 手工巡检。

如果后台 `sessions_send` 无法发送 follow-up：

- 检查是否使用完整 `agent:claude:acp:...`。
- 检查 `tools.sessions.visibility` 是否为 `all`。
- 检查 `tools.agentToAgent.enabled` 是否为 `true`。
- 如 session 丢失或过期，重新执行 `sessions_spawn` 并在 prompt 中带上 OpenClaw 保存的上下文。

如果 Claude Code 报权限不足：

- 检查 `--cwd` 是否指向目标仓库。
- 检查运行用户是否能读写 `repo_path`。
- 检查 ACPX 非交互写入权限。
- 修复权限后重新创建 Claude ACP 会话。
