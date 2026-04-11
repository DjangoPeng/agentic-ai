# 🦞 Agentic AI Architect

> OpenClaw 生产部署、Agent 开发与 Claude Code 深度实战的完整知识库

[![OpenClaw](https://img.shields.io/badge/OpenClaw-GitHub%20353K⭐-blue)](https://github.com/openclaw/openclaw)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 这个仓库是什么

一套经过生产验证的 OpenClaw + Claude Code 实战资料，包含部署脚本、配置模板、安全加固指南和排错手册。

无论你是：
- **想把 OpenClaw 跑起来的开发者** — 一键部署脚本，30 分钟从零到能用
- **想在团队中落地 AI Agent 的技术负责人** — 生产级配置、安全架构、运维速查
- **想系统学习 AI 业务流架构的学员** — 配套课程《AI 业务流架构师：从 OpenClaw 到 Claude Code 深度实战》

都可以直接使用。

## 目录结构

```
.
├── openclaw-infra/                # 基础设施：部署、守护进程、安全穿透
│   ├── configs/
│   │   ├── .env.example           # 环境变量模板（6 种 API 提供商）
│   │   └── openclaw.service       # OpenClaw Gateway systemd 服务文件
│   ├── scripts/
│   │   ├── setup-openclaw.sh      # 一键部署脚本（交互式）
│   │   └── commands-cheatsheet.sh # 运维命令速查卡
│   └── checklists/
│       ├── security-checklist.md  # 安全配置检查清单
│       └── troubleshooting.md     # 常见问题排错指南（9 个场景）
├── openclaw-im/                   # IM 接入：钉钉、企微、飞书（即将更新）
├── openclaw-soul/                 # 人格工程：SOUL.md 设计（即将更新）
├── openclaw-heartbeat/            # 心跳引擎：定时自动化（即将更新）
├── openclaw-skills/               # 技能开发：Skills 与 ClawHub（即将更新）
├── openclaw-multi-agent/          # 多 Agent 协作（即将更新）
└── claude-code/                   # Claude Code 深度实战（即将更新）
```

## 快速开始：30 分钟部署 OpenClaw

### 你需要准备

| 项目 | 说明 | 费用 |
|------|------|------|
| 云服务器 | 推荐火山引擎 2C4G（或阿里云 / 腾讯云同配置） | ¥99/年 |
| 大模型 API Key | DeepSeek / 豆包 / 通义千问 / Kimi / OpenAI 均可 | 按用量 |
| Tailscale 账号 | https://tailscale.com （GitHub 登录即可） | 免费 |

### 一键部署

```bash
git clone https://github.com/DjangoPeng/ai-agent-architect.git
cd ai-agent-architect/openclaw-infra

chmod +x scripts/setup-openclaw.sh
sudo scripts/setup-openclaw.sh
```

脚本自动完成：系统更新 → Docker 安装 → OpenClaw 部署 → systemd 双保险 → Tailscale 安装。

完成后按屏幕提示执行手动步骤：

```bash
# 1. Tailscale 认证
sudo tailscale up

# 2. 开启私有访问
tailscale serve --bg 18789

# 3. 预获取 HTTPS 证书
tailscale cert $(hostname).tailnet.ts.net

# 4. 配置 Gateway 认证
docker compose exec openclaw bash
openclaw doctor --generate-gateway-token
openclaw config set gateway.auth.mode token
openclaw config set gateway.auth.token "你的令牌"
openclaw config set gateway.bind loopback
openclaw config set gateway.controlUi.allowInsecureAuth false
exit && docker compose restart
```

然后在个人设备安装 Tailscale，浏览器访问 `https://<你的设备名>.tailnet.ts.net` 即可进入 Dashboard。

### 手动部署

如果你希望理解每一步在做什么，可以按以下顺序操作：

1. 购买云服务器（推荐 Ubuntu 24.04 LTS）
2. 安装 Docker：`curl -fsSL https://get.docker.com | sh`
3. 复制 `configs/docker-compose.yml` 和 `configs/.env.example` 到服务器
4. 编辑 `.env`，填入 API Key
5. `docker compose up -d` 启动
6. 复制 `configs/openclaw.service` 配置 systemd 双保险
7. 安装 Tailscale，配置 Serve

详细说明见各配置文件中的注释。

## 支持的 API 提供商

本项目通过 OpenAI 兼容格式接入大模型，配置 `OPENAI_API_KEY` + `OPENAI_BASE_URL` 即可。

| 提供商 | Base URL | 推荐场景 |
|-------|----------|---------|
| DeepSeek | `https://api.deepseek.com/v1` | 性价比最高（默认推荐） |
| 豆包 | `https://ark.cn-beijing.volces.com/api/v3` | 火山引擎生态 |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 阿里云生态 |
| Kimi | `https://api.moonshot.cn/v1` | 长上下文场景 |
| OpenAI | `https://api.openai.com/v1` | 海外服务器 |
| 硅基流动 | `https://api.siliconflow.cn/v1` | 多模型聚合 |

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

## 安全要点

> ⚠️ 部署完成后，务必对照 [`openclaw-infra/checklists/security-checklist.md`](openclaw-infra/checklists/security-checklist.md) 逐项检查

- 2026 年初 **13.5 万个** OpenClaw 实例因端口暴露被攻击（SecurityScorecard 报告）
- **永远不要**将 `.env` 提交到 Git
- **永远不要**将端口绑定到 `0.0.0.0`
- **永远不要**在安全组中开放 18789 端口

## 常见问题

遇到问题请查阅 [`openclaw-infra/checklists/troubleshooting.md`](openclaw-infra/checklists/troubleshooting.md)，覆盖 9 个场景：

| # | 问题 | 关键词 |
|---|------|-------|
| Q1 | docker compose up 报端口占用 | `address already in use` |
| Q2 | tailscale up 卡住不动 | `timed out` |
| Q3 | Serve 成功但浏览器无法访问 | `ERR_CONNECTION_REFUSED` |
| Q4 | Dashboard 加载但认证失败 | `auth failed` |
| Q5 | 容器启动后立即退出 | `Exited` |
| Q6 | systemd 服务启动失败 | `failed` |
| Q7 | Docker 镜像拉取失败 | `timeout` |
| Q8 | Tailscale 证书获取失败 | `acme` / `i/o timeout` |
| Q9 | Clash/VPN 代理导致无法访问 | `ERR_CONNECTION_CLOSED` |

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
