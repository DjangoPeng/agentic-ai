# 第12节 实验手册：云端部署小红书自动发布 Skill

> 配套课程：AI 业务流架构师 · 第12节 云端执行体与跨端登录协作
> 前置条件：已准备好 `DjangoPeng/agentic-ai` 仓库（xhs-auto-publisher/ 目录），并能让龙虾访问目标云服务器
> 操作方式：把本实验中的完整 Prompt 复制给龙虾执行，学员不需要直接登录服务器
> 预计耗时：30-50 分钟

---

## 实验目标

1. 理解小红书自动发布 Skill 的云端最小可运行链路：生成二维码截图 -> 生成 payload -> 由龙虾转发到飞书群。
2. 完成一次标准云端部署：拉取仓库、安装系统依赖、初始化项目、复制 `.env`、设置 `MODE=draft`。
3. 验证 Playwright + Xvfb 能在 Ubuntu 服务器上启动浏览器并跑到扫码登录阶段。
4. 检查二维码截图和 lobster notify payload 是否正确生成。
5. 明确本节边界：只做可运行性验证，不配置 nginx，不配置 systemd，不真实发布内容。

---

## 实验说明

这一节不是要把小红书笔记真正发布出去，而是验证云端 Skill 是否具备最基本的运行能力。

当前项目只走一条链路：

```text
生成二维码截图 -> 生成 payload -> 后续由龙虾把图片发到飞书群
```

只要成功生成下面两个文件，就说明本节实验完成：

```text
runtime/runs/<run_id>/screenshots/login_qr.png
runtime/lobster-notify/<run_id>/login_qr.payload.json
```

> 注意：下面的 Prompt 是本实验的核心执行指令。复制给龙虾时请保持完整，不要拆开改写。

---

## 实验一：让龙虾部署并运行 Skill

在飞书中把下面整段发送给龙虾：

```text
你现在帮我部署一个 Skill 到云服务器。

目标仓库：
GitHub - DjangoPeng/agentic-ai（xhs-auto-publisher/ 目录）
https://github.com/DjangoPeng/agentic-ai/tree/main/xhs-auto-publisher

目标机器信息：
- Ubuntu 24.04.4 LTS
- root 用户
- 项目部署目录：~/projects/xhs-auto-publisher

部署要求：
1. 从 GitHub 拉取仓库到 `~/projects/xhs-auto-publisher`
2. 执行项目自带的系统依赖安装脚本：
   `bash ~/projects/xhs-auto-publisher/deploy/install_system_ubuntu.sh`
3. 执行项目自带的初始化脚本：
   `cd ~/projects/xhs-auto-publisher && bash deploy/bootstrap_project.sh`
4. 复制环境变量模板：
   `cd ~/projects/xhs-auto-publisher && cp deploy/env.example .env`
5. 这次先不要改复杂配置，不需要 nginx，不需要 `XHS_PUBLIC_RUNTIME_BASE_URL`
6. 这次只做“可运行性验证”，不要真的发布内容；把 `.env` 里的 `MODE` 设为 `draft`
7. 执行一次手动测试：
   `cd ~/projects/xhs-auto-publisher && bash deploy/run_with_xvfb.sh`
8. 运行后检查以下文件是否生成：
   - `runtime/runs/<run_id>/screenshots/login_qr.png`
   - `runtime/lobster-notify/<run_id>/login_qr.payload.json`
9. 如果已经生成二维码截图和 payload，就说明部署成功
10. 暂时先不要配置 systemd，先把手动验证跑通再说

重要说明：
- 这个项目当前只走一条链路：生成二维码截图 -> 生成 payload -> 后续由龙虾把图片发到飞书群
- 不要再额外配置公网二维码访问
- 不要引入 nginx 方案
- 不要删除仓库里的文档和示例文件
- 不要修改核心逻辑，除非遇到明确报错并且必须修复

你执行时请严格按步骤来，每完成一步就回报：
1. 执行了什么命令
2. 成功还是失败
3. 关键输出是什么
4. 如果失败，贴核心报错
5. 当前卡在哪一步

验收标准：
- 项目目录已正确部署到 `~/projects/xhs-auto-publisher`
- `.venv` 创建成功
- Playwright Chromium 安装成功
- 能成功跑起测试
- 成功生成 `login_qr.png`
- 成功生成 `login_qr.payload.json`

如果测试跑到需要扫码登录这一步，执行以下操作：
1. 读取 ~/projects/xhs-auto-publisher/runtime/lobster-notify/<run_id>/login_qr.payload.json
2. 取出 delivery.path 字段对应的图片文件
3. 把那张二维码图片直接发到飞书群（图片消息，不是路径文字）
4. 把 delivery.caption_lines 的内容作为说明文字一并发出
5. 等待用户确认扫码完成后再继续执行
```

### 确认要点

龙虾回报时，重点检查：

1. 仓库是否在 `~/projects/xhs-auto-publisher`
2. `.venv` 是否创建成功
3. Playwright Chromium 是否安装成功
4. `.env` 中是否是 `MODE=draft`
5. 是否生成 `login_qr.png`
6. 是否生成 `login_qr.payload.json`

---

## 实验二：判断部署是否通过

当龙虾回报执行结果后，用下面标准判断。

### 场景 A：成功跑到二维码阶段

期望看到类似信息：

```text
run_id:
<run_id>

二维码图片路径:
~/projects/xhs-auto-publisher/runtime/runs/<run_id>/screenshots/login_qr.png

payload 文件路径:
~/projects/xhs-auto-publisher/runtime/lobster-notify/<run_id>/login_qr.payload.json
```

如果两个文件都存在，本实验通过。

### 场景 B：系统依赖安装失败

重点看龙虾回报中的：

- `apt` 是否失败
- 是否是 root 用户
- Ubuntu 版本是否符合预期
- `install_system_ubuntu.sh` 的核心报错是什么

### 场景 C：Playwright 或 Chromium 初始化失败

重点看：

- `.venv` 是否存在
- `playwright` 是否能 import
- Chromium 是否安装成功
- 是否缺少 Linux 系统库

### 场景 D：没有生成二维码截图或 payload

重点看：

- `deploy/run_with_xvfb.sh` 是否真的跑起来
- 是否创建了 `runtime/runs/<run_id>/`
- `runtime/runs/<run_id>/screenshots/` 里是否有截图
- `runtime/lobster-notify/` 里是否有对应 run_id

---

## 验收标准

完成本实验时，应满足以下条件：

- 项目目录已正确部署到 `~/projects/xhs-auto-publisher`
- `.venv` 创建成功
- Playwright Chromium 安装成功
- 能成功跑起测试
- 成功生成 `login_qr.png`
- 成功生成 `login_qr.payload.json`
- 没有配置 nginx
- 没有配置 systemd
- 没有真实发布内容

---

## 实验记录

请记录你在实验过程中遇到的任何与预期不符的情况：

| # | 发生在哪一步 | 预期行为 | 实际行为 | 你的解决方法 |
|---|------------|----------|---------|------------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

## 常见问题排查

- GitHub 拉取失败：检查服务器网络，确认能访问 GitHub。
- 系统依赖安装失败：确认是 root 用户，检查 apt 源和 Ubuntu 版本。
- `.venv` 创建失败：查看 `deploy/bootstrap_project.sh` 的 Python 相关报错。
- Playwright Chromium 安装失败：重新执行初始化脚本，并确认系统依赖已安装。
- `run_with_xvfb.sh` 无法启动：检查 Xvfb 是否安装，查看 DISPLAY 和 Chromium 报错。
- 没有生成 `login_qr.png`：检查最近一次 `runtime/runs/<run_id>/actions.jsonl` 和 `screenshots/`。
- 没有生成 `login_qr.payload.json`：检查 `runtime/lobster-notify/<run_id>/` 是否生成，以及 payload 生成逻辑是否触发。

> 欢迎把你的实验记录和踩坑发现分享到课程社群。
