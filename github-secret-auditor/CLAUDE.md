# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 本文件只管 `github-secret-auditor/` 子项目。仓库根 `agentic-ai/CLAUDE.md` 是课程总览，与本文件并存。

## 这个项目是什么

一份面向 OpenClaw 的 **Skill 协议**：OpenClaw 通过 ACP 调度 Claude Code，对授权 GitHub 仓库巡检密钥泄露 → 最小修复 → 验收 → commit / push → 飞书汇报。

**项目本体是协议与模板，没有可运行代码**——智能在 Claude Code 的 agent 循环里，不在脚本里。改这个项目 = 改 `skills/github-secret-auditor/SKILL.md`、`templates/`、`references/`、`lesson19-lab.md` 这些 Agent 面向的契约文件。

## 铁律（不可违背）

1. **ACP 是唯一调度通道。** 后台自动化用 OpenClaw Sessions API（`sessions_spawn` / `sessions_send`），飞书交互演示用 `/acp doctor|spawn|steer` slash command。不要把 Claude Code CLI 当本 Skill 的常规降级路径，不要让 OpenClaw 手工替代 Claude Code 巡检或修复。
2. **执行权与发布权分离。** Claude Code 会话内只巡检 / 改文件 / 本地验证，**禁止 `git commit`、`git push`、创建 PR、输出完整密钥**；commit / push 只由 OpenClaw 在验收通过后执行。
3. **报告不入库。** 巡检报告（`security-report.md`）绝不提交进目标仓库，只发飞书或写入 `/srv/openclaw-runner/reports/`。
4. **只动授权仓库。** 不读 `.env`、真实环境配置、SSH Key、私钥、Cookie、生产配置、用户个人目录；`.env.example`、示例配置、公开模板可读 / 写 / 建，但不得含真实密钥。
5. **最小修复，不强凑模板。** 按仓库实际语言 / 框架 / 配置方式修；只有修复确实需要时才补 `.env.example` / README / `.gitignore`，不为满足固定模板强行新建无关文件。
6. **历史泄露不阻断主流程。** 疑似真实密钥已进 Git 历史时，继续完成当前代码修复，把风险类型 / 疑似文件 / 脱敏片段 / 建议动作写进飞书报告的 `risk_notes`，最终状态仍可 `passed`。

## 架构

```text
用户(飞书 repo_url)
  -> OpenClaw 编排 Agent ──ACP 调度通道(ACPX)──⇄── Claude Code 执行 Agent
       (准备/验收/发布)        sessions_spawn ▶          (巡检/修复/本地验证)
                              ◀ diff/childSessionKey
  -> 目标 GitHub 仓库(共享工作区:Claude 改、OpenClaw 推) + 飞书巡检报告
```

**默认任务流（16 步骨架）**：确认输入 → 准备工作目录 → clone / pull（脏工作区即 `failed`）→ 生成任务包 → `sessions_spawn` 启动 Claude Code → 记录 `childSessionKey` → 等待 4 件套输出 → 保存 diff / 验收 → 缺失则 `sessions_send` 补漏 → 复检 + 查 Claude 是否提前 commit → 验收通过后 `git add/commit/push` → 生成飞书报告（不入库）→ 返回最终状态。完整版见 `skills/github-secret-auditor/SKILL.md` 的"默认任务流"。

## 调用契约

**后台自动化（默认）**：
```text
sessions_spawn(runtime="acp", agentId="claude", mode="run", thread=false, cwd=<repo_path>, prompt=<完整任务 prompt>)
# 成功返回 {status:"accepted", childSessionKey:"agent:claude:acp:...", mode:"run"}
sessions_send(sessionKey=<childSessionKey>, prompt=<显式带上 上一轮输出 + 当前 git diff + 验收缺失项 + 本轮目标>)
```

**飞书交互演示**：`/acp doctor` → `/acp spawn claude --mode persistent --thread on --cwd <repo_path>` → `/acp steer --session <session-key> ...`（一次性巡检用 `sessions_spawn(mode=run)`，persistent 会话是交互式演示用）。`/acp ...` 是聊天 slash command，**不能在 bash / SSH 里执行**。

> 关键认知：`childSessionKey` 是**投递地址，不是记忆保证**。每轮 `sessions_send` 的 prompt 必须显式重新带上上一轮输出、当前 diff、验收缺失项——不要只写"继续修一下"。

后台多轮依赖：`openclaw config set tools.sessions.visibility all` 且 `openclaw config set tools.agentToAgent.enabled true`。

## 输入 / 输出契约

**输入**：`repo_url`（必填）、`branch`（默认 `main`）、`mode`（默认 `audit_fix_push_report`）。未给 `repo_path` 时默认 `/srv/openclaw-runner/repos/<repo-name>`。默认策略 `allow_auto_fix=true` / `allow_push=true` / `runner=acp`。

**输出**（OpenClaw 返回）：`status`(passed|failed) / `repo` / `runner` / `session_key` / `report_path` / `changed_files` / `risk_summary` / `completed_fixes` / `residual_risks` / `risk_notes` / `pushed` / `commit` / `notified` / `next_action`。

Git 历史泄露、疑似外部凭证、无法自动判定的凭证归属，**不改变自动化完成状态**，写入 `risk_notes`。

## 验收标准（OpenClaw 必须检查）

- 仓库 diff 中没有 `security-report.md`。
- 当前代码与被修改文件中不再出现明显完整硬编码密钥。
- 修复方式符合仓库实际结构，不强凑模板新增无关文件。
- 若修复引入 / 依赖环境变量，`.env.example` / README / 已有配置说明含必要占位符，且不含真实密钥。
- 若有再次误提交风险，`.gitignore` 或同类忽略规则已补齐。
- Claude Code 输出了修改文件清单、风险摘要、测试 / 静态检查结果、Git Diff 摘要。
- 若有历史泄露或外部凭证风险，报告中有 `risk_notes`。
- **额外**：验收前检查当前分支是否出现 Claude Code 提前生成的本地 commit；若有，先核实改动范围 / diff / 是否含禁止文件 / 是否满足验收，核实通过才复用并 push，否则要求回到未提交状态。

## 失败处理 / 已知坑

- `sessions_spawn` 返回 `thread_required`：多半误用了 `mode=session`，改回 `mode=run` / `thread=false`。
- `sessions_send` 报 visibility / agent-to-agent forbidden：检查 `tools.sessions.visibility=all`、`tools.agentToAgent.enabled=true`，必要时重启 gateway 并重建 session。
- Claude Code 只能分析不能写：检查 ACPX 非交互写入权限（课堂演示可临时 `permissionMode=approve-all`，结束恢复 `approve-reads`），确认 `--cwd` 指向授权仓库、运行用户能读写 `repo_path`。
- `claude: command not found` 或终端能跑 OpenClaw 不能：gateway 运行用户 / PATH 不一致。
- ACP runtime 不可用 / 无法建 child session：返回 `failed` 并说明阻塞原因，**不要改用 OpenClaw 手工巡检**。

## 改这个项目时注意

- **同步更新契约**：改了 Agent 面向的流程，`SKILL.md`、`templates/`、`references/`、`lesson19-lab.md` 要一起改到一致。
- **路径引用按项目根相对**：`SKILL.md` 在 `skills/github-secret-auditor/`，但引用 `templates/...`、`references/...` 时写**项目根相对路径**（OpenClaw 按项目根解析，与 morning-newspaper / CRM-Assistant 同约定）。
- **报告示例一律脱敏**：文档里出现密钥只能是占位符或脱敏片段（如 `sk-...abcd`），不得出现真实密钥。
- **服务器路径是约定不是本地目录**：`/srv/openclaw-runner/{repos,tasks,reports}`、`/root/projects/...`、`~/.claude/settings.json` 是课程服务器部署约定，不在本项目内创建。
