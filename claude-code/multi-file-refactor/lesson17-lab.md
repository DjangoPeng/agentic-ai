# 第 17 节 实验手册：多文件协同与终端代码级重构实战

> 配套课程：AI 业务流架构师 · 第 17 节《多文件协同与终端代码级重构实战》
> 预计耗时：60–90 分钟
> 操作方式：全程在终端和 Claude Code 对话完成——**你给目标，它动手**；你看 diff、确认、跑测试，不用自己背命令
> 前置条件：Claude Code 已装好并接火山（第 16 节内容）；本机有 Python 3.10+ 和 git；本仓库已克隆到本地

---

## 0. 开始前确认

| # | 物料 | 备注 |
|---|---|---|
| 1 | Claude Code 能正常对话 | `claude` 进入后 `/status` 显示 `ark.cn-beijing.volces.com` |
| 2 | 本仓库已克隆到本地 | 例：`~/projects/agentic-ai` |
| 3 | Python 3.10+ 与 git | `python3 --version` / `git --version` 能正常输出 |

> 本节的重构改动都发生在 `claude-code/multi-file-refactor/` 的**快照**里，**原始的 `financial-automation/`、`CRM-Assistant/` 目录不动**——这是真实工程里对待遗留代码的姿势：在隔离副本上动手，原件永远安全。

---

## 1. 先让 Claude Code 读懂这几个 app（干净仓库，只读）

**这一步在搭工作区之前做**——此时仓库是干净的，Claude Code 读的是真实的 4 个 app。在仓库根打开它：

```bash
cd ~/projects/agentic-ai   # 换成你的实际路径
claude
```

**第一问**——逐个摸清结构：

```
这个项目里有好几个独立的应用（financial-automation、CRM-Assistant、
morning-newspaper、xhs-auto-publisher）。先别改任何文件——逐个看一下：
每个 app 是干嘛的、用什么技术栈、各自怎么对接飞书？
```

**第二问**——找出重复：

```
这几个 app 有没有重复造轮子？特别是飞书对接——是不是有人各写了一遍认证？
把具体文件和函数名指出来。
```

它会指出 `financial-automation` 和 `CRM-Assistant` **各写了一遍**飞书认证（`get_tenant_access_token` vs `get_feishu_tenant_access_token`）——这就是下一步要消除的重复。

> 💡 学习点：它不是把几十个文件一次读完，而是用 Glob/Grep **按需检索**、顺着线索翻具体文件。这就是它能驾驭「超出一次脑容量」的大项目的原因。
> ⚠️ **顺序很重要**：先在干净仓库读懂、**再** setup。反过来的话，setup 把两个 app 快照进 `multi-file-refactor/` 后，CC 再扫仓库会看到 financial / CRM **各两份**，干扰它对「项目群」的判断。

`/exit` 退出。

---

## 2. 搭好实验工作区（让 Claude Code 跑 setup.sh）

读懂了，现在把**要改的那两个 app** 隔离进工作区再动手。仍在仓库根，发送目标：

```
运行 claude-code/multi-file-refactor/setup.sh 把本节实验工作区建好
（快照 financial-automation + CRM-Assistant、建好各自的 venv、跑通基线测试），
完成后告诉我两个 app 的基线测试是否都通过。
```

完成后你应看到两个 app 的「重构前」测试都是绿的——这是后面验证重构没改坏的基准。

> 💡 学习点：搭环境这种重复样板活，也是写成脚本、一句话交给 CC——**给目标、不给步骤**。原件不动、两个独立 venv 项目并进一处，才谈得上抽一个共享层。
> 如果 `claude-code/multi-file-refactor/` 里已带快照、想从零练，先 `rm -rf` 掉 `{financial-automation,CRM-Assistant,common}` 再跑脚本；或在你自己的 fork 上做。

---

## 3. 安全重构：抽出一个共享 FeishuClient

切到工作区再开 Claude Code（之后所有改动都在这里）：

```bash
cd ~/projects/agentic-ai/claude-code/multi-file-refactor
claude
```

**① 先要方案，别急着改**（你是 reviewer）：

```
这里的 financial-automation 和 CRM-Assistant 各写了一遍飞书对接
（认证 / 端点 / Bitable / 容错）。我想抽一个共享 FeishuClient（放到 common/ 下），
两个 app 都用它。先别改，给我一个重构方案：客户端放哪、提供哪些方法、
各 app 哪些调用点要改、风险在哪。
```

读一遍方案，觉得合理再放行。

**② 动手改**（每处看 diff）：

```
方案可以。开始改：先建共享 FeishuClient，再逐个替换 financial 的调用点，
每改一处给我看 diff；financial 改完再改 CRM，最后删掉两边旧的 token 函数。
```

> 📦 你会拿到什么：CC 通常把共享层落成一个 `common/feishu/` **包**（按职责分层：`errors` 统一异常树 / `auth` / `http` / `bitable` / `client` / `__init__`），而不是单个文件——这才是更专业的分层。本课程实测去重约 **450 行**。

**③ 跑测试验证**：

```
改完了，把两个 app 的测试都跑一遍，看重构有没有破坏原有行为。
```

测试**很可能一遍就过**（本课程实测就是干净通过）。万一报红——两边签名 / 异常类型本来不同，没对齐就会红——让它自愈：

```
测试红了，看报错自己修，改完再跑，直到绿。
```

**④（可选）再加一道独立验证**：

```
两个 app 测试都绿之后，用 CRM 的 --dry-run 把重构前后「将要发给飞书的请求」
各导一份，比对它们是否完全一致——证明对飞书的行为没变。
```

> 💡 学习点：让 AI 大规模改代码不可怕，靠的是**安全带四件套**——① 先方案后动手 ② 分批 + diff 审查 ③ 测试兜底 ④ dry-run / git 回滚。记住这四条，以后改任何项目都不会翻大车。

---

## 4. 给重构上工程化护栏：三道关

> 三道关由近及远：**本地 pre-commit → 云端 GitHub CI → PR 自动摘要**。第一道人人可做；后两道要 push 到一个你有写权限的仓库（你自己的 fork 或私有库），不要 push 到课程公共仓库。

**① pre-commit 钩子**（本地，人人可做）：

```
写一个 pre-commit hook：谁的提交里直接硬编码了 open.feishu.cn、
或绕过 FeishuClient 自己拼 token，就拒绝提交并提示走共享客户端。
只检查 claude-code/multi-file-refactor/ 目录。
装好后，故意制造一次违规提交验证它能拦住，验证完把探针改动撤掉。
```

亲眼看到「想偷懒、提交不进去」——这就是把规矩从「期望」变成「机制」。

**② GitHub CI**（进阶，在你自己的 fork / 有写权限的仓库上做）：

```
给本节工作区写一个 GitHub Actions workflow：push 后自动跑这两个 app 的测试，
再扫一遍有没有硬编码密钥。然后切一个临时分支，把 workflow 和重构一起提交、
push 到这个远端分支——CI 会在 push 时自动跑起来（测试 + 扫密钥）。
```

**③ PR 自动摘要**（进阶，同上）：

```
重构已经在那个分支上、CI 也绿了，现在基于这个分支开一个 Pull Request 到 main：
CI 会在 PR 上再跑一次当合并门禁，标题和 PR 语义摘要你来写（讲清抽了什么、
两个 app 怎么受影响、测试过没过）。review 通过后合并、删掉临时分支。
```

> 💡 push ≠ 再推一遍代码：push 是把分支传上去、顺带触发一次 CI；PR 是为这个**已上传的分支**开一个到 main 的合并请求——再触发一次 CI 当门禁、出语义摘要、给 review/合并入口。所以 ② 和 ③ 是一条链上的两步，不是把改动推两遍。

> 💡 学习点：你不用是 CI/Git 专家——说人话，Claude Code 替你把工程化流水线搭起来。本地 pre-commit、云端 CI、PR 摘要，三道关让「干净的代码」一直干净。

---

## 5. 课后作业

1. **必做**：`xhs-auto-publisher/src/cloud_notify.py` 也碰飞书，但还没用上共享客户端。按第 3 步的四件套，让 Claude Code 把它也接到 `FeishuClient`，三个 app 全部收口。
2. **进阶**：给你自己的某个项目装一个 pre-commit Hook，挑一条你最在意的规矩去守。
3. **选做**：让 Claude Code 为你的项目生成一份 `CLAUDE.md`，体会下次对话「一上来就懂」的差别。

---

## 小结

- **读懂**：给目标，它自己 Glob/Grep/Read 吃下整个项目群，不用你喂文件。
- **重构**：跨多文件、多项目的语义级重构，靠安全带四件套保你睡得着觉。
- **护栏**：pre-commit + CI + PR 摘要，让干净的代码一直干净。

从「指挥业务流」到「驾驭 AI 做代码级工程」——这一节你迈过去了。
