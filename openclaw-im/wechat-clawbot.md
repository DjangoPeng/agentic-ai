# 微信 ClawBot 接入指南

> 适用版本：OpenClaw >= 2026.3.13 · 微信 iOS/Android 最新版（>= 8.0.70）

---

## 一、这是什么？

微信 ClawBot 是腾讯官方推出的微信插件，让你的 OpenClaw Agent 直接以「微信联系人」的形式出现在你的微信聊天列表中。你在微信里给它发消息，就是在和你自己部署的 OpenClaw 对话。

**核心特点：**

- 腾讯官方插件，走正规插件体系，不用担心封号
- 仅作为消息通道，不会自动化操作你的微信账号
- 你在 OpenClaw 里配置的人格、记忆、Skills 全部保留，只是入口变成了微信
- iOS 和 Android 均支持

**当前限制：**

- 仅支持一对一私聊，暂不支持群聊
- ClawBot 仅接收 OpenClaw 24 小时内的回复
- 插件仍在逐步放量中，部分用户可能暂时看不到入口

---

## 二、前提条件

在开始之前，请确认以下环境已就绪：

| 项目 | 要求 |
|------|------|
| OpenClaw | 已安装并正常运行（本地或云服务器均可） |
| OpenClaw 版本 | 建议 2026.3.13 ~ 2026.4.x（过高版本可能有兼容性问题） |
| 微信版本 | iOS / Android 均需更新至最新版（>= 8.0.70） |
| Node.js | >= 22.0（OpenClaw 运行环境已包含） |

---

## 三、安装步骤

### Step 1：确认微信已灰度到 ClawBot 插件

打开手机微信，依次进入：

```
我 → 设置 → 插件
```

在插件列表中查看是否有 **「微信 ClawBot」** 选项。

> **常见问题：** 进入后提示"暂无可用的插件"，只看到微信输入法。
> **解决方法：** 从手机后台彻底杀掉微信（不是最小化），重新打开微信，再次进入插件页面。

如果看到了 ClawBot 插件，进入插件详情页，记下页面上显示的安装命令（或直接使用下面的命令）。

### Step 2：在 OpenClaw 服务器上安装微信插件

SSH 登录到运行 OpenClaw 的服务器（或在本地电脑的终端中），执行：

```bash
npx -y @tencent-weixin/openclaw-weixin-cli@latest install
```

安装过程会自动完成以下操作：

1. 下载并安装微信 Channel 插件
2. 启用插件
3. 在终端显示一个二维码

> **注意：** 安装完成后会自动重启 OpenClaw 网关。如果你的 OpenClaw 由 systemd 管理，安装脚本可能无法自动重启，需要手动执行：
> ```bash
> systemctl restart openclaw
> ```
> 然后通过以下命令重新生成二维码：
> ```bash
> openclaw channels login --channel openclaw-weixin
> ```

### Step 3：微信扫码绑定

1. 打开手机微信
2. 进入 ClawBot 插件详情页，点击「扫一扫」
3. 扫描终端上显示的二维码
4. 微信端会弹出确认页面，提示"将 OpenClaw 连接到微信"
5. 点击绿色的 **「连接」** 按钮

等待几秒，终端会显示：

```
✅ 与微信连接成功！
[openclaw-weixin] 正在重启 OpenClaw Gateway...
```

### Step 4：开始对话

连接成功后，微信里会出现一个 **「微信 ClawBot」** 的对话入口（带有灰色 AI 标识）。

点进去发送第一条消息：

```
你好，你是谁？
```

如果 Agent 正常回复，说明接入成功。

---

## 四、常见问题排查

| 症状 | 原因 | 解决方案 |
|------|------|----------|
| 插件列表里看不到 ClawBot | 未灰度到 / 微信版本过低 | 更新微信至最新版，杀掉重开；若仍无，需等待灰度放量 |
| 终端不显示二维码 | 安装脚本异常 | 手动执行 `openclaw channels login --channel openclaw-weixin` |
| 扫码后无反应 | 网关未启动 | 执行 `systemctl restart openclaw` 后重试 |
| 发消息没回复 | 网关未正常连接 / 模型 API 异常 | 查看日志 `journalctl -u openclaw -f`，检查是否有报错 |
| 回复延迟很久（>30秒） | 模型冷启动 / 网络延迟 | 首次回复可能较慢，后续会快很多 |
| 聊天列表里找不到 ClawBot | 已知问题，对话入口不显示在列表 | 在微信搜索框搜索"微信 ClawBot"或搜索聊天记录内容 |

---

## 五、进阶配置

### 多微信号接入

如果你想让多个微信号都能和同一个 OpenClaw 对话：

```bash
openclaw channels login --channel openclaw-weixin
```

每次执行会生成新的二维码，用新的微信号扫码即可。多个微信号的对话上下文互相隔离。

### 查看插件状态

```bash
openclaw plugins list
```

确认 `openclaw-weixin` 状态为 `enabled`。

### 卸载插件

```bash
openclaw plugins uninstall openclaw-weixin
systemctl restart openclaw
```

---

## 六、安全提醒

- ClawBot 仅作为消息通道，不会读取你的微信聊天记录、朋友圈或其他数据
- 你的 Agent 可以操作服务器（取决于 Skills 和权限配置），请务必在 SOUL.md 中设定好安全边界
- 建议在 SOUL.md 中明确禁止 Agent 执行危险操作（如删除文件、修改系统配置等）
