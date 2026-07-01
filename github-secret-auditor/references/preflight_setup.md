# 第 19 节前置部署参考

本文件用于课程环境初始化，不属于 Skill 的默认执行流程。只有在需要部署 OpenClaw、Claude Code、ACP 或排查写入权限时读取。

## 目标

让 OpenClaw 能通过 ACP 调度 Claude Code，并允许 Claude Code 在授权仓库目录内完成必要的文件修改。飞书交互可以使用 `/acp ...` slash command；后台自动化应使用 OpenClaw Sessions API 调度同一个 ACP runtime。

## 推荐目录

```text
/root/projects/agentic-ai
/srv/openclaw-runner/repos
/srv/openclaw-runner/tasks
/srv/openclaw-runner/reports
```

## 安装 ACPX 后端

OpenClaw 通过 ACPX 后端经 ACP 调度 Claude Code。ACPX 随 OpenClaw 一起分发（打包在 `dist/extensions/acpx`），但需显式安装启用；否则 `/acp doctor` 报 backend 不健康、`sessions_spawn` 找不到 acp runtime。

acpx 随 OpenClaw 自带、通常已在 `allow` 且 `enabled: true`，但**有两个坑会让它"装上却用不了"**（`/acp doctor` 报 `registeredBackend: (none)`）：

- **`openclaw plugins install acpx` 可能被安全扫描拦下**（检测到 `child_process`——ACP 本就要拉子进程）。不用管：acpx 自带且已在 `allow`，网关启动直接加载，不必走 CLI。
- **自带扩展漏装运行时依赖 `acpx@0.5.3`** → 启动报 `Cannot find module 'acpx/runtime'` → 后端不注册。手动补依赖后重启：

```bash
cd /usr/lib/node_modules/openclaw/dist/extensions/acpx
npm install --registry=https://registry.npmmirror.com    # 国内镜像；能直连官方源就去掉 --registry
openclaw config get plugins              # 确认 acpx 在 allow，且 entries.acpx.enabled: true
systemctl restart openclaw               # 重启 gateway 生效
```

> 验证只看 `/acp doctor` 的 `registeredBackend: acpx`；`acpx --help` 不存在（进程内插件）。`configuredBackend: acpx` 但 `registeredBackend: (none)` = 没加载，多半缺依赖或没重启。

安装后 `entries.acpx` 形如：

```json
"acpx": {
  "enabled": true,
  "config": {
    "permissionMode": "approve-all",
    "nonInteractivePermissions": "fail",
    "timeoutSeconds": 120
  }
}
```

`config` 里的写入权限策略见下文「写入权限说明」。若 `openclaw config get plugins` 顶部出现 `plugins.allow: plugin not found: help (stale config entry ignored...)` 告警，是 `plugins.allow` 残留了已卸载插件名，用 `openclaw config set plugins.allow '[...]'` 重设去掉即可，无害。

## 飞书交互健康检查

在 OpenClaw/飞书聊天对话框中执行。`/acp ...` 是聊天 slash command，不是 shell 命令，不要在 SSH/bash/PowerShell 里执行：

```text
/acp doctor
```

应确认：

```text
configuredBackend: acpx
registeredBackend: acpx
healthy: yes
```

继续验证可创建 Claude Code 会话：

```text
/acp spawn claude --mode persistent --thread off --cwd /srv/openclaw-runner/repos/agentic-ai
```

应返回完整 `session-key`，例如 `agent:claude:acp:...`。

这一步只用于证明飞书交互链路可用，不是后台 Skill runner 的默认调用方式。

## 后台 Sessions API 配置

后台任务不依赖 `/acp ...` 聊天命令，也不需要把 slash command 伪造成 shell 或聊天消息。后台默认使用 Sessions API：

```text
sessions_spawn(runtime="acp", agentId="claude", mode="run", thread=false, cwd=<repo_path>, prompt=<task_prompt>)
```

如果需要向同一个 child session 追加补漏任务，使用：

```text
sessions_send(sessionKey=<childSessionKey>, prompt=<explicit_context_prompt>)
```

启用后台多轮投递前，确认以下配置：

```bash
openclaw config set tools.sessions.visibility all
openclaw config set tools.agentToAgent.enabled true
```

`sessions_spawn` 成功后应返回：

```json
{
  "status": "accepted",
  "childSessionKey": "agent:claude:acp:...",
  "mode": "run"
}
```

注意：`childSessionKey` 是后续投递目标，不等于 Claude Code 一定保留上一轮上下文。使用 `sessions_send` 时，prompt 必须显式包含上一轮输出、当前 Git Diff、验收缺失项和本轮目标。

推荐只读验证：

```text
sessions_spawn(
  runtime="acp",
  agentId="claude",
  mode="run",
  thread=false,
  cwd="/srv/openclaw-runner/repos/agentic-ai",
  prompt="请输出 pwd 和 git status --short，不要修改文件。"
)
```

如果需要验证补漏投递：

```text
sessions_send(
  sessionKey="<childSessionKey>",
  prompt="只读测试：请再次输出 pwd 和 git status --short，不要修改文件。"
)
```

## 写入权限说明

ACP 会话通常是非交互式运行。如果权限策略过于保守，Claude Code 可能可以搜索和分析仓库，但无法执行 `Edit`、`Write` 或修改授权仓库文件。

课程演示环境可以在明确授权的仓库范围内，临时使用更宽松的 ACPX 权限策略。该配置是持久写入 OpenClaw 配置文件的，不是一次性命令。任务完成后应恢复保守策略。

示例命令：

```bash
openclaw config set plugins.entries.acpx.config.permissionMode approve-all
openclaw config set plugins.entries.acpx.config.nonInteractivePermissions fail
```

配置后必须重启 OpenClaw gateway，并重新执行：

```text
/acp doctor
```

然后重新创建 Claude ACP 会话。旧 session 可能沿用旧权限。

## 恢复保守策略

课程演示结束后，可恢复更保守的策略：

```bash
openclaw config set plugins.entries.acpx.config.permissionMode approve-reads
openclaw config set plugins.entries.acpx.config.nonInteractivePermissions deny
```

恢复后同样需要重启 OpenClaw gateway。

## 安全边界

- 不要把 ACP 会话 `--cwd` 指向 `/root`、用户 home、系统目录或包含生产密钥的目录。
- 只把 `--cwd` 指向明确授权的仓库，例如 `/srv/openclaw-runner/repos/agentic-ai`。
- 即使使用 `approve-all`，任务 prompt 仍必须禁止读取 `.env`、私钥、Cookie、生产配置和用户个人目录。
- 如果发现真实密钥进入 Git 历史，代码修复、commit、push 和飞书报告仍应自动完成；同时在飞书报告风险备注中记录风险类型、疑似文件、脱敏片段和建议动作。
