# 火山引擎 Coding Plan 购买与配置指南

> 适用版本：OpenClaw >= 2026.3.x · 火山引擎方舟平台

---

## 一、这是什么？

火山引擎方舟 **Coding Plan** 是为开发者量身定制的大模型订阅服务。一个订阅即可使用多款国产顶级模型（Kimi K2.5、DeepSeek V3.2、GLM-4.7、豆包 Seed Code 等），采用固定月费模式，超出额度自动停止计费，不会产生"天价账单"。

**为什么 OpenClaw 用户需要 Coding Plan？**

- OpenClaw 是"Token 大户"——Agent 模式下每次对话的实际消耗是普通聊天的 5-10 倍（工具调用、上下文注入、Skills 执行等）
- Coding Plan 的包月模式让你可以放心使用，不用时刻盯着用量
- 同时提供 Embedding 模型，用于 OpenClaw 的记忆搜索功能（语义向量检索）

---

## 二、购买 Coding Plan

### Step 1：注册/登录火山引擎

前往 https://www.volcengine.com 注册账号并完成实名认证。

### Step 2：订阅 Coding Plan

访问 Coding Plan 订阅页面：

```
https://www.volcengine.com/activity/codingplan
```

选择套餐：

| 套餐 | 适合场景 | 说明 |
|------|---------|------|
| **Lite** | 个人轻度使用 | 每天约 20-30 次有效对话 |
| **Pro** | 个人重度使用 / 小团队 | 每天 50+ 次有效对话，推荐 |

> **建议：** 新用户从 Lite 起步体验，不够用再升级 Pro。

### Step 3：获取 API Key

访问 API Key 管理页面：

```
https://console.volcengine.com/ark/region:ark+cn-beijing/apikey
```

1. 点击 **「创建 API Key」**
2. 生成后复制密钥
3. **妥善保管，不要泄露**

> 如果你之前已经有火山引擎的 API Key，购买 Coding Plan 后原有的 Key 可以直接使用，不需要重新创建。

---

## 三、配置 OpenClaw 使用 Coding Plan

### 关键区分：Coding Plan vs 在线推理

| 项目 | Coding Plan（包月） | 在线推理（按量计费） |
|------|-------------------|-------------------|
| Base URL | `https://ark.cn-beijing.volces.com/api/coding/v3` | `https://ark.cn-beijing.volces.com/api/v3` |
| 计费方式 | 固定月费，超额自动停止 | 按 Token 计费，无上限 |

> ⚠️ **最常见的错误：** 把 Base URL 写成 `/api/v3`（在线推理地址），导致不走 Coding Plan 额度而产生额外费用。正确地址是 `/api/coding/v3`。

### Step 1：编辑 OpenClaw 配置文件

```bash
nano ~/.openclaw/openclaw.json
```

#### 配置大模型

在 `models.providers` 中添加或修改 `volcengine` 配置：

```json
"models": {
    "mode": "merge",
    "providers": {
        "volcengine": {
            "baseUrl": "https://ark.cn-beijing.volces.com/api/coding/v3",
            "apiKey": "你的API Key",
            "api": "openai-completions",
            "models": [
                {
                    "id": "kimi-k2.5",
                    "name": "Kimi K2.5"
                },
                {
                    "id": "deepseek-v3.2",
                    "name": "DeepSeek V3.2"
                },
                {
                    "id": "ark-code-latest",
                    "name": "Ark Code Latest"
                }
            ]
        }
    }
}
```

**可用模型列表：**

| 模型 ID | 说明 | 推荐场景 |
|---------|------|---------|
| `ark-code-latest` | 方舟自动调度最优模型 | 编程任务 |
| `kimi-k2.5` | 理解力强，响应稳定 | 日常对话和任务执行（推荐） |
| `deepseek-v3.2` | 深度推理能力强 | 复杂分析任务 |
| `glm-4.7` | 智谱编程模型 | 代码生成 |
| `doubao-seed-2.0-code` | 豆包最新编程模型 | 编程任务 |

> **建议使用 `ark-code-latest` 或 `kimi-k2.5`。** `ark-code-latest` 由方舟自动调度，模型升级时无需改配置。`kimi-k2.5` 在对话理解和指令执行方面表现最均衡。

#### 配置 Embedding 模型（记忆搜索）

在 `agents.defaults` 中添加 `memorySearch` 配置：

```json
"agents": {
    "defaults": {
        "model": "volcengine/kimi-k2.5",
        "memorySearch": {
            "provider": "openai",
            "model": "doubao-embedding-vision",
            "remote": {
                "baseUrl": "https://ark.cn-beijing.volces.com/api/coding/v3",
                "apiKey": "你的API Key（与上面相同）"
            }
        }
    }
}
```

Embedding 模型为 OpenClaw 提供语义向量能力：

- 将对话、文档与任务信息转换为高维向量
- 基于语义相似度进行高效记忆检索
- 相比关键词匹配，在信息量大、对话长的场景下更准确

### Step 2：删除旧的 models.json

OpenClaw 有一个容易忽略的机制：`models.json` 的优先级高于 `openclaw.json`，且修改 `openclaw.json` 不会自动更新 `models.json`。所以改完配置后必须删除旧文件让它重新生成：

```bash
rm ~/.openclaw/agents/main/agent/models.json
```

> 删除后重启网关时，OpenClaw 会自动从 `openclaw.json` 重新生成 `models.json`。

### Step 3：重启网关

```bash
systemctl restart openclaw
```

### Step 4：验证

查看日志确认没有报错：

```bash
journalctl -u openclaw -f
```

**正常日志特征：**

- 看到 `[gateway] agent model: volcengine/kimi-k2.5`（或你配置的模型）
- **没有** `[memory] sync failed` 报错（说明 Embedding 配置正确）

在微信或企微中与 Agent 对话，确认模型正常响应。

---

## 四、切换模型

### 临时切换（在聊天中）

在微信或企微里给 Agent 发送：

```
/model volcengine/ark-code-latest
```

可用的模型切换命令：

| 命令 | 切换到 |
|------|--------|
| `/model volcengine/kimi-k2.5` | Kimi K2.5 |
| `/model volcengine/deepseek-v3.2` | DeepSeek V3.2 |
| `/model volcengine/ark-code-latest` | Ark Code（自动调度） |

临时切换只影响当前会话，不改变默认配置。

### 永久切换（修改默认模型）

编辑配置文件中的 `agents.defaults.model`：

```bash
nano ~/.openclaw/openclaw.json
# 修改 "model": "volcengine/kimi-k2.5" 为你想要的默认模型
```

然后：

```bash
rm ~/.openclaw/agents/main/agent/models.json
systemctl restart openclaw
```

---

## 五、完整配置文件示例

以下是一个同时配置了火山引擎 Coding Plan + 海外 GPT-5.4 的完整 `models` 和 `agents` 配置片段：

```json
{
    "models": {
        "mode": "merge",
        "providers": {
            "volcengine": {
                "baseUrl": "https://ark.cn-beijing.volces.com/api/coding/v3",
                "apiKey": "你的火山引擎API Key",
                "api": "openai-completions",
                "models": [
                    { "id": "kimi-k2.5", "name": "Kimi K2.5" },
                    { "id": "deepseek-v3.2", "name": "DeepSeek V3.2" },
                    { "id": "ark-code-latest", "name": "Ark Code Latest" }
                ]
            },
            "hotai": {
                "baseUrl": "https://www.hotaitool.net/v1",
                "apiKey": "你的海外代理API Key",
                "api": "openai-responses",
                "models": [
                    { "id": "gpt-5.4", "name": "GPT-5.4" }
                ]
            }
        }
    },
    "agents": {
        "defaults": {
            "compaction": { "mode": "safeguard" },
            "model": "hotai/gpt-5.4",
            "memorySearch": {
                "provider": "openai",
                "model": "doubao-embedding-vision",
                "remote": {
                    "baseUrl": "https://ark.cn-beijing.volces.com/api/coding/v3",
                    "apiKey": "你的火山引擎API Key"
                }
            }
        }
    }
}
```

**策略说明：**

- 默认模型使用 GPT-5.4（推理能力最强，用于复杂任务）
- 通过 `/model` 命令可随时切换到国产模型（省 Token、低延迟）
- Embedding 使用火山引擎的 doubao-embedding-vision（Coding Plan 包含）

---

## 六、常见问题排查

| 症状 | 原因 | 解决方案 |
|------|------|----------|
| 401 Unauthorized | API Key 错误或未订阅 Coding Plan | 确认 Key 正确且已完成订阅 |
| 404 model does not support coding plan | 模型名写错 | 使用上方表格中的正确模型 ID |
| 修改配置后不生效 | models.json 未更新 | 删除 `~/.openclaw/agents/main/agent/models.json` 后重启 |
| `[memory] sync failed` 401 | Embedding 配置缺失或 Key 错误 | 检查 `memorySearch` 配置是否完整 |
| 响应很慢（>60秒） | ark-code-latest 自动调度偶发慢 | 切换为 `kimi-k2.5`，响应更稳定 |
| 走了按量计费而非 Coding Plan | Base URL 写成了 `/api/v3` | 必须使用 `/api/coding/v3` |
| API rate limit reached | 超出套餐额度 | 等待次日额度重置，或升级套餐 |

---

## 七、费用说明

- **Coding Plan 包月套餐：** 固定月费，超出当日/月度额度后请求会报错，不会产生额外费用
- **Embedding 模型：** 包含在 Coding Plan 中，不额外计费
- **Token 消耗预估：** OpenClaw Agent 模式下，一次有效对话约消耗普通聊天 5-10 倍的 Token（含工具调用、上下文注入、Skills 执行等）
- Lite 套餐适合每天 20-30 次对话，Pro 套餐适合 50+ 次对话
