请使用 `/root/projects/agentic-ai/github-secret-auditor/skills/github-secret-auditor/SKILL.md` 执行一次全自动 GitHub 密钥泄露巡检。

目标仓库：

```text
https://github.com/DjangoPeng/agentic-ai.git
```

要求：

1. 全程自动化执行，不要让我手动复制 session、手动执行命令、手动拼接 prompt 或手动验收。
2. OpenClaw 自动读取 Skill、准备仓库、生成任务包、通过 ACP Sessions API 调度 Claude Code、验收修复、commit、push，并通过飞书汇报。
3. Claude Code 负责仓库内敏感信息巡检和代码修复；OpenClaw 不要手工替代 Claude Code 修复。
4. 不要把后台调度细节作为需要我操作的步骤输出。除非失败排查，不要展开 `sessions_spawn` / `sessions_send` 参数。
5. 安全巡检应先判断仓库里是否存在泄露，再按仓库实际结构做最小安全修复；不要把修复固定成 `.env.example` / README / `.gitignore` 三件套。
6. 最终只回复巡检结果、是否修复、是否推送、commit、风险摘要、风险备注和下一步建议。

最终回复格式：

```text
状态：
passed / failed

目标仓库：
DjangoPeng/agentic-ai

是否调用 Claude Code：
yes / no

调用方式：
acp / failed

是否已推送到 GitHub：
yes / no

commit：
<commit hash>

修改文件：
- ...

风险摘要：
- ...

已完成修复：
- ...

残余风险：
- ...

风险备注：
- ...

下一步建议：
- ...
```
