#!/bin/bash
# ============================================================
# OpenClaw 一键部署脚本
# 课程：AI 业务流架构师 · 第二节课实战
#
# 使用方法（root 用户）：
#   chmod +x setup-openclaw.sh
#   ./setup-openclaw.sh
#
# 前置条件：
#   - Ubuntu 24.04 LTS（推荐火山引擎 2C4G ¥99/年）
#   - 已通过 SSH 连接到服务器
#   - 准备好大模型 API Key（OpenAI / DeepSeek / 豆包等均可）
#
# 部署架构（6 步）：
#   Step 1  购买并初始化云服务器（脚本自动完成系统更新）
#   Step 2  安装 Node.js 与 OpenClaw
#   Step 3  配置 API Key 并启动 Gateway
#   Step 4  安装 Tailscale
#   Step 5  配置 Tailscale Serve 与 Dashboard 访问（手动）
#   Step 6  开启 Tailscale SSH 并关闭公网 SSH（可选）
# ============================================================

set -e

echo "=========================================="
echo "  OpenClaw 一键部署脚本"
echo "  课程：AI 业务流架构师 · 第二节课"
echo "=========================================="
echo ""

# ==========================================================
# Step 1: 购买并初始化云服务器
# ==========================================================
# 购买部分由学员在云厂商控制台完成，脚本负责系统初始化。
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[Step 1/6] 初始化云服务器"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
apt update && apt upgrade -y
apt install -y curl git
echo ""
echo "✅ Step 1 完成：系统已更新"
echo ""

# ==========================================================
# Step 2: 安装 Node.js 与 OpenClaw
# ==========================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[Step 2/6] 安装 Node.js 与 OpenClaw"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 安装 Node.js 24（官方推荐：Node 24，最低要求 Node 22.16+）
NODE_MAJOR=""
if command -v node &> /dev/null; then
    NODE_MAJOR=$(node -v | grep -oP '(?<=v)\d+')
fi

if [ -z "$NODE_MAJOR" ] || [ "$NODE_MAJOR" -lt 24 ]; then
    echo "安装 Node.js 24..."
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
    apt install -y nodejs
else
    echo "Node.js $(node -v) 已安装，跳过"
fi

echo "Node.js: $(node -v)"
echo "npm: $(npm -v)"

# 安装 OpenClaw
echo ""
echo "安装 OpenClaw..."
npm install -g openclaw@latest

# 生成 shell 补全（避免 SSH 登录时报错）
mkdir -p /root/.openclaw/completions
openclaw completion > /root/.openclaw/completions/openclaw.bash 2>/dev/null || true

echo ""
echo "✅ Step 2 完成：Node.js $(node -v) + OpenClaw 已安装"
echo ""

# ==========================================================
# Step 3: 配置 API Key 并启动 Gateway
# ==========================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[Step 3/6] 配置 API Key 并启动 Gateway"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 确保配置目录存在
mkdir -p /root/.openclaw
mkdir -p /opt

# 配置 API Key
ENV_FILE="/opt/openclaw.env"
NEED_CONFIG=true

if [ -f "$ENV_FILE" ]; then
    if grep -q 'OPENAI_API_KEY=.' "$ENV_FILE" && ! grep -q 'OPENAI_API_KEY=sk-xxx' "$ENV_FILE"; then
        echo "API 配置已存在："
        echo "---"
        cat "$ENV_FILE"
        echo "---"
        read -rp "是否重新配置？[y/N]：" RECONFIG
        if [[ ! "$RECONFIG" =~ ^[Yy]$ ]]; then
            NEED_CONFIG=false
        fi
    fi
fi

if [ "$NEED_CONFIG" = true ]; then
    echo "请选择你的大模型 API 提供商："
    echo "  1) DeepSeek（推荐，国内性价比最高）"
    echo "  2) 豆包（火山引擎）"
    echo "  3) 通义千问（阿里云百炼）"
    echo "  4) Kimi（Moonshot AI）"
    echo "  5) OpenAI 官方"
    echo "  6) 其他（手动输入 Base URL）"
    echo ""
    read -rp "请输入编号 [1-6]（默认 1）：" PROVIDER_CHOICE
    PROVIDER_CHOICE=${PROVIDER_CHOICE:-1}

    case $PROVIDER_CHOICE in
        1) BASE_URL="https://api.deepseek.com/v1" ; PROVIDER_NAME="DeepSeek" ;;
        2) BASE_URL="https://ark.cn-beijing.volces.com/api/v3" ; PROVIDER_NAME="豆包" ;;
        3) BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1" ; PROVIDER_NAME="通义千问" ;;
        4) BASE_URL="https://api.moonshot.cn/v1" ; PROVIDER_NAME="Kimi" ;;
        5) BASE_URL="https://api.openai.com/v1" ; PROVIDER_NAME="OpenAI" ;;
        6) read -rp "请输入 Base URL：" BASE_URL ; PROVIDER_NAME="自定义" ;;
        *) BASE_URL="https://api.deepseek.com/v1" ; PROVIDER_NAME="DeepSeek" ;;
    esac

    echo ""
    read -rp "请输入你的 ${PROVIDER_NAME} API Key：" API_KEY

    if [ -z "$API_KEY" ]; then
        echo "❌ API Key 不能为空，请重新运行脚本。"
        exit 1
    fi

    cat > "$ENV_FILE" << ENV_EOF
OPENAI_API_KEY=${API_KEY}
OPENAI_BASE_URL=${BASE_URL}
ENV_EOF
    chmod 600 "$ENV_FILE"

    echo "✅ API 配置完成（${PROVIDER_NAME}）"
fi

# 配置 gateway 为 local 模式
openclaw config set gateway.mode local 2>/dev/null || true

# 配置 systemd 系统级服务
echo ""
echo "配置 systemd 服务..."

# 清理可能残留的用户级服务（避免端口冲突）
if systemctl --user is-active openclaw-gateway &> /dev/null 2>&1; then
    echo "检测到残留的用户级服务，正在清理..."
    systemctl --user stop openclaw-gateway 2>/dev/null || true
    systemctl --user disable openclaw-gateway 2>/dev/null || true
    echo "✅ 用户级服务已清理"
fi

OPENCLAW_BIN=$(which openclaw)

cat > /etc/systemd/system/openclaw.service << SERVICE_EOF
[Unit]
Description=OpenClaw Gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=/opt/openclaw.env
Environment=HOME=/root
ExecStart=${OPENCLAW_BIN} gateway --port 18789
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable openclaw

# 启动前检查端口占用
PORT_PID=$(ss -tlnp | grep ':18789' | grep -oP 'pid=\K[0-9]+' | head -1)
if [ -n "$PORT_PID" ]; then
    echo "⚠️  端口 18789 被 PID ${PORT_PID} 占用，正在清理..."
    kill "$PORT_PID" 2>/dev/null || true
    sleep 2
    if ss -tlnp | grep -q ':18789'; then
        kill -9 "$PORT_PID" 2>/dev/null || true
        sleep 1
    fi
    echo "✅ 端口已释放"
fi

systemctl start openclaw
sleep 3

if systemctl is-active --quiet openclaw; then
    echo ""
    echo "✅ Step 3 完成：Gateway 已启动并设为开机自启"
else
    echo ""
    echo "⚠️  Gateway 启动可能需要几秒，请稍后运行："
    echo "   systemctl status openclaw"
    echo "   journalctl -u openclaw --no-pager -n 20"
fi
echo ""

# ==========================================================
# Step 4: 安装 Tailscale
# ==========================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[Step 4/6] 安装 Tailscale"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if command -v tailscale &> /dev/null; then
    echo "Tailscale 已安装，跳过"
else
    curl -fsSL https://tailscale.com/install.sh | sh
    systemctl enable --now tailscaled
fi

# 持久化添加公网 DNS（防止 MagicDNS 导致 Let's Encrypt 证书获取超时）
# 注意：直接写 /etc/resolv.conf 会被云厂商 DHCP 续租覆盖，这里用 systemd-resolved 持久化
if [ -d /run/systemd/resolve ]; then
    # 使用 systemd-resolved（Ubuntu 24.04 默认）
    mkdir -p /etc/systemd/resolved.conf.d
    cat > /etc/systemd/resolved.conf.d/public-dns.conf << 'DNS_EOF'
[Resolve]
DNS=8.8.8.8 8.8.4.4
DNS_EOF
    systemctl restart systemd-resolved 2>/dev/null || true
    echo "   已通过 systemd-resolved 持久化公网 DNS 8.8.8.8"
else
    # 无 systemd-resolved 的系统，回退到直接写入 + 锁定文件
    if ! grep -q '8.8.8.8' /etc/resolv.conf 2>/dev/null; then
        # 先解锁（如果之前锁过）
        chattr -i /etc/resolv.conf 2>/dev/null || true
        echo "nameserver 8.8.8.8" >> /etc/resolv.conf
        # 锁定文件防止 DHCP 覆盖
        chattr +i /etc/resolv.conf 2>/dev/null || true
        echo "   已添加公网 DNS 8.8.8.8 并锁定 resolv.conf"
    fi
fi

echo ""
echo "✅ Step 4 完成：Tailscale 已安装"
echo ""

# ==========================================================
# 自动化部分结束，输出后续手动操作指南
# ==========================================================
echo "=========================================="
echo "  ✅ 自动化部署完成（Step 1-4）！"
echo "=========================================="
echo ""
echo "💡 常用命令："
echo "   systemctl status openclaw          # 查看 Gateway 状态"
echo "   journalctl -u openclaw -f          # 查看实时日志"
echo "   systemctl restart openclaw         # 重启 Gateway"
echo "   openclaw config get gateway        # 查看 Gateway 配置"
echo ""
echo ""
echo "=========================================="
echo "  接下来请手动完成 Step 5（必须）和 Step 6（可选）"
echo "=========================================="
echo ""
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[Step 5/6] 配置 Tailscale Serve 与 Dashboard 访问"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "5.1  Tailscale 认证（将服务器加入你的私有网络）："
echo "     sudo tailscale up"
echo "     # 按提示在浏览器中完成认证"
echo ""
echo "5.2  开启 Tailscale Serve（HTTPS 代理）："
echo "     tailscale serve --bg 18789"
echo ""
echo "5.3  预获取 HTTPS 证书（重要！避免首次访问超时）："
echo "     # 先获取你的 Tailscale 域名："
echo "     tailscale status --self --json | grep -m1 DNSName | tr -d ' \",' | cut -d: -f2 | sed 's/\.\$//'"
echo "     # 然后用输出的域名执行（例：tailscale cert myhost.tail1234.ts.net）："
echo "     tailscale cert <上面输出的域名>"
echo ""
echo "5.4  配置 allowedOrigins（必须！否则浏览器访问会报 origin not allowed）："
echo "     # 将 <你的域名> 替换为 5.3 中获取的 Tailscale 域名："
echo "     openclaw config set gateway.controlUi.allowedOrigins '[\"http://localhost:18789\",\"http://127.0.0.1:18789\",\"https://<你的域名>\"]'"
echo "     systemctl restart openclaw"
echo ""
echo "5.5  获取 Dashboard 访问地址："
echo "     openclaw dashboard --no-open"
echo "     # 将输出 URL 中的 127.0.0.1 替换为你的 Tailscale 域名"
echo "     # 例如：https://你的设备名.tailnet.ts.net/#token=你的令牌"
echo ""
echo "5.6  首次浏览器访问需要设备配对："
echo "     # 浏览器点 Connect 后如果提示 pairing required，在服务器执行："
echo "     openclaw devices list"
echo "     openclaw devices approve <Request 列中的 ID>"
echo "     # 然后回浏览器重新点击 Connect"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[Step 6/6] 开启 Tailscale SSH 并关闭公网 SSH（可选）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "   此步骤为安全加固，建议熟悉 Tailscale 后再操作。"
echo "   跳过不影响使用，公网 SSH 仍可正常连接。"
echo ""
echo "6.1  在服务器上开启 Tailscale SSH："
echo "     sudo tailscale set --ssh"
echo ""
echo "6.2  验证 Tailscale SSH（在你的 MacBook 本地终端执行）："
echo "     ssh root@<你的设备名>.tailnet.ts.net"
echo "     # ⚠️ 务必确认能连上再执行下一步！"
echo ""
echo "     # VS Code Remote SSH 配置（添加到本地 ~/.ssh/config）："
echo "     # Host openclaw-dev"
echo "     #     HostName <你的设备名>.tailnet.ts.net"
echo "     #     User root"
echo ""
echo "6.3  确认能连上后，关闭公网 SSH："
echo "     # ⚠️ 务必先完成 6.2 验证！否则关闭后将无法连接服务器！"
echo "     # 去云厂商控制台 → 安全组 → 删除 22 端口的放行规则"
echo ""
echo ""
echo "⚠️  代理工具注意事项："
echo "   如果你的笔记本使用了 Clash / V2Ray 等代理工具，"
echo "   需要配置 *.ts.net 和 100.0.0.0/8 走直连（DIRECT），"
echo "   否则浏览器可能无法通过 Tailscale 连接。"
echo ""
echo "=========================================="