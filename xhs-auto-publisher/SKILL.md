---
name: xhs-auto-publisher
description: 面向云服务器的小红书图文自动发布 Skill。适用于需要在 Linux 云服务器上，通过 Playwright/CDP、二维码人工接管、登录缓存、龙虾代发飞书群图片消息、截图留痕与审计日志来完成小红书草稿或发布流程的场景。
---

# XHS Auto Publisher Cloud

这个 Skill 是云端执行版，不是本机版替代品。

它主要解决四件事：

- 在 Linux 云服务器上跑浏览器自动化
- 把登录二维码交给人扫码
- 把登录状态缓存起来
- 把执行结果留痕

## 默认链路

当前项目只保留一条默认链路：

1. Agent 打开小红书登录页
2. Agent 截出二维码图片
3. 项目生成 `login_qr.payload.json`
4. 龙虾读取 payload
5. 龙虾把二维码图片直接发到飞书群
6. 用户扫码
7. Agent 继续执行

不依赖公网二维码链接，不依赖 `XHS_PUBLIC_RUNTIME_BASE_URL`。

## 适用场景

适合：

- 在云服务器上跑小红书图文草稿/发布
- 需要人工扫码接管登录
- 需要持久化浏览器 profile
- 需要截图、日志、DOM 快照
- 需要把标准化部署交给龙虾执行

不适合：

- 绕过验证码、滑块、人机验证
- 批量互动、批量点赞、批量评论
- 操作未授权账号

## 项目结构

- `config/`：平台配置与选择器
- `src/`：发布逻辑、登录检测、通知模块
- `scripts/`：CLI 入口
- `deploy/`：部署脚本与 systemd 示例
- `docs/`：部署说明和龙虾执行文档
- `runtime/`：浏览器 profile、截图、运行结果

## 部署分层

### 系统级

这部分影响整台机器：

- `python3`
- `python3-venv`
- `python3-pip`
- `xvfb`
- 浏览器运行依赖

### 项目级

这部分只属于当前目录：

- `.venv`
- Python 依赖
- Playwright Chromium
- `runtime/`

## 推荐目录

```text
~/projects/xhs-auto-publisher
~/projects/xhs-auto-publisher/runtime
~/projects/xhs-auto-publisher/runtime/browser-profile
~/projects/xhs-auto-publisher/runtime/runs
~/projects/xhs-auto-publisher/runtime/lobster-notify
```

## 输入格式

发布内容使用 JSON 文件，例如：

```json
{
  "title": "OpenClaw 能帮业务团队做什么？",
  "body": "很多团队不是缺 AI 聊天工具，而是缺一个能把业务流程真正跑起来的数字员工。",
  "topics": ["OpenClaw", "AI工具", "浏览器自动化"],
  "images": ["assets/cover.jpg"],
  "mode": "publish"
}
```

## 环境变量

当前只保留最常用的两个：

```env
MODE=publish
LOGIN_TIMEOUT=300
```

## 运行方式

手动运行：

```bash
cd ~/projects/xhs-auto-publisher
bash deploy/run_with_xvfb.sh
```

## 执行流程

1. 校验内容和图片
2. 检查重复发布保护
3. 启动持久化 Chromium profile
4. 读取登录缓存，默认 12 小时
5. 检查是否已登录
6. 如未登录，生成二维码截图并写出龙虾通知 payload
7. 龙虾把二维码图片发到飞书群
8. 用户扫码后继续
9. 上传图片、填写内容、触发发布
10. 保存截图、日志、DOM 快照和结果 JSON

## 运行产物

每次执行都会写入：

```text
runtime/runs/<timestamp>/
```

包含：

- `actions.jsonl`
- `result.json`
- `content.normalized.json`
- `screenshots/*.png`
- `dom/*.html`

通知文件会写入：

```text
runtime/lobster-notify/<run_id>/login_qr.payload.json
```

## 文档入口

- [docs/cloud_deploy.md](./docs/cloud_deploy.md)
- [docs/DEPLOY_TODO.md](./docs/DEPLOY_TODO.md)
- [docs/LOBSTER_NOTIFY_PROTOCOL.md](./docs/LOBSTER_NOTIFY_PROTOCOL.md)

## 当前定位

这不是并发平台，而是一套稳妥的单机顺序执行方案：

- 单机
- 单浏览器
- 单任务
- 人工扫码接管
- 有留痕
- 可复跑
