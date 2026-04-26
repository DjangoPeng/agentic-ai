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
2. 生成后复制密钥（格式类似 `f218f0fd-169e-4c88-8e67-1bcd23e86697`）
3. **妥善保管，不要泄露**

> 如果你之前已经有火山引擎的 API Key，购买 Coding Plan 后原有的 Key 可以直接使用，不需要重新创建。

---

## 三、关键概念：Coding Plan vs 在线推理

火山引擎方舟平台有两种完全不同的模型调用方式，**务必区分清楚**：

| 项目 | Coding Plan（包月） | 在线推理（按量计费） |
|------|-------------------|-------------------|
| Base URL | `https://ark.cn-beijing.volces.com/api/coding/v3` | `https://ark.cn-beijing.volces.com/api/v3` |
| 模型调用方式 | 直接用模型名（如 `kimi-k2.5`） | 需要先创建「接入点」，用接入点 ID 调用（如 `ep-2026xxxx-xxxxx`） |
| 是否需要接入点 | **不需要**，平台统一调度 | **需要**，每个模型手动创建 |
| 计费方式 | 固定月费，超额自动停止 | 按 Token 计费，无上限 |
| 适合场景 | 日常使用，成本可控 | 需要 Coding Plan 套餐外的特定模型 |

> ⚠️ **最常见的错误：** 把 Base URL 写成 `/api/v3`（在线推理地址），导致不走 Coding Plan 额度而产生额外费用。正确地址是 `/api/coding/v3`。

**简单来说：用 Coding Plan 就不需要创建接入点，直接填模型名即可。** 接入点是在线推理模式的概念，两者不要混淆。

---

## 四、配置 OpenClaw 使用 Coding Plan

配置文件路径：`~/.openclaw/openclaw.json`

```bash
nano ~/.openclaw/openclaw.json
```

### 4.1 配置大模型 Provider

在 `models.providers` 中添加 `volcengine` 配置块。以下是完整配置及每个字段的详细说明：

```json
"models": {
    "mode": "replace",
    "providers": {
        "volcengine": {
            "baseUrl": "https://ark.cn-beijing.volces.com/api/coding/v3",
            "apiKey": "<YOUR_VOLCENGINE_API_KEY>",
            "api": "openai-completions",
            "models": [
                {
                    "id": "ark-code-latest",
                    "name": "ark-code-latest",
                    "contextWindow": 256000,
                    "maxTokens": 32000,
                    "input": ["text", "image"]
                },
                {
                    "id": "kimi-k2.5",
                    "name": "kimi-k2.5",
                    "contextWindow": 256000,
                    "maxTokens": 32000,
                    "input": ["text", "image"]
                },
                {
                    "id": "deepseek-v3.2",
                    "name": "deepseek-v3.2",
                    "contextWindow": 128000,
                    "maxTokens": 32000,
                    "input": ["text"]
                },
                {
                    "id": "glm-4.7",
                    "name": "glm-4.7",
                    "contextWindow": 200000,
                    "maxTokens": 128000,
                    "input": ["text"]
                },
                {
                    "id": "doubao-seed-2.0-code",
                    "name": "doubao-seed-2.0-code",
                    "contextWindow": 256000,
                    "maxTokens": 128000,
                    "input": ["text", "image"]
                },
                {
                    "id": "doubao-seed-2.0-pro",
                    "name": "doubao-seed-2.0-pro",
                    "contextWindow": 256000,
                    "maxTokens": 128000,
                    "input": ["text", "image"]
                },
                {
                    "id": "doubao-seed-2.0-lite",
                    "name": "doubao-seed-2.0-lite",
                    "contextWindow": 256000,
                    "maxTokens": 128000,
                    "input": ["text", "image"]
                },
                {
                    "id": "minimax-m2.5",
                    "name": "minimax-m2.5",
                    "contextWindow": 200000,
                    "maxTokens": 128000,
                    "input": ["text"]
                },
                {
                    "id": "doubao-seed-code",
                    "name": "doubao-seed-code",
                    "contextWindow": 256000,
                    "maxTokens": 32000,
                    "input": ["text", "image"]
                }
            ]
        }
    }
}
```

**字段逐项说明：**

| 字段 | 值 | 说明 |
|------|---|------|
| `mode` | `"replace"` | 模型列表模式。`replace` 表示完全替换默认模型列表（推荐）；`merge` 表示与默认列表合并 |
| `baseUrl` | `https://ark.cn-beijing.volces.com/api/coding/v3` | **Coding Plan 专用地址**。⚠️ 写成 `/api/v3` 会走按量计费！ |
| `apiKey` | 你的火山引擎 API Key | 在方舟控制台的 API Key 管理页面获取 |
| `api` | `"openai-completions"` | API 协议格式，火山引擎兼容 OpenAI Chat Completions 协议 |
| `models[].id` | 如 `"kimi-k2.5"` | 模型标识符，Coding Plan 下直接用模型名，不需要接入点 ID |
| `models[].name` | 如 `"kimi-k2.5"` | 显示名称，在 Dashboard 和 `/model` 命令中展示 |
| `models[].contextWindow` | 如 `256000` | 模型的最大上下文窗口（Token 数），OpenClaw 用此值管理上下文压缩 |
| `models[].maxTokens` | 如 `32000` | 单次回复的最大 Token 数 |
| `models[].input` | `["text"]` 或 `["text", "image"]` | 模型支持的输入类型。包含 `image` 的模型可以处理图片 |

**Coding Plan 可用模型速查：**

| 模型 ID | 上下文窗口 | 最大输出 | 支持图片 | 推荐场景 |
|---------|----------|---------|---------|---------|
| `ark-code-latest` | 256K | 32K | ✅ | 方舟自动调度最优模型（推荐默认） |
| `kimi-k2.5` | 256K | 32K | ✅ | 日常对话、指令执行，响应最稳定 |
| `deepseek-v3.2` | 128K | 32K | ❌ | 深度推理、逻辑分析 |
| `glm-4.7` | 200K | 128K | ❌ | 代码生成、长文本输出 |
| `doubao-seed-2.0-code` | 256K | 128K | ✅ | 编程任务，豆包最新编程模型 |
| `doubao-seed-2.0-pro` | 256K | 128K | ✅ | 综合能力，豆包旗舰 |
| `doubao-seed-2.0-lite` | 256K | 128K | ✅ | 轻量任务，速度快 |
| `minimax-m2.5` | 200K | 128K | ❌ | 综合能力均衡 |
| `doubao-seed-code` | 256K | 32K | ✅ | 编程任务，上一代豆包编程模型 |

> 你不需要把所有模型都配上。建议至少配 `ark-code-latest`（自动调度）+ `kimi-k2.5`（日常稳定）+ `deepseek-v3.2`（深度推理），其余按需添加。

### 4.2 配置默认模型

在 `agents.defaults` 中指定 OpenClaw 启动时默认使用的模型：

```json
"agents": {
    "defaults": {
        "compaction": {
            "mode": "safeguard"
        },
        "model": "volcengine/ark-code-latest"
    }
}
```

**字段说明：**

| 字段 | 值 | 说明 |
|------|---|------|
| `compaction.mode` | `"safeguard"` | 上下文压缩策略。`safeguard` 是安全模式，在上下文接近窗口上限时自动压缩，避免丢失关键信息 |
| `model` | `"volcengine/ark-code-latest"` | 默认模型，格式为 `provider名/模型id`。这里用的是 volcengine provider 下的 ark-code-latest 模型 |

### 4.3 配置 Embedding 模型（记忆搜索）

在 `agents.defaults` 中添加 `memorySearch` 配置，让 Agent 的记忆检索从关键词匹配升级为语义搜索：

```json
"agents": {
    "defaults": {
        "compaction": {
            "mode": "safeguard"
        },
        "model": "volcengine/ark-code-latest",
        "memorySearch": {
            "provider": "openai",
            "model": "doubao-embedding-vision",
            "remote": {
                "baseUrl": "https://ark.cn-beijing.volces.com/api/coding/v3",
                "apiKey": "<YOUR_VOLCENGINE_API_KEY>"
            }
        }
    }
}
```

**字段说明：**

| 字段 | 值 | 说明 |
|------|---|------|
| `memorySearch.provider` | `"openai"` | Embedding 接口协议，火山引擎兼容 OpenAI Embeddings 格式，所以填 `openai` |
| `memorySearch.model` | `"doubao-embedding-vision"` | Embedding 模型名称，这是 Coding Plan 包含的向量模型 |
| `memorySearch.remote.baseUrl` | Coding Plan 地址 | 与大模型用同一个 Base URL（`/api/coding/v3`） |
| `memorySearch.remote.apiKey` | 你的火山引擎 API Key | 与大模型用同一个 Key |

**为什么需要 Embedding？**

- 没有 Embedding：Agent 的记忆检索只能靠关键词精确匹配，问"上周聊的那个项目"可能搜不到
- 有了 Embedding：Agent 把所有记忆转为语义向量，支持模糊搜索和语义关联，大幅提升记忆召回质量
- 如果不配 Embedding，日志里会持续报 `[memory] sync failed` 错误

### 4.4 应用配置

修改完 `openclaw.json` 后，必须执行以下两步才能生效：

```bash
# 1. 删除旧的 models.json（重要！）
#    OpenClaw 2026.2.26+ 版本中，models.json 优先级高于 openclaw.json
#    不删除的话，修改不会生效
rm ~/.openclaw/agents/main/agent/models.json

# 2. 重启网关
systemctl restart openclaw
```

> ⚠️ **这是最容易踩的坑：** 很多人改了 `openclaw.json` 发现不生效，排查半天才发现是 `models.json` 在"作祟"。每次改完配置都要先删 `models.json` 再重启。

### 4.5 验证

查看日志确认没有报错：

```bash
journalctl -u openclaw -f
```

**正常日志特征：**

- 看到 `[gateway] agent model: volcengine/ark-code-latest`（或你配置的默认模型）
- **没有** `[memory] sync failed` 报错（说明 Embedding 配置正确）

在微信或企微中与 Agent 对话，确认模型正常响应。

---

## 五、切换模型

### 临时切换（在聊天中）

在微信或企微里给 Agent 发送 `/model` 命令：

```
/model volcengine/kimi-k2.5
```

可用的模型切换命令（取决于你在 models 中配置了哪些模型）：

| 命令 | 切换到 | 推荐场景 |
|------|--------|---------|
| `/model volcengine/ark-code-latest` | 方舟自动调度 | 编程任务（默认） |
| `/model volcengine/kimi-k2.5` | Kimi K2.5 | 日常对话、指令执行 |
| `/model volcengine/deepseek-v3.2` | DeepSeek V3.2 | 深度推理、逻辑分析 |
| `/model volcengine/glm-4.7` | GLM 4.7 | 代码生成 |
| `/model volcengine/doubao-seed-2.0-pro` | 豆包 Seed Pro | 综合任务 |

临时切换只影响当前会话，不改变默认配置。

### 永久切换（修改默认模型）

编辑 `openclaw.json` 中的 `agents.defaults.model` 字段：

```bash
nano ~/.openclaw/openclaw.json
# 将 "model": "volcengine/ark-code-latest" 改为你想要的默认模型
# 例如 "model": "volcengine/kimi-k2.5"
```

然后：

```bash
rm ~/.openclaw/agents/main/agent/models.json
systemctl restart openclaw
```

---

## 六、完整配置文件示例

以下是一个同时配置了火山引擎 Coding Plan + Hotai 海外代理的完整 `models` 和 `agents` 配置。你也可以参考仓库中的 [openclaw.json.example](../openclaw.json.example) 查看包含所有配置块（gateway、models、agents、plugins、channels、tools）的完整模板。

```json
{
    "models": {
        "mode": "replace",
        "providers": {
            "volcengine": {
                "baseUrl": "https://ark.cn-beijing.volces.com/api/coding/v3",
                "apiKey": "<YOUR_VOLCENGINE_API_KEY>",
                "api": "openai-completions",
                "models": [
                    {
                        "id": "ark-code-latest",
                        "name": "ark-code-latest",
                        "contextWindow": 256000,
                        "maxTokens": 32000,
                        "input": ["text", "image"]
                    },
                    {
                        "id": "kimi-k2.5",
                        "name": "kimi-k2.5",
                        "contextWindow": 256000,
                        "maxTokens": 32000,
                        "input": ["text", "image"]
                    },
                    {
                        "id": "deepseek-v3.2",
                        "name": "deepseek-v3.2",
                        "contextWindow": 128000,
                        "maxTokens": 32000,
                        "input": ["text"]
                    }
                ]
            },
            "hotai": {
                "baseUrl": "https://www.hotaitool.net/v1",
                "apiKey": "<YOUR_HOTAI_API_KEY>",
                "api": "openai-responses",
                "models": [
                    {
                        "id": "gpt-5.4",
                        "name": "GPT-5.4"
                    }
                ]
            }
        }
    },
    "agents": {
        "defaults": {
            "compaction": { "mode": "safeguard" },
            "model": "volcengine/ark-code-latest",
            "memorySearch": {
                "provider": "openai",
                "model": "doubao-embedding-vision",
                "remote": {
                    "baseUrl": "https://ark.cn-beijing.volces.com/api/coding/v3",
                    "apiKey": "<YOUR_VOLCENGINE_API_KEY>"
                }
            }
        }
    }
}
```

**策略说明：**

- 默认模型使用 `ark-code-latest`（方舟自动调度最优模型，模型升级时无需改配置）
- 日常对话可切换到 `kimi-k2.5`（响应最稳定）
- 需要海外旗舰推理能力时，通过 `/model hotai/gpt-5.4` 临时切换
- Embedding 使用 Coding Plan 包含的 `doubao-embedding-vision`，不额外计费

---

## 七、补充：在线推理接入点（按量计费）

如果你需要使用 Coding Plan 套餐外的模型（如特定版本的豆包模型），或者在未订阅 Coding Plan 的情况下使用火山引擎，需要通过「在线推理」方式接入。这种方式需要手动创建接入点。

> 大多数场景下 Coding Plan 已经够用，本节内容仅作补充。

### 创建接入点

1. 访问火山引擎控制台：`https://console.volcengine.com/ark/region:ark+cn-beijing/endpoint`
2. 点击「创建接入点」
3. 选择你需要的模型（如 `doubao-seed-2-0-pro-260215`）
4. 创建完成后，复制接入点 ID（格式如 `ep-20260413045435-2shmq`）

### 在 OpenClaw 中配置

在 `models.providers` 中新增一个独立的 provider（不要和 Coding Plan 的 `volcengine` 混在一起）：

```json
"volcengine-online": {
    "baseUrl": "https://ark.cn-beijing.volces.com/api/v3",
    "apiKey": "<YOUR_VOLCENGINE_API_KEY>",
    "api": "openai-completions",
    "models": [
        {
            "id": "ep-20260413045435-2shmq",
            "name": "Doubao Seed Pro (在线推理)"
        }
    ]
}
```

**与 Coding Plan 配置的关键区别：**

| 字段 | Coding Plan | 在线推理 |
|------|------------|---------|
| provider 名 | `volcengine` | `volcengine-online`（建议用不同名称区分） |
| `baseUrl` | `/api/coding/v3` | `/api/v3` |
| `models[].id` | 模型名（如 `kimi-k2.5`） | 接入点 ID（如 `ep-2026xxxx-xxxxx`） |
| 计费 | 包月 | 按 Token 按量 |

> ⚠️ 在线推理按 Token 计费，无月费上限，务必关注用量。

---

## 八、常见问题排查

| 症状 | 原因 | 解决方案 |
|------|------|----------|
| 401 Unauthorized | API Key 错误或未订阅 Coding Plan | 确认 Key 正确且已完成订阅 |
| 404 model does not support coding plan | 模型名写错 | 使用第四节表格中的正确模型 ID |
| 修改配置后不生效 | models.json 未更新 | 删除 `~/.openclaw/agents/main/agent/models.json` 后重启 |
| `[memory] sync failed` 401 | Embedding 配置缺失或 Key 错误 | 检查 `memorySearch` 配置是否完整（参见 4.3 节） |
| 响应很慢（>60秒） | ark-code-latest 自动调度偶发慢 | 切换为 `kimi-k2.5`，响应更稳定 |
| 走了按量计费而非 Coding Plan | Base URL 写成了 `/api/v3` | 必须使用 `/api/coding/v3` |
| API rate limit reached | 超出套餐额度 | 等待次日额度重置，或升级套餐 |

---

## 九、费用说明

- **Coding Plan 包月套餐：** 固定月费，超出当日/月度额度后请求会报错，不会产生额外费用
- **Embedding 模型：** 包含在 Coding Plan 中，不额外计费
- **Token 消耗预估：** OpenClaw Agent 模式下，一次有效对话约消耗普通聊天 5-10 倍的 Token（含工具调用、上下文注入、Skills 执行等）
- Lite 套餐适合每天 20-30 次对话，Pro 套餐适合 50+ 次对话
