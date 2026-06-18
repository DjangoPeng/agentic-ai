# Financial Expense Automation

> 配套课程：AI 业务流架构师 · 第 13 节《全自动财务填报与跨系统数据搬运机器人》

上传图片或 PDF 票据，识别报销信息，并把结构化结果连同**真实附件**写入飞书多维表格（Bitable）。

```
票据图片/PDF → OCR/原生文本抽取 → 结构化 → 校验 → 附件上传(Bitable context) → create/update → 回读确认
```

## 与课程的关系

本项目是第 13 节的实战代码，服务于课程的两个核心留存物：

| 留存物 | 在本项目中的体现 |
|---|---|
| **五步拆解心法** | 业务理解（真终点=飞书表有记录）→ 能力拆分（识别/校验/写表/兜底）→ 接口设计（SKILL.md/run_skill_job/rules.yaml）→ 实现选型（本地 OCR + 规则提取）→ 质量兵推（渐进式失败 + 复核队列） |
| **完成态公式** | 真实写入（Bitable create/update）+ 闭环回读 + 失败分项汇报（附件失败单独说） |

## 快速开始

```bash
# 1. 进入项目
cd financial-automation

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 本地识别（不需要飞书配置）
python scripts/run_skill_job.py runtime/sample_run_input/hotel_invoice.pdf
```

跑通识别即可掌握本节 80% 的内容。真实写表需要飞书 OAuth 配置，详见 [lesson13-lab.md](lesson13-lab.md)。

## 核心模块

| 模块 | 职责 |
|---|---|
| `src/skill_entry.py` | Skill 主入口，`run_skill_job()` 串起全链路 |
| `src/ocr_extract.py` | 图片走 OCR，PDF 优先原生抽取再回退 OCR |
| `src/validate.py` | 必填字段 / 置信度 / 合规检查 / 复核队列 |
| `src/sync_bitable.py` | 费用表 / 交通表路由 + 字段映射 |
| `src/bitable_attachment_uploader.py` | 上传到 Bitable attachment context |
| `config/rules.yaml` | 业务人员可读的校验规则 |
| `skills/.../SKILL.md` | OpenClaw Skill 定义（Agent 契约） |

## 完成标准

一次完整成功必须同时满足：

1. 文档识别成功
2. `attachment_upload_result.ok = true`
3. `票据附件` 字段拿到真实 `file_token`
4. 真实 create/update 成功
5. 回读到 Bitable 记录，且附件字段可见

`bitable_write_plan` 只是中间产物，**不是完成态**。

## 飞书配置

详见 [lesson13-lab.md](lesson13-lab.md) 的分步操作指南。

环境变量模板：

```bash
cp .env.example .env.local
# 填入真实值后：
set -a && source .env.local && set +a
```

## 相关课程章节

| 前置 | 内容 |
|---|---|
| 第 4 节 | 飞书原生深度集成（Bitable 基础操作） |
| 第 9 节 | SDL 语法与 Skill 开发（SKILL.md 编写） |
| 第 12 节 | 浏览器自动化（本节转为 API 路线的对比背景） |

| 后续 | 复用 |
|---|---|
| 第 14 节 | 五步框架 + 完成态公式 → 早报管家 |
| 第 15 节 | 五步框架 + 完成态公式 → CRM 跟进 |
| 第 18 节 | 五步框架 + 完成态公式 → 量化投研 |
