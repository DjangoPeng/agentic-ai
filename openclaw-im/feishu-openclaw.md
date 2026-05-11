# 飞书 × OpenClaw 部署操作手册

> **配套课程**：第4节 · 飞书（Feishu）原生深度集成与办公流打通  
> **前置条件**：已有 OpenClaw 运行环境（第2节课部署的云服务器）  
> **版本要求**：OpenClaw ≥ 2026.4.12

---

## 一、前置检查

### 1.1 OpenClaw 版本

```bash
openclaw --version
# 推荐 >= 2026.4.12
# 【升级】再次执行项目的一键安装脚本：sudo ./setup-openclaw.sh
```

### 1.2 飞书账号

飞书个人版免费即可，注册地址：https://www.feishu.cn

Lark（国际版）用户后续配置中 `domain` 需设为 `"lark"`。

### 1.3 网络要求

飞书 Channel 使用 WebSocket 出站连接，不需要公网 IP、域名或 HTTPS 证书。服务器需能访问 `open.feishu.cn`（国内）或 `open.larksuite.com`（国际版）。

---

## 二、扫码极速接入

```bash
openclaw channels login --channel feishu
```

用飞书手机 App 扫描终端显示的二维码。OpenClaw 自动完成以下操作：

- 在飞书开放平台创建企业自建应用
- 配置机器人能力与所需权限
- 配置 WebSocket 事件订阅
- 发布应用
- 将 App ID / App Secret 写入本地配置文件

完成后重启服务：

```bash
sudo systemctl restart openclaw
```

查看日志确认连接成功：

```bash
journalctl -u openclaw -f
# 或打开 OpenClaw Dashboard → 日志模块
# 应看到：[feishu][default] connected
```

### 2.1 DM（私聊）测试

在飞书中搜索机器人应用名，发送任意消息。Owner（扫码创建者）免配对，Agent 直接回复。

其他用户首次发私信会触发配对流程，需要在终端审批：

```bash
openclaw pairing list feishu
openclaw pairing approve feishu <配对码>
```

个人使用可跳过配对：

```bash
openclaw config set channels.feishu.dmPolicy open
sudo systemctl restart openclaw
```

### 2.2 群聊测试

1. 创建飞书测试群（或使用现有群）
2. 群设置 → 添加机器人 → 搜索应用名 → 添加
3. 在群里 @机器人 发消息，Agent 回复

默认 `requireMention: true`，必须 @机器人 才触发回复。

### 2.3 进阶：手动创建 App（企业级管控场景）

扫码接入会自动申请大量权限。企业环境下如需精确控制权限，可手动创建：

1. 访问 https://open.feishu.cn/app → 创建企业自建应用
2. 获取 App ID（`cli_xxx` 格式）和 App Secret
3. 添加应用能力 → 机器人
4. 权限管理 → 按需开通最小权限集
5. 事件与回调 → 使用长连接接收事件 → 添加 `im.message.receive_v1`
6. 版本管理与发布 → 创建版本 → 提交审核
7. 将凭证填入 OpenClaw：

```bash
openclaw channels add
# 选择 Feishu → 输入 App ID 和 App Secret
```

或手动编辑 `~/.openclaw/openclaw.json`：

```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "domain": "feishu",
      "connectionMode": "websocket",
      "accounts": {
        "default": {
          "appId": "cli_xxxxxxxxxxxxxx",
          "appSecret": "你的 App Secret"
        }
      }
    }
  }
}
```

> ⚠️ 扫码接入和手动创建二选一，不要混用，否则会出现两个重复的飞书应用。

---

## 三、安装飞书官方插件

### 3.1 安装新版插件

```bash
# 教学需要, 锁定版本 如需要更新请移除锁定 版本 @2026.4.8 标记 -> openclaw plugins install @larksuite/openclaw-lark --dangerously-force-unsafe-install
openclaw plugins install @larksuite/openclaw-lark@2026.4.8 --dangerously-force-unsafe-install
```

安全扫描会报 WARNING（环境变量访问 + 网络发送），这是飞书官方插件的正常行为，加 `--dangerously-force-unsafe-install` 绕过。

### 3.2 禁用内置旧版飞书插件

```bash
openclaw config set plugins.entries.feishu.enabled false --json
```

> ⚠️ **关键步骤**。不执行此命令会导致新旧插件 ID 冲突，新插件的日历、多维表格等工具无法暴露给 Agent。

### 3.3 重启服务

```bash
sudo systemctl restart openclaw
```

### 3.4 验证

在飞书 DM 中发送：

```
列出你当前所有可用的飞书相关工具和能力
```

Agent 应列出飞书文档、云盘、知识库、多维表格、日历、任务等能力。

---

## 四、补充用户身份权限

扫码创建的 App 默认申请了应用级权限，但部分操作（如日历创建、多维表格操作）还需要**用户身份权限**。以下是经过实操验证的完整权限清单。

访问 https://open.feishu.cn/app → 进入应用 → 权限管理，搜索并开通以下权限：

### A. 飞书日历最小完整集

| 权限标识 | 说明 |
|---------|------|
| `calendar:calendar` | 日历基础能力 |
| `calendar:calendar:read` | 读取日历信息与日程上下文 |
| `calendar:calendar.event:create` | 创建日历事件 |
| `calendar:calendar.event:update` | 修改日历事件 |

### B. 飞书多维表格最小完整集

**应用级：**

| 权限标识 | 说明 |
|---------|------|
| `base:app:create` | 创建新的多维表格应用 |

**字段级：**

| 权限标识 | 说明 |
|---------|------|
| `base:field:read` | 读取字段结构 |
| `base:field:create` | 新建字段 |
| `base:field:update` | 修改字段名称或配置 |

**记录级：**

| 权限标识 | 说明 |
|---------|------|
| `base:record:retrieve` | 读取记录列表 |
| `base:record:create` | 创建记录 |
| `base:record:delete` | 删除记录 |

### C. 飞书文档最小完整集

| 权限标识 | 说明 |
|---------|------|
| `docx:document:create` | 创建飞书文档 |
| `docx:document:readonly` | 读取文档内容 |
| `docx:document:write_only` | 写入文档内容 |

### D. Wiki / 知识库（文档创建链路依赖）

| 权限标识 | 说明 |
|---------|------|
| `wiki:node:create` | 创建知识库/文档节点 |
| `wiki:node:read` | 读取知识库/节点信息 |

### E. 文档媒体与白板（文档创建链路依赖）

| 权限标识 | 说明 |
|---------|------|
| `docs:document.media:upload` | 上传文档中的图片/媒体/附件 |
| `board:whiteboard:node:create` | 白板节点能力（复合内容创建链路依赖） |

> 补充权限后，Agent 可能会发送授权卡片链接，点击完成授权即可。具体需要开通哪些权限，以实际操作时 Agent 的提示为准——Agent 会在调用工具失败时告知缺少的具体权限。
>
> **一次性授权建议**：优先开通 A + B + C 三组共 14 个权限，覆盖日历、多维表格和文档的核心操作。D 和 E 组在文档创建过程中按需开通。

---

## 五、实战验证

### 5.1 实战一：飞书文档自动生成

```
帮我创建一篇飞书文档，标题是"OpenClaw 飞书集成测试报告"，
内容包括三个章节：测试环境、测试项目、测试状态
```

验证文档创建成功后，尝试追加内容：

```
在刚才创建的文档末尾追加一段内容："所有测试项目已通过"
```

### 5.2 实战二：飞书日历与待办联动

创建日程：

```
帮我在飞书日历里创建一个日程，明天上午 11 点，录制第四节课程，时长 1 小时
```

创建待办任务：

```
帮我创建一个待办任务："准备第四节课录制材料"，截止时间设为明天上午 10 点
```

联动操作：

```
帮我下周三下午 3 点安排一个"产品需求评审会"，
同时创建一个待办提醒我"整理产品需求清单"，截止时间设在会议前一天
```

### 5.3 实战三：Markdown → 飞书多维表格

准备一个 Markdown 文件（如竞品分析报告），包含表格数据。

在飞书中操作多维表格的步骤：

1. 在飞书中创建一个空的多维表格
2. 将多维表格分享给机器人（分享 → 搜索机器人名 → 编辑权限）
3. 将 Markdown 文件发到群里或 DM 中
4. @机器人 指令提取数据并写入多维表格

示例指令：

```
请读取我刚发的 Markdown 文件，提取其中的竞品对比表格数据，
写入到这个多维表格中：[多维表格 URL]
每个竞品作为一条记录，字段包括：产品名称、公司、核心定位、月活跃用户、定价模式
```

备选方案（不通过文件，直接创建）：

```
帮我创建一个飞书多维表格，名称为"AI Agent 竞品分析"，
包含以下字段：产品名称（文本）、公司（文本）、核心定位（文本）、月活跃用户（文本）、定价模式（文本）
然后添加以下记录：
1. OpenClaw，开源社区，本地优先个人AI助手，350万+，免费开源
2. Coze，字节跳动，低代码AI Bot构建平台，500万+，按量付费
3. Dify，开源社区，LLMOps开发平台，200万+，开源+企业版
```

---

## 六、多代理路由与群组策略

### 6.1 requireMention 策略

默认 `requireMention: true`，群里必须 @机器人 才回复。修改为所有消息都回复：

```bash
openclaw config set channels.feishu.requireMention false --json
sudo systemctl restart openclaw
```

按群设置：

```json
{
  "channels": {
    "feishu": {
      "groups": {
        "oc_xxx": {
          "requireMention": false
        }
      }
    }
  }
}
```

### 6.2 多 Agent Bindings 路由

将不同群路由到不同 Agent：

```json
{
  "bindings": [
    {
      "agentId": "tech-agent",
      "match": {
        "channel": "feishu",
        "peer": { "kind": "group", "id": "oc_tech_group_id" }
      }
    },
    {
      "agentId": "hr-agent",
      "match": {
        "channel": "feishu",
        "peer": { "kind": "group", "id": "oc_hr_group_id" }
      }
    }
  ]
}
```

获取群 ID：群聊 → 右上角菜单 → 设置 → 页面显示 `oc_xxx`。

### 6.3 DM 策略

| 策略 | 说明 |
|------|------|
| `pairing`（默认） | 新用户发私信需通过配对审批 |
| `allowlist` | 仅 `allowFrom` 列表中的用户可私聊 |
| `open` | 所有用户可直接私聊 |
| `disabled` | 禁用私聊 |

---

## 七、踩坑速查表

| 问题 | 原因 | 解决 |
|------|------|------|
| 能发消息但收不到 | 事件订阅未配置 | 飞书后台 → 事件与回调 → 添加 `im.message.receive_v1` |
| 日历/多维表格工具不可用 | 新旧插件 ID 冲突 | `openclaw config set plugins.entries.feishu.enabled false --json` + 重启 |
| 日历创建报权限不足 | 缺少用户身份权限 | 补充 `calendar:calendar.event:create` 等权限 |
| 扫码后出现两个应用 | 混用了扫码和手动创建 | 删除多余应用，只保留一个 |
| 插件安装被拦截 | 安全扫描误报 | 加 `--dangerously-force-unsafe-install` |
| Agent 用企微工具而非飞书 | 多平台 Skills 优先级冲突 | 指令中明确指定"用飞书"，或通过 SOUL.md 设定飞书优先规则 |
| `unknown channel id: feishu` | OpenClaw 版本过低 | 升级到 v2026.4.10+ |
| 多维表格操作失败 | 表格未分享给机器人 | 表格 → 分享 → 搜索机器人名 → 编辑权限 |

---

## 八、常用命令速查

```bash
# 服务管理
sudo systemctl restart openclaw      # 重启服务
sudo systemctl status openclaw       # 查看服务状态

# 日志
journalctl -u openclaw -f            # 实时日志（命令行）
# Dashboard → 日志模块               # 实时日志（可视化）

# Channel 管理
openclaw channels status --probe     # Channel 连接状态
openclaw config get channels.feishu  # 查看飞书配置

# 插件管理
openclaw plugins list                # 查看所有插件状态
openclaw plugins install <包名> --dangerously-force-unsafe-install  # 安装插件（绕过安全扫描）

# 配对管理
openclaw pairing list feishu         # 查看待审批配对
openclaw pairing approve feishu <码> # 审批配对
```
