# OpenClaw 基础设施：部署、守护进程、安全穿透

> 30 分钟从零到能用的 OpenClaw 生产部署指南

## 你需要准备

| 项目 | 说明 | 费用 |
|------|------|------|
| 云服务器 | 推荐火山引擎 2C4G（或阿里云 / 腾讯云同配置） | ¥99/年 |
| 大模型 API Key | DeepSeek / 豆包 / 通义千问 / Kimi / OpenAI 均可 | 按用量 |
| Tailscale 账号 | https://tailscale.com （GitHub 登录即可） | 免费 |

## 一键部署

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

## 手动部署

如果你希望理解每一步在做什么，可以按以下顺序操作：

1. 购买云服务器（推荐 Ubuntu 24.04 LTS）
2. 安装 Docker：`curl -fsSL https://get.docker.com | sh`
3. 复制 `configs/docker-compose.yml` 和 `configs/.env.example` 到服务器
4. 编辑 `.env`，填入 API Key
5. `docker compose up -d` 启动
6. 复制 `configs/openclaw.service` 配置 systemd 双保险
7. 安装 Tailscale，配置 Serve

详细说明见各配置文件中的注释。

## 本目录文件说明

| 文件 | 说明 |
|------|------|
| [configs/.env.example](configs/.env.example) | 环境变量模板（6 种 API 提供商） |
| [configs/openclaw.service](configs/openclaw.service) | OpenClaw Gateway systemd 服务文件 |
| [scripts/setup-openclaw.sh](scripts/setup-openclaw.sh) | 一键部署脚本（交互式） |
| [scripts/commands-cheatsheet.sh](scripts/commands-cheatsheet.sh) | 运维命令速查卡 |
| [checklists/security-checklist.md](checklists/security-checklist.md) | 安全配置检查清单 |
| [checklists/troubleshooting.md](checklists/troubleshooting.md) | 常见问题排错指南（9 个场景） |

## 常见问题

遇到问题请查阅 [troubleshooting.md](checklists/troubleshooting.md)，覆盖 9 个场景：

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

## 下一步

部署完成后：

- 接入微信/企微 → 见 [openclaw-im/](../openclaw-im/)
- 配置大模型 → 见 [openclaw-models/](../openclaw-models/)
- 安全加固 → 对照 [security-checklist.md](checklists/security-checklist.md) 逐项检查
