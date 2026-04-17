# 🦞 Agentic AI Architect

> OpenClaw 生产部署、Agent 开发与 Claude Code 深度实战的完整知识库

[![OpenClaw](https://img.shields.io/badge/OpenClaw-GitHub%20353K⭐-blue)](https://github.com/openclaw/openclaw)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 这个仓库是什么

一套经过生产验证的 OpenClaw + Claude Code 实战资料，包含部署脚本、IM 接入指南、模型配置模板、安全加固清单和排错手册。

无论你是：
- **想把 OpenClaw 跑起来的开发者** — 一键部署脚本，30 分钟从零到能用
- **想让 Agent 接入微信/企微/飞书的用户** — 逐步指南，扫码即用
- **想在团队中落地 AI Agent 的技术负责人** — 生产级配置、安全架构、成本控制
- **想系统学习 AI 业务流架构的学员** — 配套课程《AI 业务流架构师》全部教辅资料

都可以直接使用。

## 快速导航

| 我想…… | 去这里 |
|--------|-------|
| 在云服务器上部署 OpenClaw | [openclaw-infra/](openclaw-infra/) |
| 让 Agent 接入微信 | [openclaw-im/wechat-clawbot.md](openclaw-im/wechat-clawbot.md) |
| 让 Agent 接入企业微信（含群聊） | [openclaw-im/wecom-bot.md](openclaw-im/wecom-bot.md) |
| 配置火山引擎 Coding Plan（国产模型包月） | [openclaw-models/volcengine-coding-plan.md](openclaw-models/volcengine-coding-plan.md) |
| 配置 Hotai 代理（海外旗舰模型） | [openclaw-models/hotai-api.md](openclaw-models/hotai-api.md) |
| 排查部署问题 | [openclaw-infra/checklists/troubleshooting.md](openclaw-infra/checklists/troubleshooting.md) |
| 安全加固检查 | [openclaw-infra/checklists/security-checklist.md](openclaw-infra/checklists/security-checklist.md) |

## 目录结构

```
.
├── openclaw-infra/                   # 基础设施：部署、守护进程、安全穿透
│   ├── README.md                     #   OpenClaw 部署指南
│   ├── configs/
│   │   ├── .env.example              #   环境变量模板（6 种 API 提供商）
│   │   └── openclaw.service          #   OpenClaw Gateway systemd 服务文件
│   ├── scripts/
│   │   ├── setup-openclaw.sh         #   一键部署脚本（交互式）
│   │   └── commands-cheatsheet.sh    #   运维命令速查卡
│   └── checklists/
│       ├── security-checklist.md     #   安全配置检查清单
│       └── troubleshooting.md        #   常见问题排错指南（9 个场景）
│
├── openclaw-im/                      # IM 渠道接入
│   ├── wechat-clawbot.md             #   微信 ClawBot 接入指南
│   ├── wecom-bot.md                  #   企业微信长连接机器人接入指南
│   └── feishu.md                     #   飞书原生深度集成指南（即将更新）
│
├── openclaw-models/                  # 模型配置与成本控制
│   ├── volcengine-coding-plan.md     #   火山引擎 Coding Plan 购买与配置
│   └── hotai-api.md                  #   Hotai2API 海外模型代理接入
│
├── openclaw-soul/                    # 人格工程：SOUL.md 设计与调教（即将更新）
├── openclaw-heartbeat/               # 心跳引擎：Heartbeat 定时自动化（即将更新）
├── openclaw-skills/                  # 技能开发：Skills 编写与 ClawHub 生态（即将更新）
├── openclaw-multi-agent/             # 多 Agent 协作与路由调度（即将更新）
└── claude-code/                      # Claude Code CLI 深度实战（即将更新）
```

### 📂 [openclaw-infra/](openclaw-infra/) — 基础设施

| 文件 | 说明 |
|------|------|
| [README.md](openclaw-infra/README.md) | 完整部署指南：一键部署、手动部署、Tailscale 穿透、Gateway 认证 |
| [configs/.env.example](openclaw-infra/configs/.env.example) | 环境变量模板（6 种 API 提供商） |
| [configs/openclaw.service](openclaw-infra/configs/openclaw.service) | systemd 服务文件 |
| [scripts/setup-openclaw.sh](openclaw-infra/scripts/setup-openclaw.sh) | 一键部署脚本（交互式） |
| [scripts/commands-cheatsheet.sh](openclaw-infra/scripts/commands-cheatsheet.sh) | 运维命令速查卡 |
| [checklists/security-checklist.md](openclaw-infra/checklists/security-checklist.md) | 安全配置检查清单 |
| [checklists/troubleshooting.md](openclaw-infra/checklists/troubleshooting.md) | 常见问题排错指南（9 个场景） |

### 📂 [openclaw-im/](openclaw-im/) — IM 渠道接入

| 文件 | 说明 |
|------|------|
| [wechat-clawbot.md](openclaw-im/wechat-clawbot.md) | 微信 ClawBot 接入：官方插件，一条命令 + 扫码 |
| [wecom-bot.md](openclaw-im/wecom-bot.md) | 企业微信长连接机器人：免公网 IP，支持群聊 + 文档 MCP |
| [feishu.md](openclaw-im/feishu.md) | 飞书原生深度集成（即将更新） |

### 📂 [openclaw-models/](openclaw-models/) — 模型配置与成本控制

| 文件 | 说明 |
|------|------|
| [hotai-api.md](openclaw-models/hotai-api.md) | Hotai2API：国内直连海外旗舰模型（GPT-5.4 / Claude Opus 4.6） |
| [volcengine-coding-plan.md](openclaw-models/volcengine-coding-plan.md) | 火山引擎 Coding Plan：国产模型包月，含 Embedding 配置 |


## 部署架构

```
┌─────────────────────────────────────────────┐
│  你的笔记本 / 手机                            │
│  (安装 Tailscale 客户端)                      │
└──────────────┬──────────────────────────────┘
               │ WireGuard 加密隧道
               │ (零公网 IP，Shodan 不可见)
┌──────────────▼──────────────────────────────┐
│  你的云服务器（¥99/年）                        │
│  ┌────────────────────────────────────────┐  │
│  │ Tailscale Serve (HTTPS, 仅 tailnet)   │  │
│  │         ↓                              │  │
│  │ Docker: openclaw (127.0.0.1:18789)    │  │
│  │         ↑                              │  │
│  │ systemd 双保险 (崩溃自动重启)           │  │
│  └────────────────────────────────────────┘  │
│  数据主权：SOUL.md / 记忆 / 会话 全在你的磁盘  │
└─────────────────────────────────────────────┘
```

**核心安全设计：**
- 零公网 IP — 服务器不暴露任何端口，对 Shodan / Censys 完全不可见
- WireGuard 端到端加密 — 所有流量经 Tailscale 加密隧道
- Gateway Token 认证 — 即使进入 tailnet，仍需令牌才能操作
- 127.0.0.1 绑定 — Docker 容器只监听本机，双重防护

> 完整部署步骤见 [openclaw-infra/README.md](openclaw-infra/README.md)

## 安全要点

> ⚠️ 部署完成后，务必对照 [security-checklist.md](openclaw-infra/checklists/security-checklist.md) 逐项检查

- 2026 年初 **13.5 万个** OpenClaw 实例因端口暴露被攻击（SecurityScorecard 报告）
- **永远不要**将 `.env` 提交到 Git
- **永远不要**将端口绑定到 `0.0.0.0`
- **永远不要**在安全组中开放 18789 端口

## 支持的 API 提供商

本项目通过 OpenAI 兼容格式接入大模型，配置 `OPENAI_API_KEY` + `OPENAI_BASE_URL` 即可。

| 提供商 | Base URL | 推荐场景 |
|-------|----------|---------|
| DeepSeek | `https://api.deepseek.com/v1` | 性价比最高 |
| 豆包 | `https://ark.cn-beijing.volces.com/api/v3` | 火山引擎生态 |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 阿里云生态 |
| Kimi | `https://api.moonshot.cn/v1` | 长上下文场景 |
| OpenAI | `https://api.openai.com/v1` | 海外服务器 |
| 硅基流动 | `https://api.siliconflow.cn/v1` | 多模型聚合 |

> 详细的模型配置指南见 [openclaw-models/](openclaw-models/) 目录。

## 配套课程

本仓库同时作为课程《**AI 业务流架构师：从 OpenClaw 到 Claude Code 深度实战**》的配套教辅资料。课程由彭靖田主讲，共 20 章。

## 关于作者

**彭靖田** — 连续创业者

- 浙江大学竺可桢学院毕业，加州大学访问学者
- 谷歌 AI 开发者专家（GDE），谷歌出海创业加速器导师
- TensorFlow Contributor · Kubeflow Maintainer
- 畅销书《深入理解 TensorFlow》作者
- 极客时间 AI 课程累计培训超 10 万学员

## 参与贡献

欢迎提交 Issue 和 PR！如果你有新的部署场景、排错经验或配置优化，欢迎贡献。

## License

MIT License. 详见 [LICENSE](LICENSE)。

---

**⭐ 如果这个仓库对你有帮助，请给一个 Star！**
