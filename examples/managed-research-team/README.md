# Synthetic research team

A local coordinator organizes two local DSH Agents and two cloud Ark Agents
to analyze a filing and its correction. An Ark reviewer adopts a local
analyst's result, independently checks it, and returns evidence for the local
coordinator's combined report. There is no `phase` argument or script that
selects the next business step. The model chooses questions and delegation order
through the [shared local delegation interface](../../docs/reference/local-delegation.md).

This composition example prepares an isolated synthetic Goal, roster and
worktrees, then starts one local DSH coordinator Turn. Each member uses existing
Todo, Turn and TS acceptance owners. Ark is an [optional execution provider](../../packages/loopx-ark-turn/README.md).
The example supplies domain inputs, validators and operator bindings; it does
not implement a separate scheduler or task database.

## Run

From a matching source checkout, install both optional providers into the same
interpreter. Node 24.21 or later qualifies the File/SQLite example.

```bash
uv sync --extra test --extra deepseek-harness
uv pip install --python .venv/bin/python -e packages/loopx-ark-turn
```

Set `ARK_API_KEY`, `ARK_MODEL_ID`, `ARK_ENVIRONMENT_ID` and `DEEPSEEK_API_KEY`
in the environment. The Ark Environment must already belong to the operator;
this launcher never creates or deletes it. The local model defaults to
`deepseek-v4-flash@high`; select another profile with `--dsh-model`.

Choose a **new private disposable directory**. Never point this example at an
active Goal or research workspace. The canonical Goal quota governs admission;
this version no longer has the old demo-only two-attempt counter. Each binding
has a finite deadline, and rejected attempts may still incur provider usage.
The local lead and nested cloud coordinator have up to 20 minutes each; other
members have five-minute host budgets, including cleanup. These are per-binding
limits, not a fleet-wide currency cap.

```bash
uv run --no-sync --extra test python examples/managed-research-team/research_team.py \
  run "$DEMO_ROOT" --model "$ARK_MODEL_ID" --environment-id "$ARK_ENVIRONMENT_ID"

uv run --no-sync --extra test python examples/managed-research-team/research_team.py \
  validate-report "$DEMO_ROOT"
```

The launcher succeeds only after the lead's validated Turn and canonical Todo
completion. Read `completion.json`, `lead/report.json`, `lead-turn.json`, the
private collaboration execution receipts and `provider-receipts/`. They are local
experiment records, not publishable fixtures. Canonical readback:

```bash
uv run --no-sync --extra test python -m loopx.cli \
  --registry "$DEMO_ROOT/registry.json" --runtime-root "$DEMO_ROOT/runtime" \
  --format json todo list --goal-id synthetic-managed-research

uv run --no-sync --extra test python -m loopx.cli \
  --registry "$DEMO_ROOT/registry.json" --runtime-root "$DEMO_ROOT/runtime" \
  --format json goal-acceptance verify --goal-id synthetic-managed-research --execute
```

## Collaboration path

### Keep an existing Codex or other local lead

Use `prepare` instead of `run` to provision only the disposable fixture and
operator bindings. It makes no model call and does not start another lead
session. Keep the provider setup above, including the existing Environment:

```bash
uv run --no-sync --extra test python examples/managed-research-team/research_team.py \
  prepare "$DEMO_ROOT" --model "$ARK_MODEL_ID" --environment-id "$ARK_ENVIRONMENT_ID"
export LOOPX_RESEARCH_DEMO_ROOT="$DEMO_ROOT"

uv run --no-sync --extra test loopx --registry "$DEMO_ROOT/registry.json" \
  --runtime-root "$DEMO_ROOT/runtime" --format json delegation list \
  --goal-id synthetic-managed-research --agent-id lead \
  --execution-config "$DEMO_ROOT/delegation-config.json"
```

The existing Agent then uses [delegation start/read/wait/resume](../../docs/reference/local-delegation.md#use-an-existing-agent-conversation-through-its-shell)
for the listed bindings, writing its own briefs. It reads the synthetic
`input.json` files and returned artifacts, chooses the work order and continues
its own analysis while members run. The nested cloud analyst still requests
its local reviewer through the same service. No business phase argument is
introduced.

After reading all four canonical completions and exact artifact hashes, the
lead writes `lead/report.json` with the fields described by `scenario.py` and
the acceptance table below. Run `validate-report`, then complete the report
through ordinary `todo complete --todo-id todo_lead-report --agent-id lead
--no-follow-up` against this disposable registry/runtime. That command reruns
the bound validator. Retain the original conversation; preparation does not
attach, resume, migrate or impersonate any existing production Agent.

### Member relationships

The primary `local-led` profile has four independently accepted member tasks:

- The local lead delegates initial-filing analysis to local DSH `local-analyst`.
- Ark `cloud-reviewer` independently verifies that completed artifact and adopts
  its exact hash. Starting early cannot bypass the prerequisite's acceptance.
- Ark `cloud-analyst` receives the corrected-filing task and itself delegates
  independent review to local DSH `local-reviewer`, preserving the parent
  request. It waits for acceptance and adopts the returned artifact.
- The local lead reads all four accepted artifacts, resolves the revision and
  source distinctions, and writes the combined report with exact dependencies.

The two branches may run concurrently. The model chooses when to start, what to
ask, whether to repair rejected work and how to synthesize. The host provides
bounded `list_execution_bindings`, `start_delegation`, `wait_delegation`,
`read_delegation` and `resume_delegation` operations. Members independently
`assess_request`; a read, message or tool ACK cannot complete a task.

The optional `--topology cloud-led` profile retains Ark-to-DSH coordination as
an additional route. It does not substitute for the primary local-led path.

## Independent acceptance

| Evidence | Initial | Corrected | Required conclusion |
| --- | --- | --- | --- |
| Cash from operations | 120 | 105 | Consume the correction |
| Capital expenditure | 30 | 30 | Raw FCF is 90 → 75 |
| Receivables sold | 50 | 50 | Normalized FCF is 40 → 25; delta −15 |
| Fiscal period comparison | H1 vs FY | H1 vs FY | Growth is unsupported |
| Repost of issuer material | Same source | Old figures retained | One current-period source family; corrected repost is stale |

`bootstrap.ts` creates only a fresh disposable canonical runtime and invokes
the production owner configuration API once. It binds four member criteria and
one report criterion. Task instructions, the roster and verifier files are
pinned; a member cannot change its own acceptance. Existing Goals are never
promoted or rewritten by this bootstrap.

Core delegation asks the TS acceptance owner for the exact task's criteria and
runs those checks as its Turn validator. It then uses ordinary `todo complete`,
which re-executes validation and atomically commits through the same TS owner.
The report separately checks all four canonical completions, current binding
guards, adopted hashes and financial conclusions. All five Todos may be done
while the overall Goal remains active for its owner.

A member's own peer conclusion is preserved. The delegation result independently
reports canonical acceptance; it does not replace that message or trust a
model-authored `accepted` flag. Saved artifacts and old receipts cannot hide
changed inputs, stale work or modified output.

## Recovery and validation

A delegated worker runs independently of the requesting MCP conversation. A
new connection reads its original operation id. Repeating that operation or
resuming a live worker cannot start a concurrent duplicate. After process loss,
recovery uses the original Turn journal. Ark observes its original cloud session
and input; acknowledged tool effects are not repeated. While the host is absent,
cloud computation can continue until it needs a local tool, then waits.
Unknown creation/input acknowledgements or interrupted tool side effects require
explicit reconciliation. Reconnecting does not reset the original deadline.

Durable tests use the production CLI, File/SQLite authority, TS acceptance and
real stdio MCP, with explicit model substitutes where appropriate. They cover
missing adoption, conflicting operation ids, ungranted actors, concurrent
resume, stale/changed artifacts, prerequisite completion and preserved peer
conclusions. Provider tests restore actual execution checkpoints and verify no
new input or acknowledged tool effect. TS acceptance also runs on isolated real
PostgreSQL; no model calls occur in CI.

```bash
uv run --no-sync --extra test python -m pytest -q \
  packages/loopx-ark-turn/tests tests/test_collaboration_mcp.py
```

Real execution qualification uses the public Ark SDK and DSH with synthetic
materials. A process-loss drill kills the owned worker/Turn/provider process
group after the input ACK, observes cloud `requires_action`, then resumes the
same operation to canonical completion. It confirms one provider receipt, the
same Session and input, and cleanup of owned resources. This evidence is
separate from mocked provider tests and does not establish market-research
quality, arbitrary team scale or attached persistent Codex-task integration.

## Boundaries and cleanup

The operator owns Agent registration, bindings, workspaces, executables,
credentials and validators. The model cannot grant new execution authority.
Leaf DSH tools receive no provider credentials. The local lead forwards the
credentials needed for its authorized execution bindings by environment
reference; Ark's local tool process receives the DSH credential only when it
must launch that local member. Ark credentials never enter cloud tool inputs or
results. MCP servers need trusted local OS isolation.

On normal completion Ark deletes its owned Session and Agent and confirms
absence. Retain private receipts after interruption and use the adapter's
cleanup command for known resources. The Environment remains operator-owned.
Disable admission by removing grants or the explicit execution configuration;
stop/reconcile existing workers before deleting the disposable runtime.

This slice provides fixed authorized work, dependent artifacts, nested requests
and local recovery. General Agent creation, dynamically derived work, full
inbox/queue/steer, remote authority and Dashboard/Lark configuration remain with
the existing RFC owners. No default executor, product navigation or recurring
monitor changes here.

## 中文操作与能力说明

主路径由本地 DSH 协调员带领两个本地 DSH 和两个云端 Ark 成员。初始披露走“本地
分析 → 云端独立核验”；修订披露由云端分析员继续委派本地核验员，采用其结果后
返回。最后由本地主 Agent 综合四份带哈希的已验收产物。一次启动之后由模型决定
问题、并发顺序、修正与汇总，不输入 `phase`，也没有示例专用业务调度器。

成员必须先自行记录采用请求，再经过 Turn 验证、普通 Todo 完成入口的重新验证和
TS 提交。主 Agent 断开后，已启动的委派仍可继续；整组本地进程中断后，使用原操作
ID 接回原 Turn 和云端 Session。云端需要本地工具时会等待，不能据此宣称完全离线
自主运行。副作用是否已发生不明时保留记录并核对，绝不自动重复执行。

依次运行上面的安装、`run`、`validate-report` 和 canonical readback 命令。所有数据
是合成投研材料，归一化自由现金流应为 40 → 25、变化 −15，不支持跨期间增长判断。
总体 Goal 保持 active。真实执行记录留在私有实验目录；公开仓库保留可复用接口、
合成案例和验证方法。
