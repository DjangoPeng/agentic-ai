# OpenClaw 常见问题排错指南

> 课程：AI 业务流架构师 · 第二节课
> 实战过程中遇到问题，按以下步骤排查

---

## Q1：openclaw gateway 报端口占用

**现象：** `Error: listen EADDRINUSE: address already in use :::18789`

**排查步骤：**
```bash
# 1. 查看谁占用了 18789 端口
ss -tlnp | grep 18789

# 2. 如果是残留的旧进程，杀掉
kill <PID>

# 3. 如果是残留的用户级服务
systemctl --user stop openclaw-gateway 2>/dev/null
systemctl --user disable openclaw-gateway 2>/dev/null

# 4. 重新启动系统级服务
sudo systemctl restart openclaw
```

---

## Q2：systemd 服务启动失败

**现象：** `systemctl status openclaw` 显示 `failed`

**排查步骤：**
```bash
# 1. 查看详细错误
journalctl -u openclaw --no-pager -n 30

# 2. 常见原因：
# - openclaw 命令路径不对 → which openclaw 确认路径，更新 ExecStart
# - EnvironmentFile 不存在 → 确认 /opt/openclaw.env 存在且有内容
# - .env 内容无效（占位符未替换）→ cat /opt/openclaw.env 检查
# - 端口被占用 → 参考 Q1

# 3. 修改 service 文件后重新加载
sudo systemctl daemon-reload
sudo systemctl restart openclaw
```

---

## Q3：tailscale up 卡住不动

**现象：** 执行 `tailscale up` 后长时间无响应，不弹出授权链接

**排查步骤：**
```bash
# 1. 重启 tailscaled 服务
sudo systemctl restart tailscaled

# 2. 重新认证
sudo tailscale up --reset

# 3. 如果仍然卡住，检查网络
curl -I https://controlplane.tailscale.com
```

---

## Q4：Tailscale Serve 配置后浏览器访问超时

**现象：** `tailscale serve status` 显示正常，浏览器打不开或 HTTPS 证书错误

**排查步骤：**
```bash
# 1. 确认本地服务正常
curl http://localhost:18789/health

# 2. 预获取证书（关键！MagicDNS 可能导致 Let's Encrypt 解析超时）
# 先获取域名
tailscale status --self --json | grep -m1 DNSName | tr -d ' ",' | cut -d: -f2 | sed 's/\.$//'
# 用域名获取证书
tailscale cert <你的域名>

# 3. 确认已添加公网 DNS
grep '8.8.8.8' /etc/resolv.conf
# 如果没有，添加：
echo "nameserver 8.8.8.8" >> /etc/resolv.conf

# 4. 确认个人设备登录了同一 Tailscale 账号
tailscale status
```

---

## Q5：Dashboard 显示 "origin not allowed"

**现象：** 浏览器能打开页面，但控制台报错 `origin not allowed`

**解决方案：**
```bash
# 获取你的 Tailscale 域名
tailscale status --self --json | grep -m1 DNSName | tr -d ' ",' | cut -d: -f2 | sed 's/\.$//'

# 配置 allowedOrigins（替换 <你的域名> 为上一步输出）
openclaw config set gateway.controlUi.allowedOrigins \
  '["http://localhost:18789","http://127.0.0.1:18789","https://<你的域名>"]'

# 重启生效
sudo systemctl restart openclaw
```

---

## Q6：浏览器提示 "pairing required" / 设备配对

**现象：** 浏览器点击 Connect 后提示需要设备配对

**解决方案：**
```bash
# 1. 在服务器上查看待批准的设备
openclaw devices list

# 2. 批准你的浏览器设备（复制 Request 列中的 ID）
openclaw devices approve <Request ID>

# 3. 回浏览器重新点击 Connect
```

---

## Q7：代理工具导致 Tailscale 连接失败

**现象：** 笔记本使用 Clash / Clash Verge / V2Ray 等代理工具时，浏览器无法通过 Tailscale 域名访问，SSH 也连不上

**解决方案：**

在代理工具的配置中添加 Tailscale 绕过规则：

**Clash Verge Rev（在 Merge.yaml 中添加）：**
```yaml
prepend-rules:
  - DOMAIN-SUFFIX,ts.net,DIRECT
  - IP-CIDR,100.64.0.0/10,DIRECT,no-resolve
```

**其他 Clash 客户端：** 在 rules 部分最前面添加上述两行

**原理：** Tailscale 使用 100.64.0.0/10 网段和 *.ts.net 域名。如果代理工具拦截了这些流量，就无法走 Tailscale 隧道。

---

## 通用排查思路

遇到任何问题，按这个顺序排查：

1. **看日志** — `journalctl -u openclaw -f`
2. **看状态** — `systemctl status openclaw` + `tailscale status`
3. **看端口** — `ss -tlnp | grep 18789`
4. **看网络** — `curl localhost:18789/health` + `tailscale ping <device>`
5. **重启** — `sudo systemctl restart openclaw`
