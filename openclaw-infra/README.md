# OpenClaw 基础设施：部署、守护进程、安全穿透

> 30 分钟从零到能用的 OpenClaw 生产部署指南

## 你需要准备

| 项目 | 说明 | 费用 |
|------|------|------|
| 云服务器 | 推荐火山引擎 2C4G（或阿里云 / 腾讯云同配置），Ubuntu 24.04 LTS | ¥99/年 |
| 大模型 API Key | DeepSeek / 豆包 / 通义千问 / Kimi / OpenAI 均可 | 按用量 |
| Tailscale 账号 | https://tailscale.com （GitHub 登录即可） | 免费 |

## 一键部署

```bash
git clone https://github.com/DjangoPeng/agentic-ai.git
cd agentic-ai/openclaw-infra

chmod +x scripts/setup-openclaw.sh
sudo scripts/setup-openclaw.sh
```

脚本自动完成 4 个步骤：

| 步骤 | 内容 | 方式 |
|------|------|------|
| Step 1 | 系统更新、安装 curl / git | 自动 |
| Step 2 | 安装 Node.js 24 + `npm install -g openclaw` | 自动 |
| Step 3 | 交互式选择 API 提供商、配置 Key、启动 Gateway + systemd 守护 | 半自动（需输入 Key） |
| Step 4 | 安装 Tailscale、添加公网 DNS | 自动 |

脚本完成后，按屏幕提示手动完成 Step 5 和 Step 6：

### Step 5：配置 Tailscale Serve 与 Dashboard 访问（必须）

```bash
# 5.1 Tailscale 认证（将服务器加入你的私有网络）
sudo tailscale up
# 按提示在浏览器中完成认证

# 5.2 开启 Tailscale Serve（HTTPS 代理）
tailscale serve --bg 18789

# 5.3 预获取 HTTPS 证书（重要！避免首次访问超时）
# 先获取你的 Tailscale 域名：
tailscale status --self --json | grep -m1 DNSName | tr -d ' ",' | cut -d: -f2 | sed 's/\.$//'
# 然后用输出的域名执行：
tailscale cert <上面输出的域名>

# 5.4 配置 allowedOrigins（必须！否则浏览器报 origin not allowed）
# 将 <你的域名> 替换为 5.3 中获取的 Tailscale 域名：
openclaw config set gateway.controlUi.allowedOrigins \
  '["http://localhost:18789","http://127.0.0.1:18789","https://<你的域名>"]'
systemctl restart openclaw

# 5.5 获取 Dashboard 访问地址
openclaw dashboard --no-open
# 将输出 URL 中的 127.0.0.1 替换为你的 Tailscale 域名
# 例如：https://你的设备名.tailnet.ts.net/#token=你的令牌

# 5.6 首次浏览器访问需要设备配对
# 浏览器点 Connect 后如果提示 pairing required，在服务器执行：
openclaw devices list
openclaw devices approve <Request 列中的 ID>
# 然后回浏览器重新点击 Connect
```

### Step 6：开启 Tailscale SSH 并关闭公网 SSH（可选，安全加固）

```bash
# 6.1 在服务器上开启 Tailscale SSH
sudo tailscale set --ssh

# 6.2 验证 Tailscale SSH（在你的本地终端执行）
ssh root@<你的设备名>.tailnet.ts.net
# ⚠️ 务必确认能连上再执行下一步！

# 6.3 确认能连上后，去云厂商控制台 → 安全组 → 删除 22 端口的放行规则
# ⚠️ 务必先完成 6.2 验证！否则关闭后将无法连接服务器！
```

然后在个人设备安装 Tailscale，浏览器访问 `https://<你的设备名>.tailnet.ts.net` 即可进入 Dashboard。

## 常用命令

```bash
systemctl status openclaw          # 查看 Gateway 状态
journalctl -u openclaw -f          # 查看实时日志
systemctl restart openclaw         # 重启 Gateway
openclaw config get gateway        # 查看 Gateway 配置
openclaw --version                 # 查看版本
```

## 本目录文件说明

| 文件 | 说明 |
|------|------|
| [configs/.env.example](configs/.env.example) | 环境变量模板（6 种 API 提供商） |
| [configs/openclaw.service](configs/openclaw.service) | systemd 服务文件 |
| [scripts/setup-openclaw.sh](scripts/setup-openclaw.sh) | 一键部署脚本（交互式） |
| [scripts/commands-cheatsheet.sh](scripts/commands-cheatsheet.sh) | 运维命令速查卡 |
| [checklists/security-checklist.md](checklists/security-checklist.md) | 安全配置检查清单 |
| [checklists/troubleshooting.md](checklists/troubleshooting.md) | 常见问题排错指南（9 个场景） |

## 常见问题

遇到问题请查阅 [troubleshooting.md](checklists/troubleshooting.md)，覆盖 9 个场景：

| # | 问题 | 关键词 |
|---|------|-------|
| Q1 | 端口 18789 被占用 | `address already in use` |
| Q2 | tailscale up 卡住不动 | `timed out` |
| Q3 | Serve 成功但浏览器无法访问 | `ERR_CONNECTION_REFUSED` |
| Q4 | Dashboard 加载但认证失败 | `auth failed` |
| Q5 | Gateway 启动后立即退出 | `systemctl status openclaw` |
| Q6 | systemd 服务启动失败 | `failed` |
| Q7 | npm install 超时 | `timeout` / 网络问题 |
| Q8 | Tailscale 证书获取失败 | `acme` / `i/o timeout` |
| Q9 | Clash/VPN 代理导致无法访问 | `ERR_CONNECTION_CLOSED` |

> ⚠️ **代理工具注意：** 如果你的笔记本使用了 Clash / V2Ray 等代理工具，需要配置 `*.ts.net` 和 `100.0.0.0/8` 走直连（DIRECT），否则浏览器可能无法通过 Tailscale 连接。

## 下一步

部署完成后：

- 接入微信/企微 → 见 [openclaw-im/](../openclaw-im/)
- 配置大模型与 Embedding → 见 [openclaw-models/](../openclaw-models/)
- 安全加固 → 对照 [security-checklist.md](checklists/security-checklist.md) 逐项检查