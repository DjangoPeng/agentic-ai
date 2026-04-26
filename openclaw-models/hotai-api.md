# Hotai2API 海外模型代理接入指南

> 适用场景：通过国内网络访问 GPT-5.4、Claude 4.6 Ops 等海外旗舰模型

---

## 一、这是什么？

Hotai2API 是一个海外大模型的国内代理服务，让你无需 VPN、无需海外信用卡，即可在国内网络环境下调用 OpenAI、Anthropic 等海外厂商的旗舰模型。

**核心价值：**

- 国内直连，无需翻墙，延迟低
- 兼容 OpenAI API 格式，OpenClaw 直接对接
- 按量计费，充值即用，无月费门槛
- 支持 GPT-5.4、Claude 4.6 Ops 等当前最强推理模型

**适用人群：**

- 需要旗舰模型处理复杂推理任务（量化投研、代码重构、深度分析）的用户
- 日常以国产模型为主，偶尔需要切换旗舰模型的"双引擎"用户
- 课程学习中需要体验不同模型差异的学员

---

## 二、注册与充值

### Step 1：注册账号

访问 Hotai2API 注册页面：

```
https://www.hotaitool.net/register?ref=TCOEHW7Q
```

使用邮箱注册，完成邮箱验证。

### Step 2：充值

登录后进入 Dashboard，点击「充值」或「Purchase Plans」。

Hotai 提供多档充值套餐，按需选择：

| 套餐 | 价格 | 说明 |
|------|------|------|
| 基础档 | ¥50 | 适合初次体验和轻度使用 |
| 标准档 | ¥99 | 适合日常使用 |
| 高级档 | ¥198 | 适合重度使用和团队共享 |

> **建议：** 初次使用先充基础档体验，确认服务稳定后再加量。

### Step 3：获取 API Key

在 Dashboard 中找到「API Keys」或「令牌管理」页面：

1. 点击「创建新 Key」
2. 复制生成的 API Key（格式类似 `sk-xxxxxxxxxxxxxxxx`）
3. **妥善保管，不要泄露**

---

## 三、配置 OpenClaw 使用 Hotai

配置文件路径：`~/.openclaw/openclaw.json`

```bash
nano ~/.openclaw/openclaw.json
```

### 3.1 添加 Hotai Provider

在 `models.providers` 中添加 `hotai` 配置块：

```json
"models": {
    "mode": "replace",
    "providers": {
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
}
```

**字段逐项说明：**

| 字段 | 值 | 说明 |
|------|---|------|
| `baseUrl` | `https://www.hotaitool.net/v1` | Hotai 的 API 端点，固定不变 |
| `apiKey` | `sk-xxxx` | 你在 Hotai Dashboard 中生成的 Key |
| `api` | `"openai-responses"` | API 协议格式。Hotai 兼容 OpenAI Responses API（注意：不是 `openai-completions`，Hotai 用的是 Responses 协议） |
| `models[].id` | `"gpt-5.4"` | 模型标识符，用于 `/model` 命令切换时引用 |
| `models[].name` | `"GPT-5.4"` | 显示名称，在 Dashboard 和日志中展示 |

> **关于 `api` 字段的区别：** 火山引擎用 `"openai-completions"`（Chat Completions 协议），Hotai 用 `"openai-responses"`（Responses 协议）。填错会导致 API 调用失败。

### 3.2 同时配置 Hotai + 火山引擎（推荐的双引擎配置）

大多数用户会同时配置国产模型（日常省钱）和海外旗舰（复杂任务切换）。以下是双引擎共存的完整 `models` 配置：

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
}
```

**两个 provider 的关键区别：**

| 字段 | volcengine（火山引擎） | hotai（海外代理） |
|------|---------------------|-----------------|
| `baseUrl` | `/api/coding/v3` | `/v1` |
| `api` | `openai-completions` | `openai-responses` |
| 计费 | Coding Plan 包月 | 按量计费 |
| 适合 | 日常任务 | 复杂推理任务 |

### 3.3 设置默认模型

在 `agents.defaults` 中指定默认使用哪个模型：

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

**推荐策略：**

- 默认模型设为国产模型（如 `volcengine/ark-code-latest`），日常省钱
- 需要旗舰推理时，在聊天中用 `/model hotai/gpt-5.4` 临时切换
- 用完切回：`/model volcengine/ark-code-latest`

如果你希望默认就使用 GPT-5.4（不在乎成本）：

```json
"model": "hotai/gpt-5.4"
```

### 3.4 应用配置

```bash
# 1. 删除旧的 models.json
rm ~/.openclaw/agents/main/agent/models.json

# 2. 重启网关
systemctl restart openclaw
```

### 3.5 验证

在微信或企微中发送：

```
/model hotai/gpt-5.4
```

然后发一条消息测试回复是否正常。或者直接问 Agent：

```
你现在用的是什么模型？
```

---

## 四、可用模型列表

Hotai 代理支持的主要模型（以平台实际提供为准）：

| 模型 | 说明 | 推荐场景 |
|------|------|---------|
| `gpt-5.4` | OpenAI 最新旗舰 | 复杂推理、长上下文分析 |
| `gpt-5.4-mini` | 轻量版 | 日常对话、快速响应 |
| `claude-sonnet-4-6` | Anthropic Sonnet | 代码生成、指令遵循 |
| `claude-opus-4-6` | Anthropic Opus | 极致推理、研究分析 |

> 具体可用模型以 Hotai 平台 Dashboard 中的模型列表为准，平台会随厂商更新同步。

---

## 五、在微信/企微中切换模型

配置完成后，你可以随时在聊天中切换模型：

```
/model hotai/gpt-5.4              → 切到 GPT-5.4（旗舰推理）
/model volcengine/kimi-k2.5       → 切回 Kimi（日常省钱）
/model volcengine/deepseek-v3.2   → 切到 DeepSeek（深度推理）
/model volcengine/ark-code-latest  → 切到方舟自动调度（默认）
```

临时切换只影响当前会话，不改变默认配置。

---

## 六、成本控制建议

Hotai 按 Token 计费，OpenClaw 的 Agent 模式消耗较大（每次对话约普通聊天的 5-10 倍）。建议采用以下策略：

**日常任务 → 国产模型（火山引擎 Coding Plan 包月）**

- 回复消息、资讯摘要、简单问答、定时任务
- 固定月费，不怕超支

**复杂任务 → 海外旗舰模型（Hotai 按量）**

- 量化投研分析、大型代码重构、深度推理
- 用 `/model` 命令临时切换，用完切回

**监控用量：**

- 在 Hotai Dashboard 中查看余额和消耗明细
- 在 OpenClaw 中可配置 `maxTokensPerDay` 设置日预算上限（第 11 节详讲）

---

## 七、常见问题排查

| 症状 | 原因 | 解决方案 |
|------|------|----------|
| 401 Unauthorized | API Key 错误或已失效 | 重新从 Dashboard 复制 Key |
| 403 Forbidden | 余额不足 | 登录 Dashboard 充值 |
| 回复很慢（>60秒） | 海外模型推理本身较慢 | GPT-5.4 复杂任务正常需要 10-30 秒 |
| 连接超时 | 网络波动 | 稍后重试，或检查服务器网络 |
| `/model` 切换后无效 | models.json 缓存 | 删除 `~/.openclaw/agents/main/agent/models.json` 后重启 |
| 模型不存在 | 模型名称写错 | 检查 Dashboard 中的实际模型 ID |
| API 调用失败 | `api` 字段写错 | Hotai 用 `openai-responses`，不是 `openai-completions` |

---

## 八、安全提醒

- API Key 是你的付费凭证，泄露后他人可消耗你的余额
- 不要将 API Key 硬编码在公开的代码仓库中
- 如果配置文件在 Git 仓库中，确保 `openclaw.json` 已加入 `.gitignore`
- 如怀疑 Key 泄露，立即在 Dashboard 中删除旧 Key 并重新生成
