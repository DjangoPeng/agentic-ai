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

## 三、在 OpenClaw 中配置 Hotai

### Step 1：编辑配置文件

```bash
nano ~/.openclaw/openclaw.json
```

在 `models.providers` 中添加 `hotai` 配置：

```json
"hotai": {
    "baseUrl": "https://www.hotaitool.net/v1",
    "apiKey": "你的 Hotai API Key",
    "api": "openai-responses",
    "models": [
        {
            "id": "gpt-5.4",
            "name": "GPT-5.4"
        }
    ]
}
```

**配置说明：**

| 字段 | 值 | 说明 |
|------|---|------|
| baseUrl | `https://www.hotaitool.net/v1` | Hotai 的 API 端点，固定不变 |
| apiKey | `sk-xxxx` | 你在 Dashboard 中生成的 Key |
| api | `openai-responses` | API 协议格式，Hotai 兼容 OpenAI Responses API |
| models.id | `gpt-5.4` | 模型标识，用于 `/model` 命令切换 |

### Step 2：设置默认模型（可选）

如果你希望 Hotai 的 GPT-5.4 作为默认模型：

```json
"agents": {
    "defaults": {
        "model": "hotai/gpt-5.4"
    }
}
```

如果你希望国产模型作为默认、GPT-5.4 作为备选（推荐）：

```json
"agents": {
    "defaults": {
        "model": "volcengine/kimi-k2.5"
    }
}
```

然后通过 `/model hotai/gpt-5.4` 命令临时切换。

### Step 3：删除旧缓存并重启

```bash
rm ~/.openclaw/agents/main/agent/models.json
systemctl restart openclaw
```

### Step 4：验证

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
/model hotai/gpt-5.4          → 切到 GPT-5.4（旗舰推理）
/model volcengine/kimi-k2.5   → 切回 Kimi（日常省钱）
/model volcengine/deepseek-v3.2 → 切到 DeepSeek（深度推理）
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
| 回复很慢（>60秒） | 海外模型本身推理较慢 | GPT-5.4 复杂任务正常需要 10-30 秒 |
| 连接超时 | 网络波动 | 稍后重试，或检查服务器网络 |
| `/model` 切换后无效 | models.json 缓存 | 删除 models.json 并重启网关 |
| 模型不存在 | 模型名称写错 | 检查 Dashboard 中的实际模型 ID |

---

## 八、安全提醒

- API Key 是你的付费凭证，泄露后他人可消耗你的余额
- 不要将 API Key 硬编码在公开的代码仓库中
- 如果配置文件在 Git 仓库中，确保 `openclaw.json` 已加入 `.gitignore`
- 如怀疑 Key 泄露，立即在 Dashboard 中删除旧 Key 并重新生成
