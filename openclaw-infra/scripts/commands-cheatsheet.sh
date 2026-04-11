#!/bin/bash
# ============================================================
# OpenClaw 运维命令速查卡
# 课程：AI 业务流架构师 · 第二节课
# 建议打印或截图保存
# ============================================================

# ==================== systemd 管理 ====================

sudo systemctl enable openclaw     # 设置开机自启
sudo systemctl start openclaw      # 启动服务
sudo systemctl stop openclaw       # 停止服务
sudo systemctl restart openclaw    # 重启服务
sudo systemctl status openclaw     # 查看状态
journalctl -u openclaw -f          # 实时查看日志
journalctl -u openclaw --since '1 hour ago'  # 最近 1 小时日志

# ==================== OpenClaw 管理 ====================

openclaw gateway --port 18789                     # 手动启动 gateway（调试用）
openclaw config get gateway                       # 查看 gateway 配置
openclaw config set <key> <value>                 # 修改配置
openclaw dashboard --no-open                      # 获取 Dashboard URL + Token
openclaw devices list                             # 查看已配对设备
openclaw devices approve <id>                     # 批准设备配对请求

# ==================== Tailscale ====================

sudo tailscale up                  # 启动并认证
sudo tailscale down                # 断开连接
tailscale status                   # 查看设备列表
tailscale status --self --json     # 查看本机详细信息（含域名）
tailscale serve --bg 18789         # 开启 Serve（私有访问）
tailscale serve status             # 查看 Serve 状态
tailscale serve 18789 off          # 关闭 Serve
tailscale funnel --bg 18789        # 开启 Funnel（公网访问）
tailscale funnel 18789 off         # 关闭 Funnel
tailscale cert <域名>              # 预获取 HTTPS 证书
tailscale ping <device>            # 测试连通性
sudo tailscale set --ssh           # 启用 Tailscale SSH
ssh user@device.tailnet.ts.net     # 通过 Tailscale SSH 连接

# ==================== Gateway 认证配置 ====================

openclaw config set gateway.mode local                          # 绑定本机
openclaw config set gateway.controlUi.allowedOrigins '["http://localhost:18789","https://你的域名.tailnet.ts.net"]'
                                                                # 配置允许的来源域名

# ==================== 故障排查 ====================

ss -tlnp | grep 18789             # 检查端口占用
curl http://localhost:18789/health # 检查服务健康状态
journalctl -u openclaw --no-pager -n 30  # 最近30行日志
tailscale status                   # 检查 Tailscale 连接
node -v                            # 检查 Node.js 版本（需 ≥ 22.16）
which openclaw                     # 检查 OpenClaw 安装路径
