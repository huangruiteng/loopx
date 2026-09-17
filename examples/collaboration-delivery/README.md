# Allocation delivery with three managed Agents

[中文](#中文操作说明) · [Capability contract](../../loopx/capabilities/manager_context/README.md#semantic-delegation-and-peer-review)

This demo runs real `dsh` workers through `loopx turn run-once`: builder requests
an analyst's model, consumes its versioned artifact, implements a solver, obtains
independent review, incorporates an owner correction, obtains a second review,
and returns both results to the original conversation. Each phase has a fresh
execution session but retains its registered Agent identity and durable Inbox.

The task has six orders, shared stock, regional capacity, an integer-cent budget,
a high-value zero-demand order and a deterministic tie-break. The owner rejected
proportional rounding. Round two adds reserve stock and a minimum East allocation.
The independent exhaustive oracle never imports the generated solver.

| Input version | Allocation in id order a–f | Value | Cost |
| --- | --- | --- | --- |
| Initial | 1, 1, 3, 2, 0, 2 | 84 | 1000 |
| Reserve 1; East minimum 4 | 2, 1, 3, 1, 0, 2 | 83 | 990 |

These expectations were derived before worker execution. Correctness includes
the exact allocation, not only the objective value. Do not supply this table or
`verify.py` to the reviewer as its reasoning; it must derive its own expectations.

## Run

Run from the LoopX source root on a supported dsh host, with Git, Node and the
selected Python environment available:

```sh
uv sync --extra test --extra deepseek-harness
```

Configure `DEEPSEEK_API_KEY` through your normal credential setup. The controller
only consumes this environment variable; it does not discover credentials or
store them. Model runs are explicit, billable calls: seven successful phases,
each capped at 600 seconds. Stop on a failed phase and inspect its private
receipt before spending more; a retry may require a new Turn identity if the
original Turn recorded terminal failure. Use `--attempt 2` (then 3, etc.) to
create a new bounded Turn while retaining earlier results. Before a repair run,
write concrete findings in that worker's `outputs/repair-feedback.md`; rerun the
builder phase, transfer its artifacts, rerun the reviewer with the same new
attempt number, then repeat the independent verifier. Never overwrite an approval
or skip the failing case. No model calls run in CI.

Define a convenience command in your shell:

```sh
demo() { uv run --extra test --extra deepseek-harness python examples/collaboration-delivery/demo.py "$@"; }
demo prepare
```

`prepare` requires a **new** `.local/allocation-demo` directory. It creates a
disposable registry, Goal state, synthetic Git repository, three worktrees and
per-worker Cordis patches. It seeds the owner's typed Chat request explicitly;
this is a controlled fixture, not a test of natural-language team creation. All
later work assignments use the existing Todo CLI. No active user Goal is used.
Pass `--root <fresh-path>` to every command to select another isolated run.

Run the dependency chain one phase at a time (default model
`deepseek-v4-flash`, reasoning `high`; override with `--model`):

```sh
demo run --phase builder-1 --execute
demo run --phase analyst-1 --execute
demo transfer --phase analyst-1
demo run --phase builder-2 --execute
demo transfer --phase builder-2
demo run --phase reviewer-1 --execute
uv run --extra test python examples/collaboration-delivery/verify.py .local/allocation-demo/agents/reviewer
demo transfer --phase reviewer-1
```

Inspect the review and verifier output. A failure is a failure: do not continue
as though acceptance passed. After passing round one:

```sh
demo correct
demo run --phase builder-3 --execute
demo transfer --phase builder-3
demo run --phase reviewer-2 --execute
uv run --extra test python examples/collaboration-delivery/verify.py .local/allocation-demo/agents/reviewer
demo transfer --phase reviewer-2
demo run --phase builder-final --execute
demo readback
```

`correct` writes a new input version and a new immutable owner request. The old
request retains its original digest. `readback` uses the real return pump and
checks that a second drain sends nothing; `conversation.json` retains the
result. The packaged frontend can show the same brief, receiver facts and returns:

```sh
uv run --extra test loopx --registry .local/allocation-demo/registry.json \
  --runtime-root .local/allocation-demo/runtime chat --no-open
```

Open the printed URL and choose the manager conversation. The generated
`outputs/model.json`, `solver.py`, `outputs/review-r1.md`, `outputs/review-r2.md`
and `outputs/final.md` are real worker artifacts. Inspect them, rather than
counting tool calls or trusting a success sentence. Turn receipts distinguish
host execution, artifact/route validation, writeback and settlement. The separate
oracle checks nine positive/infeasible cases and five malformed inputs.

## Conversation preview

Packaged-browser screenshots use synthetic UI fixtures, separate from the live
model qualification: [before](screenshots/before.png),
[desktop brief](screenshots/desktop.png), [mobile brief](screenshots/mobile.png).

## Boundaries and recovery

The controller selects bounded phases, transports an explicit artifact list
through signed synthetic Git commits, and changes the fixture input. Workers
independently read/assess requests, author artifacts, request peers and return
results. This demonstrates dependency adoption and continuation across fresh
sessions, not autonomous scheduling or full roadmap G1/R2 qualification.

The MCP patch binds Goal, Agent and workspace outside model arguments. It keeps
dsh `workspace-write`, exposes five Inbox tools and adds no shell, Todo/lease
writer or network listener. Relative references and hashes do not transfer
files, certify comprehension or transfer ownership. Same-host, same-Goal peers
are supported; cross-host authority, Lark peer forwarding, stop/lease takeover,
24-hour continuity and hundred-Agent scale are not qualified by this demo.

To stop, end the active bounded command and launch no further phase. Remove the
per-worker Cordis patch from your runtime configuration and restart that worker
to disable the tools; existing Inbox records remain. The demo's source repository
and worktrees all live under its disposable root. After processes exit, delete
only that root when its evidence is no longer needed. Never copy its runtime,
raw model logs, credential configuration or machine paths into public artifacts.

## 中文操作说明

这个 demo 演示的是一条可检查的交付链：**管家交办 → builder 向 analyst
求助 → 使用模型产物实现求解器 → reviewer 独立复核 → 用户修订要求 →
重新计算及第二轮复核 → 回到原对话报告结果**。每个阶段启动全新 dsh 会话，
持久 Inbox、注册身份与真实文件把前后工作连接起来。

按照上面的命令从仓库根目录运行。先安装 `test` 和 `deepseek-harness` extras，
通过已有凭据管理方式配置 `DEEPSEEK_API_KEY`，再执行 `demo prepare`。
它只创建隔离的演示目录，不调用模型；七个 `demo run ... --execute` 才会产生
真实模型调用，每个阶段最多 600 秒。可用 `--model` 选择模型，用 `--root`
选择另一全新目录；同一轮所有命令应使用相同目录。

`transfer` 由控制器通过 Git 交接指定文件，并记录提交和实际摘要。Agent 自己
读取材料、决定是否采纳、发起同伴请求、写实现及复核报告、提交结论。两次
`verify.py` 是独立的穷举验收，不能以 Agent 自称通过代替。第一轮结果应为
价值 **84**、成本 **1000**；新增“每组预留一件、东区至少四件”后应为价值
**83**、成本 **990**，分配向量见上表。失败时停下检查结果，不把失败改写成通过。

`demo readback` 会运行原有结果回传服务，并检查重复执行没有新增投递。
启动上面的 `loopx chat` 后，在管家原对话即可查看交办说明、接收方判断和
最终结果。无需新增导航入口或改变 Kanban。

这里的初始管家请求由测试控制器明确写入；不是自然语言创建团队的验收。
它证明同主机、同 Goal 的真实产物协作与新会话续接，不证明无人值守调度、
跨主机协作、Lark 同伴转发、停机接管、跨日持续运行或百 Agent 规模。
MCP 仅提供绑定身份的五个 Inbox 工具，保留 dsh 文件沙箱，不授予额外 shell、
Todo/lease 或发布权限。停止运行后，不再启动下一阶段即可；移除 Cordis 配置
并重启相应 worker 可停用工具，已有请求与回复保留。确认进程退出后，只删除
这次演示的隔离目录。凭据、原始日志和本地运行状态不要提交到仓库。
