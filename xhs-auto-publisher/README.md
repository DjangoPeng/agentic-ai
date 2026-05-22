# xhs-auto-publisher

一个面向云服务器的小红书图文自动发布 Skill。

这套项目的定位很明确：

- 在 Linux 云服务器上运行 Playwright/Chromium
- 自动打开小红书创作后台
- 检查登录态
- 遇到登录时生成二维码截图
- 通过龙虾平台把二维码图片直接转发到飞书群
- 人工扫码后继续执行发布流程

它不是“完全无人值守、绕过风控”的工具，而是一套带人工登录接管的浏览器自动化方案。

## 适合什么场景

适合：

- 已有自己授权的小红书账号
- 需要把图文内容发布流程放到云端执行
- 能接受扫码登录这一步由人处理
- 希望保留运行截图、DOM 快照、结果 JSON、登录缓存

不适合：

- 绕过验证码、滑块、人机校验
- 批量互动、批量养号
- 操作未授权账号

## 当前默认链路

现在仓库只保留一条默认链路：

1. 项目生成登录二维码截图
2. 项目生成 `runtime/lobster-notify/<run_id>/login_qr.payload.json`
3. 龙虾读取 payload
4. 龙虾把二维码图片直接发到飞书群
5. 用户扫码
6. 任务继续执行

也就是说：

- 不需要 `XHS_PUBLIC_RUNTIME_BASE_URL`
- 不需要为二维码再配 nginx 公网访问
- 不靠链接扫码，直接靠图片发群

## 仓库结构

```text
config/     平台配置与选择器
deploy/     云端安装、运行、systemd 脚本
docs/       部署文档、龙虾执行清单、通知协议
examples/   示例内容与素材
scripts/    CLI 入口
src/        核心发布逻辑
SKILL.md    Skill 说明
```

运行后会在本地产生：

```text
runtime/browser-profile/
runtime/runs/
runtime/lobster-notify/
```

这些目录默认不提交到 Git。

## 快速开始

### 1. 放到服务器目录

建议放在：

```bash
~/projects/xhs-auto-publisher
```

### 2. 安装系统依赖

```bash
bash ~/projects/xhs-auto-publisher/deploy/install_system_ubuntu.sh
```

### 3. 初始化项目环境

```bash
cd ~/projects/xhs-auto-publisher
bash deploy/bootstrap_project.sh
```

### 4. 配置环境变量

```bash
cp deploy/env.example .env
```

默认可用：

```env
MODE=publish
LOGIN_TIMEOUT=300
```

### 5. 手动执行一次

```bash
cd ~/projects/xhs-auto-publisher
bash deploy/run_with_xvfb.sh
```

## 关键文件

- [SKILL.md](./SKILL.md)
- [docs/cloud_deploy.md](./docs/cloud_deploy.md)
- [docs/DEPLOY_TODO.md](./docs/DEPLOY_TODO.md)
- [docs/LOBSTER_NOTIFY_PROTOCOL.md](./docs/LOBSTER_NOTIFY_PROTOCOL.md)

## 运行产物

每次运行会写入：

```text
runtime/runs/<run_id>/
```

通常包含：

- `actions.jsonl`
- `result.json`
- `content.normalized.json`
- `screenshots/*.png`
- `dom/*.html`

如果需要扫码，还会生成：

```text
runtime/lobster-notify/<run_id>/login_qr.payload.json
```

## GitHub 用途

这个仓库就是给后续龙虾从 GitHub 拉取并部署用的。

推荐部署源：

```text
https://github.com/DjangoPeng/agentic-ai/tree/main/xhs-auto-publisher
```

## 说明

当前这版是单机、单浏览器、单任务顺序执行方案。

如果后面要继续增强，可以再加：

- HTTP API 触发
- 多账号隔离
- 定时任务
- 历史运行清理
- 更正式的龙虾接入脚本
