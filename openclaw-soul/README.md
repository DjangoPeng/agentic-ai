# 🧠 openclaw-soul — 人格工程

> SOUL.md 四层建造法 + AGENTS.md 权限矩阵设计

## 这是什么

OpenClaw Agent 的行为由 workspace 下的 `.md` 文件控制。其中最核心的两个文件：

- **SOUL.md**：定义 Agent 的人格、风格、价值观和安全边界——回答"你是谁"
- **AGENTS.md**：定义 Agent 的操作规程、权限矩阵和记忆管理——回答"你怎么做事"

本目录提供可直接使用的模板和多个行业案例。

## SOUL.md 四层建造法

从空文件开始，逐层叠加，每层可独立验证：

| 层级 | 作用 | 示例 |
|------|------|------|
| Layer 1: Identity | 身份锚点——你是谁、服务谁、专精什么 | "你是 David，彭总的研发助手" |
| Layer 2: Communication Style | 沟通风格——语言、长度、格式控制 | "禁止使用 emoji 和客套语" |
| Layer 3: Values & Rules | 行为规则——硬规则 + 软偏好 | "删除操作必须获得明确确认" |
| Layer 4: Boundaries | 安全边界——绝对红线 | "绝不修改自己的 SOUL.md" |

## AGENTS.md 三级权限矩阵

| 级别 | 含义 | 示例 |
|------|------|------|
| Act & Report | 直接执行，事后汇报 | 创建文档、查询记录 |
| Propose First | 先复述方案，确认后执行 | 删除记录、新建表、生成待办 |
| Critical | 必须主人亲自确认 | 重启服务、修改核心配置 |

## 文件说明

```
openclaw-soul/
├── README.md                          # 本文件
├── lesson05-lab.md                    # 第5节实验手册（可直接跟着操作）
├── templates/
│   ├── SOUL.md.example                # 通用模板（带注释）
│   └── AGENTS.md.example              # 通用模板（带注释）
├── examples/
│   ├── dev-assistant/                 # 研发助手场景
│   │   ├── SOUL.md
│   │   └── AGENTS.md
│   ├── biz-assistant/                 # 业务管家场景
│   │   ├── SOUL.md
│   │   └── AGENTS.md
│   └── devops-agent/                  # DevOps 运维场景
│       └── SOUL.md
```

## 快速使用

```bash
# 复制模板到你的 workspace
cp templates/SOUL.md.example ~/.openclaw/workspace/SOUL.md
cp templates/AGENTS.md.example ~/.openclaw/workspace/AGENTS.md

# 编辑并定制（或直接在 IM 中让 Agent 自己修改）
# 然后在 IM 中发送 /reset 重新加载
```

或者直接在微信/飞书中告诉 Agent：
```
请把你的 SOUL.md 文件替换为以下内容……
```

## 配套课程

本目录对应课程第5节《Markdown 调教法：铸造 Agent 的价值观与不可变内核》。
