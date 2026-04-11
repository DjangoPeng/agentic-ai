# OpenClaw 安全配置检查清单

> 课程：AI 业务流架构师 · 第二节课
> 完成实战后，逐项检查，确保每一项都打勾

---

## 🔴 网络层（最高优先级）

- [ ] OpenClaw gateway 绑定 loopback（`gateway.mode local`）
- [ ] Tailscale 已安装并 `tailscale up` 认证成功
- [ ] Tailscale Serve 已配置 `tailscale serve --bg 18789`
- [ ] 已添加公网 DNS（`echo "nameserver 8.8.8.8" >> /etc/resolv.conf`）
- [ ] 云服务器安全组：**关闭所有入站端口**（包括 22/SSH，改用 Tailscale SSH）


**验证命令：**
```bash
ss -tlnp | grep 18789
# 应显示 127.0.0.1:18789，不应显示 0.0.0.0:18789

tailscale serve status
# 应显示 serve 已启用
```

---

## 🟡 认证层

- [ ] Gateway 认证已配置（`openclaw dashboard --no-open` 能输出 Token URL）
- [ ] `allowedOrigins` 已配置 Tailscale 域名
- [ ] 设备配对已完成（`openclaw devices list` 显示 approved）

**验证命令：**
```bash
openclaw config get gateway
# 确认 mode 为 local

curl http://localhost:18789/health
# 应返回正常响应
```

---

## 🔵 运维层

- [ ] systemd 服务已创建并 `systemctl enable openclaw`
- [ ] EnvironmentFile 指向 `/opt/openclaw.env`（权限 600）
- [ ] Restart=always 已配置
- [ ] Tailscale SSH 已启用 `sudo tailscale set --ssh`
- [ ] 公网 SSH（22 端口）已在安全组中删除
- [ ] Node.js 版本 ≥ 22.16（推荐 24）

**验证命令：**
```bash
sudo systemctl status openclaw     # 应显示 active (running)
tailscale status                    # 应显示设备在线
node -v                             # 应显示 v24.x
```

---

## ✅ 完成确认

全部检查通过后，你的 Agent 具备：

| 能力 | 状态 |
|------|------|
| 7×24 不掉线 | ✅ systemd Restart=always + enable 开机自启 |
| 公网不可见 | ✅ 零公网 IP，Shodan/Censys 扫不到 |
| 认证保护 | ✅ Gateway Token + 设备配对 |
| 端到端加密 | ✅ WireGuard 隧道 + Tailscale Serve HTTPS |
| 数据主权 | ✅ 数据全在你自己的服务器上 |
