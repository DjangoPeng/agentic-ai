# Runbook（P0）

## 1. 前置准备
- Python 3.10+（建议使用固定虚拟环境）
- 建议统一使用项目虚拟环境：`~/projects/financial-automation/.venv`
- 准备输入目录（放发票 PDF/图片）
- 飞书相关（仅同步或 webhook 需要）：
  - `FEISHU_APP_ID`
  - `FEISHU_APP_SECRET`
  - `FEISHU_BITABLE_APP_TOKEN`
  - `FEISHU_BITABLE_EXPENSE_TABLE`
  - `FEISHU_BITABLE_REVIEW_TABLE`

## 2. 配置文件
- `config/app_config.yaml`：运行配置
  - 输入/输出路径
  - OCR 开关与参数
  - webhook 与 bitable 同步参数
- `config/rules.yaml`：规则配置
  - 必填字段
  - 置信度阈值
  - 复核策略

## 3. 本地批处理（主流程）
### 3.1 首次准备虚拟环境
```bash
cd ~/projects/financial-automation
python3 -m venv .venv
./.venv/bin/pip install -i https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org rapidocr_onnxruntime pypdf PyMuPDF
```

如果 OCR 模块报 `libGL.so.1` 缺失，需要额外安装系统库：

```bash
apt-get update && apt-get install -y libgl1
```

### 3.2 执行处理
1) 将运行凭据放到项目根目录的 `.env`（例如 `~/projects/financial-automation/.env`），统一由项目入口按需加载。  
2) 放置样例发票到输入目录  
3) 优先使用统一入口执行：

```bash
~/projects/financial-automation/bin/run_skill_job /path/to/invoice.pdf
```

该入口会在当前执行进程内自动加载项目目录下的 `.env`，不会污染其他项目。 

4) 如需直接调用 Python，请优先使用：

```bash
~/projects/financial-automation/.venv/bin/python
```

4) 检查输出：
- `runtime/.../extracted_json/*.json`
- `runtime/.../review_queue.json`
- `runtime/.../compliance_report.json`
- `runtime/.../run_summary.json`

## 4. Bitable 同步
### 4.1 当前推荐架构（重要）
当前项目的**主链路**建议拆成两段：

1. `financial-automation` project 负责：
   - OCR / PDF 解析
   - 票据类型判断
   - 结构化字段提取
   - 输出 `bitable_write_plan`
2. 当前 OpenClaw 会话负责：
   - 使用**用户身份**调用飞书多维表格工具
   - 按 `bitable_write_plan.records` 写入交通报销表 / 费用报销表
   - 回读或确认真实写入结果后再回复用户

请明确：
- 识别票据只是前半段
- 生成 `bitable_write_plan` 只是中间产物，不是最终结果
- 只要当前会话具备飞书多维表格工具能力，就必须继续真实写表
- **除非明确失败，否则不要停在 plan；必须继续执行真实写表**
- 只有真实 create/update 成功，才算完成

原因：
- 应用身份（App ID / App Secret）当前可读表，但 real-run 写 record / 上传附件仍会被飞书拒绝
- 用户身份已经验证可成功写入记录
- 用户授权卡片、授权完成通知、重试逻辑都天然发生在当前会话内，更适合放在 OpenClaw 侧处理

### 4.2 Dry-run
- 先执行 dry-run，检查字段映射与样本数据
- 确认 `bitable_write_plan.records` 中的目标表与字段 payload 正确
- 确认主表字段名与映射一致

### 4.3 Real-run（推荐：用户身份）
- 通过 `bin/run_skill_job` 或 `src/skill_entry.py` 运行识别
- 从返回结果中读取：
  - `documents`
  - `review_queue`
  - `bitable_write_plan`
- 由当前 OpenClaw 会话使用用户身份工具执行真实录入：
  - 交通类 → `交通报销表`
  - 费用类 → `费用报销表`
- 对每条记录，先查目标表是否存在可复用空白行：
  - 若 `doc_id` 为空，则优先 update 空白行
  - 若无空白行，再 create 新记录
- 若附件链路暂时不可用，也必须先把非附件字段真实写入
- 若飞书要求用户授权，按卡片完成授权后重试
- 写入后必须回读或明确确认写入结果
- 如果没有真实写入成功，不能把 plan 当作完成结果

### 4.4 应用身份同步（仅保留为备用/实验链路）
- 在项目 `.env` 中提供以下变量：
  - `FEISHU_APP_ID`
  - `FEISHU_APP_SECRET`
  - `FEISHU_BITABLE_APP_TOKEN`
  - `FEISHU_BITABLE_TRANSPORT_TABLE`
  - `FEISHU_BITABLE_EXPENSE_TABLE`
- 该链路当前不建议作为默认 real-run 主方案
- 现状：
  - 可拿 `tenant_access_token`
  - 可访问 bitable app / 列表表
  - 但写 record 会报 `403 / 91403`
  - 附件上传会报 `403 / 1061004`

## 5. 飞书 webhook 模式
1) 启动 webhook 服务（后续以 `src/webhook.py` 为准）  
2) 在飞书开放平台配置事件订阅地址  
3) 上传文件触发处理  
4) 验证单消息独立目录：
- `runtime/feishu_jobs/<message_id>/<job_id>/`

## 6. 常见问题排查
- 文件锁导致写失败：更换运行输出目录，避免占用
- OCR 结果空：检查图片质量、OCR 依赖与模型路径
- `rapidocr_onnxruntime` 导入失败且提示 `libGL.so.1`：安装系统库 `libgl1`
- 系统 Python 与虚拟环境表现不一致：确认实际使用的是 `~/projects/financial-automation/.venv/bin/python`
- 同步失败：检查 token、表 ID、字段名一致性
- 重复入库：检查幂等键生成与 upsert 逻辑
- webhook 无响应：检查回调 URL 连通性和事件订阅类型

## 7. 验收清单（Checklist）
- [ ] 主流程可从输入文件生成结构化结果
- [ ] warning/error 可进入复核队列
- [ ] dry-run 输出符合预期
- [ ] `bitable_write_plan` 生成后不会被误判为完成态
- [ ] real-run 成功写入主表和复核表
- [ ] 当工具可用时，流程会继续执行真实 create/update，而不是停在 plan
- [ ] 附件不可用时，非附件字段仍可真实落表
- [ ] 写入后可回读或明确确认结果
- [ ] webhook 模式单消息不混单
- [ ] 运行日志与 summary 完整可追踪
