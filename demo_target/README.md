# demo_target —— 第 19 节 github-secret-auditor 巡检靶标

本目录**故意植入合成假密钥**，作为 OpenClaw 经 ACP 调度 Claude Code 做密钥泄露巡检的演示目标。

- 所有"密钥"都是**非真实、非厂商格式的合成值**，不连任何真实服务，请勿在生产中模仿。
- 巡检预期：Claude Code 识别下列硬编码凭据 → 改为环境变量读取 → 补 `.env.example`，并输出 修改清单 / 风险摘要 / diff 摘要。
- 复位：`git reset --hard <SEED> && git push -f origin secret-audit-demo` 回到植入态，便于反复演练。
