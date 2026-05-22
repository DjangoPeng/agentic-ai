# XHS Auto Publisher Cloud 云端部署说明

这份文档只保留一条默认方案：

- 项目在云服务器生成登录二维码截图
- 项目写出标准化 payload 文件
- 龙虾读取 payload
- 龙虾把二维码图片直接发到飞书群
- 你扫码后，任务继续执行

不再依赖 `XHS_PUBLIC_RUNTIME_BASE_URL`，也不要求为了二维码再单独配 nginx 公网访问。

## 1. 目标

我们要部署的是独立云端版：

- 项目目录：`~/projects/xhs-auto-publisher`
- 运行方式：Playwright + Chromium + `xvfb`
- 登录方式：人工扫码接管
- 通知方式：龙虾代发飞书群图片消息

## 2. 服务器最低要求

建议至少满足：

- Ubuntu 22.04+，你现在的 Ubuntu 24.04.4 LTS 可以
- 2 vCPU
- 4G 左右内存
- 20G 以上剩余磁盘
- root 权限

你现在这台火山引擎机器，跑单任务顺序执行是够的。

## 3. 需要装什么

分两层看。

### 系统级

这部分是整台机器共用的：

- `python3`
- `python3-venv`
- `python3-pip`
- `xvfb`
- Playwright/Chromium 依赖库

这里最关键的是：

- 要有浏览器内核
- 要有 `xvfb`

因为云服务器通常没桌面，但小红书这类页面更适合用“有头浏览器”方式跑。

### 项目级

这部分只属于当前目录：

- `.venv`
- `requirements.txt` 里的 Python 依赖
- Playwright Chromium
- `runtime/` 运行目录

## 4. 推荐目录结构

```text
~/projects/xhs-auto-publisher/
~/projects/xhs-auto-publisher/runtime/
~/projects/xhs-auto-publisher/runtime/browser-profile/
~/projects/xhs-auto-publisher/runtime/runs/
~/projects/xhs-auto-publisher/runtime/lobster-notify/
```

说明：

- `runtime/browser-profile/` 要持久化保存
- `runtime/runs/` 保存每次执行的截图、日志、结果
- `runtime/lobster-notify/` 给龙虾消费通知 payload

## 5. 登录二维码接管方式

云端默认流程如下：

1. 打开小红书登录页
2. 截图保存二维码
3. 写出 `login_qr.payload.json`
4. 龙虾读取这个 payload
5. 龙虾把二维码图片直接发到飞书群
6. 你手机扫码
7. Agent 轮询登录状态
8. 登录成功后继续发布

重点是：

- 不是靠公网链接扫码
- 是靠“图片直接发群”扫码

## 6. 当前默认通知机制

配置文件 [config/app.json](../config/app.json) 里已经默认是：

```json
{
  "notify_qr_via": "lobster_channel"
}
```

这表示项目不会自己发飞书 webhook，而是只负责生成 payload，由龙虾来代发。

## 7. 龙虾需要做什么

龙虾只要实现下面这件事：

1. 监听或读取 `runtime/lobster-notify/<run_id>/login_qr.payload.json`
2. 取出其中的 `delivery.path`
3. 把这张图片发到飞书群
4. 把 `delivery.caption_lines` 一并作为说明文字发出

协议说明见：

- [LOBSTER_NOTIFY_PROTOCOL.md](./LOBSTER_NOTIFY_PROTOCOL.md)

## 8. 部署步骤

### 第一步：放到服务器目录

建议统一放这里：

```bash
~/projects/xhs-auto-publisher
```

### 第二步：安装系统依赖

执行：

```bash
bash ~/projects/xhs-auto-publisher/deploy/install_system_ubuntu.sh
```

### 第三步：初始化项目环境

执行：

```bash
cd ~/projects/xhs-auto-publisher
bash deploy/bootstrap_project.sh
```

### 第四步：准备环境变量

执行：

```bash
cd ~/projects/xhs-auto-publisher
cp deploy/env.example .env
```

当前这版只保留两个常用项：

```env
MODE=publish
LOGIN_TIMEOUT=300
```

说明：

- `MODE=draft` 表示只到草稿/发布前
- `MODE=publish` 表示真正触发发布
- `LOGIN_TIMEOUT` 是扫码等待时长，单位秒

### 第五步：手动跑一次

执行：

```bash
cd ~/projects/xhs-auto-publisher
bash deploy/run_with_xvfb.sh
```

检查是否出现：

- 浏览器正常拉起
- `runtime/runs/<run_id>/screenshots/login_qr.png`
- `runtime/lobster-notify/<run_id>/login_qr.payload.json`

### 第六步：接通龙虾转发

龙虾收到 payload 后，应直接把二维码图片发到飞书群。

这一步接通后，你就可以在飞书群里扫码登录。

### 第七步：再考虑托管运行

确认手动执行没问题后，再启用 systemd：

```bash
cp ~/projects/xhs-auto-publisher/deploy/systemd/xhs-auto-publisher-cloud.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable xhs-auto-publisher-cloud.service
```

## 9. 为什么不再需要 `XHS_PUBLIC_RUNTIME_BASE_URL`

因为我们现在走的是：

- 龙虾直接发图片

而不是：

- 先生成图片
- 再暴露公网地址
- 再把公网链接发给你

后者要多一层静态文件服务和公网访问控制，链路更长，也更容易出问题。你现在这个场景，完全没必要。

## 10. 风险点

这版仍然要注意：

- 云服务器 IP 可能触发小红书额外风控
- 登录态可能比本机更容易失效
- 扫码二维码有时效
- 小红书页面结构变化时，需要更新选择器和发布逻辑

## 11. 当前结论

对你现在这套来说，最合适的方案就是：

- 云服务器负责跑浏览器
- 项目负责截二维码和写 payload
- 龙虾负责把图片发到飞书群
- 你负责扫码

简单，够用，也最稳。
