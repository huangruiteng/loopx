# RFC：共享 Goal 的在线权威与可插拔协调 Provider（v0）

- 状态：Draft，正在接受 maintainer review
- 提案方：NoKV Lab
- 日期：2026-08-05；修订于 2026-08-18
- 范围：LoopX 共享 Goal 协调的独立部署合同，用来补充
  [`host-integration-surface-v0`](../../reference/protocols/host-integration-surface-v0.md)
- 源码基线：LoopX `c6a1da1eaa22962faaeb6d4050d867462e7665ff`
- Provider API 基线：NoKV `3d75d96965`（0.11.0 线）。Python `publish_bytes`
  generation-CAS 映射已在该基线的真实 NoKV stack 上手工跑过一次（见示例 README）；
  该次运行只是映射本身的证据，不属于任何合并门槛
- 语言说明：[英文版](./shared-goal-authority-state-provider-v0.md)与本中文版互为
  语义镜像；两者不一致属于缺陷

---

## 0. 一个用来帮助大家理解的例子

例 1：模拟一次真实的机器 -> 人 -> 机器 handoff，为什么浪费时间

比如，我在开发机上的 agent 做完了一个 Rust PR，笔记本上的 agent 负责 review。
整个交接过程按时间顺序是这样的：

- **T0**：开发机 agent 完成修改并创建 PR；
- **T1**：代码通过固定的 head SHA 交付。这一步由 Git 完成，所以代码传递本身
  不是问题；
- **T2**：我手工把 PR、源任务和 review 要求发给笔记本上的 agent，告诉它有新活；
- **T3**：笔记本 agent 接单，但如果响应刚好丢失，我只能从它后来的行为反推它
  是否真的认领成功。

真正浪费时间的是 T2 和 T3：机器已经把工作做完了，下一台机器却还在等人转发；
即使已经接单，也没有一张可以在崩溃后重新取回的凭证。Harness 再快、模型推理再
快，也补不回人离开电脑以后这段空等。

完整需求显然同时包含“怎么通知下一台机器”和“怎么确认它真的接住了”。但第一版
RFC 不应该一口吞掉消息、调度、配额、run history 和所有 LoopX 文件。本版先把最
硬的一段做对：笔记本认领 review todo 时，只有一个端能成功，并且成功后拿到一张
可重放的原始回执。通知和唤醒仍由
[`Agent IM、LoopX 与 OpenViking 协作 v0`](./agent-im-openviking-collaboration-v0.md)
里的 delivery plane 负责。

## 1. 这份 RFC 最后选择了什么

把 authority 想象成唯一的记账员。各端不直接改账，只提交“我要认领这项工作”的
申请。记账员检查目标 todo、身份、命名依赖和 gate；通过就把认领、lease 和回执
一起记下，不通过就明确告诉申请人原因。

这次只给记账员一本很小的账，而不是把 LoopX 的所有文件都搬进远端：

1. 一个显式启用共享模式的 Goal，只有一份 **canonical coordination aggregate**；
2. 每条成功 operation 的状态变化和原始 receipt 必须在**同一次 CAS**里落账；
3. authority 负责判断，provider 只负责把确定性字节可靠保存下来；
4. run history、status、quota、scheduler、host session 和 evidence body 继续由各自的
   owner 管理，不塞进这本协调账。

NoKV 是记账员身后的可选 provider。Agent 不会为 coordination write 直接连接
NoKV，NoKV 也不会因此变成 LoopX 的控制面权威。

第一个能跑的例子只有 `claim_work`：对一个已经存在且可执行的 todo，同时写入 soft
claim、lease/fence 和 receipt。它先回答两件最容易出事故的事——多人同时抢单时谁
赢，以及响应丢失后怎样找回原回执——而不把完整 lease lifecycle 说成已经交付。

这里的争用单元是 `(goal_id, todo_id)` 及该 todo 实际引用的 precondition，不是整个
Goal。两个端抢同一个 todo 时只能一胜；两个端认领同一 Goal 下彼此独立、目标范围
内的 authorization、dependency 和 gate 均未变化的 todo 时，即使底层先后竞争同一
个 aggregate CAS，authority 也应 reload、重验并在内部完成重试，而不是把 provider
head 前进暴露成业务冲突。这与 LoopX 当前公开
[`architecture.md`](../../architecture.md) 中 todo-level 的并发形状保持一致。

举一个最关键的失败序列：operation A 成功拿到 lease `L1`、epoch `7`，但响应丢了；
随后同一 Goal 里另一个独立 todo 的 operation B 又把账本推进了一页；B 没有接管
A 的 todo。A 重启后再次提交同一申请，必须逐字段取回自己当时的原始 receipt。
只告诉 A “这笔账以前记过”以及 B 的当前版本不够，因为没有 `L1`、epoch `7` 和
expiry，A 仍然无法证明自己获准执行过这项工作。

### 1.1 稳定抽象：存储面、语义权威与持续协调

这里最高价值的边界，不是把“LoopX Server”和“NoKV Server”理解成两个彼此竞争的
数据库，而是三个拥有不同正确性合同、可以共同部署但必须分别归属的层次：

| 层次 | 负责什么 | 绝不能负责什么 |
| --- | --- | --- |
| 存储面 | 耐久字节与 artifact、provider generation CAS、snapshot 与 provider recovery | Goal/todo 语义、actor eligibility、lease 或 authority receipt |
| 语义权威 | normalized command、目标范围 precondition、claim、lease epoch、fencing、revision 与原始 receipt | raw artifact body、provider placement 或后台调度状态 |
| 持续协调层 | 通过同一 command contract 完成观察、过期 lease 恢复、wake request 与持续 Supervisor 决策 | 直接改写 head、绕过 provider 边界，或形成第二个 coordination 真相源 |

NoKV workspace service 是本 RFC 映射的候选存储面实现，仍须经过下文的分阶段验证。
LoopX 的增量是语义权威：它把 opaque generation CAS 变成可信的 `claim_work`
结果，并在后续扩展成可恢复的执行权。持续协调层只是 authority 的 client，不是另
一个 writer：Supervisor 观察 projection，通过 typed command 发起 reclaim，或请求
delivery plane 执行 wake；它自己的 scan cursor 与调度状态继续留在 coordination
head 之外。Transport 与 endpoint reachability 仍由 delivery plane 负责；wake 已送达
永远不能证明 authority command 已提交。

同一套 NoKV deployment 可以服务两条刻意分开的路径：

- **coordination path** 只保存 canonical head，并且只有 authority 持有写 credential；
- **artifact path** 可以允许 runtime 在受限 scope 内发布 checkpoint 或 evidence，
  但只有 opaque pointer、digest 与 privacy class 可以进入经 review 的 coordination
  transition。

可恢复工作流先发布 immutable checkpoint 或 evidence artifact，再在相关 coordination
transition 中提交它的 pointer。若第二步之前失败，只会留下由独立 retention 或
collection 处理的无引用 artifact；绝不能让 head 指向从未耐久发布的对象。因此，
共享同一个物理 provider 不会合并两套 ownership contract，也不要求跨领域事务。

物理上允许共同部署。一套 deployment bundle 可以同时启动 NoKV workspace service、
LoopX authority endpoint 和 Supervisor worker。这里的“分开”是指 contract 与
credential 分别归属；v0 不要求它们必须拆成不同仓库、进程、binary 或 license。
可信本地验证可以使用 embedded authority。共享部署则需要在线 authority boundary，
确保不可信或过期 client 即使合法持有受限 artifact credential，也无法发布伪造的
coordination head。

### 1.2 能力展望与可部署产品边界

上述分层在不扩大 v0 ledger 的前提下形成了分阶段能力展望：

| 阶段 | 新增能力 | promotion 前必须证明什么 |
| --- | --- | --- |
| 确定性共享协调 | provider-neutral authority、state-plus-receipt CAS、replay 与目标范围 rebase | file-backed conformance 与第 10 节的 P0 检查 |
| 可恢复执行权 | renew、release、过期 lease reclaim、stale-fence rejection，以及带 continuation/evidence pointer 的原子 completion | crash 与 clock-boundary 测试证明被替代 executor 无法 write back |
| 持续协调 | Supervisor observation、reclaim、delivery-plane wake request，以及通过 authority command 编排 remote resume | restart-safe reconciliation，且没有直接 provider write 或内存正确性依赖 |
| 服务级共享控制面 | authenticated principal、tenant-to-goal 隔离、audit、有界容量、observability、service recovery，以及最终的 HA | 显式 deployment 与 migration contract，且不存在 authority bypass 或静默本地 fallback |

这份能力展望不会把 quota accounting、run history、raw evidence、delivery state 或
Supervisor runtime state 搬进 coordination aggregate。这些能力继续由第 3 节所列的
owner 与 ledger 管理，通过 typed command、projection 或 opaque pointer 连接。

给 Apache coordination core 套一层很薄的网络 wrapper，本身不足以形成新的产品边界。
只有当一个独立交付的服务真正拥有网络信任边界，以及 authentication、持续监督、
远程恢复、migration、audit、multi-tenancy 或 HA 等实质 authority/reconciliation
能力时，独立发行才有意义。若项目将来创建单独授权的 server distribution，它的
边界应沿着这一可部署的语义权威与持续协调 surface 切分，而不是沿 NoKV adapter 或
provider-neutral core 切分。本 RFC 既不要求拆仓，也不选择独立 license；当前政策
仍以 [`LoopX Licensing`](../../project/licensing.md) 为准。

## 2. 要做的，以及不要做的

**这版要做的**

- 为一个共享 Goal 提供在线、provider-neutral 的 coordination authority；
- 让同一 todo 的并发 claim 只接受一个 owner，同时允许独立 todo 在内部 CAS rebase
  后分别成功；
- 把每个 operation identity 绑定到一份 normalized request digest，换一套语义复用
  同一个 id 时明确拒绝；
- 即使后续 operation 已推进账本，也能找回原始 receipt；
- 保持 LoopX 默认本地模式不变；
- 把现有每一类持久状态该怎么接入说清楚。

**这版明确不做的**

- 不给所有 LoopX 状态造一个通用分布式文件系统或数据库；
- 不做离线多写者 merge，也不允许离线创建受控写；
- 不把 message delivery、wake-up、presence 或 Agent IM 协议混进存储合同；
- 不定义多租户公网部署、认证协议、HA 或 provider failover；
- 不把 quota、scheduler、run history、raw evidence、host session 或 extension ledger
  搬进 coordination head；
- 不自动 promotion 当前 event projection 或任一 provider；
- 不允许 Agent 或 extension 绕过 authority 直连存储。

## 3. LoopX 现在有哪些账，各自怎么接入

Owner 提出的关键问题是：LoopX 现有状态分散在不同文件里，不能看到一个持久化
文件就把它塞进同一个 head。比如两台机器各自记录的本地路径都是真的；status 是
算出来的；quota accounting 又是一笔笔追加的账。它们不是同一种写模型。

所以下表先把这些账摊开：今天谁在写、怎么写，以及进入共享模式后应该归到哪里。
它按逻辑状态和字段组组织，而不按固定文件数组织；一个物理文件可以混合多个
owner，新 host 或 extension 也可以新增本地 artifact，而无需修改本 RFC。

下表采用这些接入类别：

- **shared canonical**：只有显式启用 shared mode 后才是权威；
- **derived**：从所命名的 source 重算；永不接受 lifecycle 写入；
- **synchronized ledger**：依据稳定 identity 和自身 append 合同复制或求并集，
  不进入 coordination head；
- **host-local**：只对一个 host、runtime 或 checkout 有效；
- **independent ledger**：保留其 capability 或 accounting owner；
- **excluded body**：跨边界时只允许 redacted digest 或 pointer。

| 逻辑状态 / 当前 surface | 当前 owner 与写模型 | v0 接入策略 |
| --- | --- | --- |
| `ACTIVE_GOAL_STATE.md` 中的 todo lifecycle、soft claim、dependency 与 gate 字段 | Markdown active state 仍是当前真相源。Todo 命令在本地文件锁下整文替换；仅当 event log 已存在时才使用 state-event projection。 | 启用 shared mode 后，只有校验 P0 命令所需的 normalized fields 成为 **shared canonical**。默认模式下 Markdown 继续 canonical；shared mode 下，它对已迁移字段变为本地 projection。私有 prose 排除。 |
| `goals/<goal>/task-leases/` 下的可选 hard task lease | 每个 todo 的 JSON 在 goal-local lock 下原子替换；release 保留 inactive terminal record，避免 re-acquire 时 version 与 `lease_epoch` 发生 ABA。Lease 是否有效还读取 todo status、soft claim、exclusion 和 registered agents。 | 把 claim、lease、terminal generation 与 fence 折入同一个 shared aggregate 和 authority revision。Shared mode 下不保留独立可写 lease file。 |
| 已应用 operation receipt | LoopX 已有 scoped receipt 先例，包括 Turn journal 与 heartbeat receipt，但没有耐久的 shared-goal operation-to-receipt index。 | 新增可重放 receipt index 作为 **shared canonical**；它与 state transition 在同一次 CAS 中提交。 |
| Project registry 的逻辑 identity、agent profile、grant 与 policy | Project registry 是本地配置，以 JSON replacement 写入。这些字段与 route、私有 reference 混在一起。 | Authority 消费显式版本化的紧凑 authorization projection 或 digest。整个 registry 不进入 coordination head，registry mutation 也不是 P0 命令。 |
| Project/global registry route：`source_registry`、repo checkout、state file、runtime root | Global registry 是同步得到的 host-local route projection，并记录本地绝对路径。 | **Host-local**。需要时共享稳定 Goal/repository identity，绝不共享 route path。 |
| `events.jsonl` 中的候选 state event | 当前 migration bridge 仍以 Markdown 为权威。Event append 使用本地锁；多 event append 不是 transaction。 | 只作 read-only shadow/canary input。本 RFC 不 promotion 它，也不用它证明 atomic completion。 |
| Run JSON/Markdown 与 raw evidence body | Run writer 预留本地 artifact name，再写入详细 record。内容和 path 可能是私有的。 | **Excluded body** 或外部 artifact-store object。只有在后续命令需要时，aggregate 才可携带 opaque pointer、digest、privacy class 与精确 code revision。 |
| `runs/index.jsonl` run history | 混合 append index，引用 run artifact，可能包含绝对路径；也携带包括 quota accounting row 在内的多种分类。 | 未来的 **synchronized ledger** 需要稳定 identity、deduplication 与 redaction。它不进入 coordination head。 |
| `rollout-event-log.jsonl` | 混合的 public-safe diagnostic stream。核心 CLI rollout append 刻意 best-effort，发生在主命令之后；普通 todo event 不按受控 operation identity 建键。 | **Derived** observability projection。Rollout append 失败不能使 coordination commit 失效，也不能证明 commit。 |
| Status 与 attention，包括 `status-projection-cache/*.json` | Status 从 registry、active state、run history、lease 等输入派生。可选 cache 是可替换的 host-local snapshot，其 key 包含本地 route input。 | **Derived**；cache 仍是 **host-local**，可随时丢弃。 |
| Quota policy | 本地 policy 配置在 registry 字段中。 | Head 之外的 configuration input。Receipt 可以引用本次采用的 policy revision，但 coordination provider 不拥有 policy。 |
| Quota accounting（`quota_slot_spent` / `quota_slot_voided`） | 详细 JSON/Markdown 加 `runs/index.jsonl` row 形成 append-style accounting history。当前 row 没有 shared operation identity 或跨 artifact transaction。 | **Independent ledger**。分布式实现需要 idempotent debit/void identity 与独立 retention contract。 |
| Quota enforcement 与 `should-run` decision | 从 policy、todo/status projection、run history、scheduler context 和 actor scope 计算。Heartbeat receipt 是特殊 rollout 用法。 | **Derived decision**。若未来全局 budget 要 gate claim，应签发独立 reservation/grant receipt；head 可引用它，但不能吸收 quota ledger。 |
| Scheduler state、liveness、host backoff 与 RRULE observation | Per-goal、per-agent、per-surface JSON 反映拥有该 scheduler 的 host。 | **Host-local**。不能把两个都有效的 host observation 当作冲突并用一个 global value 覆盖。 |
| Turn journal、`turn-sessions/` 与 Pi `.loopx/pi/` binding | Runtime recovery 与 session binding 为一个 host/session 写入，可能包含本地 path 或 task body。 | **Host-local**。Turn journal 是 receipt 设计先例，不是 shared coordination state。 |
| Supervisor、domain-state 与 extension runtime file | 每个 capability 定义自己的 schema、privacy、append/upsert rule 与 effect receipt。 | 依 capability contract 保持为 **independent ledger** 或 **host-local**。不得通用导入 head。 |

上述分类的源码锚点包括
[`architecture.md`](../../architecture.md)、
[`event-store-migration-bridge-v0`](../../reference/protocols/event-store-migration-bridge-v0.md)、
`loopx/control_plane/work_items/task_lease.py`、
`loopx/cli_rollout.py`、
`loopx/control_plane/runtime/status_projection_cache.py`、
`loopx/control_plane/quota/slot_accounting.py`、
`loopx/global_registry.py`，以及这些 host state：
`loopx/control_plane/scheduler/state.py`、
`loopx/control_plane/turn_driver/codex_cli.py` 和
`loopx/pi_goal_mode/pi-goal-loop-runtime.mjs`。

## 4. 这本协调账里到底放什么

一个 provider key 保存一个 Goal 的 v0 aggregate。以下形状仅作说明：

```json
{
  "schema_version": "loopx_coordination_head_v0",
  "goal_id": "shared-rust-review",
  "authority_revision": 43,
  "coordination": {
    "todos": {
      "todo_review": {
        "todo_revision": 9,
        "status": "open",
        "claimed_by": "laptop-reviewer",
        "eligibility": {
          "authorization_projection_revision": 3,
          "authorization_projection_digest": "sha256:...",
          "allowed_agent_ids": ["laptop-reviewer"],
          "dependencies_satisfied": true,
          "dependency_revision": 12,
          "gates_open": true,
          "gate_revision": 5
        },
        "repository": "git:example/repo",
        "code_revision": "0123456789abcdef",
        "last_lease_epoch": 7
      }
    },
    "leases": {
      "todo_review": {
        "lease_id": "lease_...",
        "owner": "laptop-reviewer",
        "lease_epoch": 7,
        "expires_at": "2026-08-06T03:30:00Z",
        "write_scopes": []
      }
    }
  },
  "receipt_index": {
    "op_claim_review_01": {
      "request_digest": "sha256:...",
      "original_receipt": {
        "schema_version": "loopx_authority_receipt_v0",
        "operation_id": "op_claim_review_01",
        "request_digest": "sha256:...",
        "command": "claim_work",
        "actor": {"agent_id": "laptop-reviewer", "device_id": "laptop"},
        "todo_id": "todo_review",
        "accepted_authority_revision": 43,
        "accepted_todo_revision": 9,
        "applied_at": "2026-08-06T03:20:00Z",
        "lease_id": "lease_...",
        "lease_epoch": 7,
        "expires_at": "2026-08-06T03:30:00Z"
      }
    }
  },
  "receipt_retention": {"mode": "retain_all_v0"}
}
```

该 schema 不包含 raw todo body、transcript、credential、绝对路径或 raw evidence。
它只包含裁决这一命令切片与恢复其凭证所需的事实。与现有 LoopX 一致，claim 后
todo 仍为 `open`，不会引入一个本地状态机不存在的 `claimed` status。在目标合同里，
soft ownership 由 `claimed_by` 表示，执行权由 lease/fence 表示；默认的 `legacy`
交接模式没有做到这一点：两本账分叉时，软认领方在写路径上实际胜出。声明了
`hard_lease` 的 goal 会把分叉变成类型化错误，并在完成时要求钥匙，详见附录 B。

这里的 eligibility revision/digest 都是目标 todo 所引用的快照：authorization 只覆盖
该 todo 的 actor scope，dependency 只覆盖它的传递依赖闭包，gate 只覆盖实际约束
它的 gate。它们不是换一个名字继续使用 Goal-wide revision。参考切片固定
`write_scopes=[]`；未来接入非空 write scope 时，与其他 active lease 的 scope overlap
也是该 claim 的真实跨 todo precondition，必须在内部 rebase 后重验并在冲突时拒绝。

这些 target-scoped token 还承担 coverage 与 no-ABA 义务。目标 todo 的 claim state
或 lease epoch 发生任何语义变化，都必须推进 `todo_revision`；allowed actor、依赖
闭包或满足结论、实际约束它的 gate 集合或结论发生变化，都必须推进对应 revision，
并在存在 digest 时同时更新 digest。同一个 token 不得复用于不同快照。Authority
无法证明这些覆盖关系时，不得内部 rebase。Deterministic reference 只验证静态
bootstrap snapshot，尚未资格化动态 projection publisher。

原始 receipt 证明某 operation 在某个 authority revision 被接受；它不证明对应
lease 当前仍有效。因此 replay response 返回逐字段等价的 `original_receipt`，同时
另行命名当前 observation，例如 `observed_authority_revision` 和
`authorization_status=active|expired|superseded`。

## 5. 受控命令怎样落账，崩溃后怎样找回回执

Request envelope 使用 `operation_id`，以免与现有 CLI 中 `command_id` 的用法冲突：

```json
{
  "schema_version": "loopx_command_v0",
  "operation_id": "op_claim_review_01",
  "actor": {"agent_id": "laptop-reviewer", "device_id": "laptop"},
  "goal_id": "shared-rust-review",
  "command": {
    "type": "claim_work",
    "todo_id": "todo_review",
    "expected_todo_revision": 8,
    "expected_preconditions": {
      "authorization_projection_revision": 3,
      "authorization_projection_digest": "sha256:...",
      "dependency_revision": 12,
      "gate_revision": 5
    },
    "lease_ttl_seconds": 600
  }
}
```

Authority 规范化完整的语义 request 并计算 `request_digest`。Digest 覆盖 actor、
Goal、command type、target todo revision、命名的 authorization/dependency/gate
precondition 与 command parameter；不覆盖 transport retry metadata。Goal-wide
`authority_revision` 不属于客户端业务前置条件，也不进入 request digest。调用方如需
携带读到的 head revision，只能把它作为 transport observation；改变该观测不构成
一条新的语义 operation。

对每个 request，authority 执行以下顺序：

1. load aggregate 与 provider generation；
2. 在执行当前状态校验之前查找 `operation_id`；
3. id 已存在且 digest 相同：返回 `already_applied` 与已存原始 receipt，不写入；
4. id 已存在但 digest 不同：返回 typed `operation_identity_mismatch`，不写入；
5. 校验 actor scope、目标 todo revision、命名 precondition、eligibility、claim state
   与本 reference 切片实现的 empty-scope lease rule；
6. 在 authority 中计算 next coordination state 与 original receipt；
7. 把 transition 和 receipt-index entry 一起放进一个确定性 envelope，并提交一次
   provider CAS；
8. provider 返回 conflict 或 ambiguous 后，reload，并在分类结果前重新查 receipt；
9. receipt 不存在且 generation 未前进时，以 `provider_outcome_unproved` fail closed；
   generation 已前进时，重新校验目标 todo 与命名 precondition，相关事实未变才基于
   latest head 重试。Receipt 缺失本身绝不证明成功；最终 `applied` 必须来自一笔新的
   successful CAS；
10. CAS miss 后，只有相关事实仍允许原命令时才继续 rebase；初始无效请求仍按普通
    domain validation 拒绝。纯粹的无关 head 前进不会成为业务 conflict；持续
    contention 耗尽 retry budget 时返回 typed `failed`，且不得创建 receipt。

API result class 如下：

| Result | 含义 |
| --- | --- |
| `applied` | State 与原始 receipt 一起提交。 |
| `already_applied` | 相同 operation 与 digest 早已提交；返回已保存的原始 receipt。 |
| `conflict` | 此 operation 不存在 receipt，且目标 todo 或命名 precondition 已 stale。 |
| `rejected` | Identity、eligibility、gate 或命令校验失败，未改变状态。 |
| `failed` | 无法证明存在 accepted result，或无关 provider contention 耗尽内部 retry budget；仅可依据有界基础设施策略重试。 |

`conflict`、`rejected` 和 `failed` 都不是成功凭证，不得得到伪造的 applied receipt。

### 5.1 第一个命令：`claim_work`

- `claim_work`：在一个 transition 中校验已有 runnable todo、设置 claimant、创建
  lease、铸造下一个 lease epoch，并保存原始 receipt。它的必填字段是 `todo_id`、
  `expected_todo_revision`、`expected_preconditions` 与 `lease_ttl_seconds`。

Accepted claim 同时推进 `authority_revision` 与目标 `todo_revision`。它只能操作由
显式 bootstrap/migration 安装的 todo，绝不把未知 todo 作为副作用创建。
Deterministic reference 的 eligibility input 是紧凑元组 `allowed_agent_ids`、
`dependencies_satisfied` 与 `gates_open`，并绑定到所命名的 authorization、
dependency、gate revision 与 digest。

`authority_revision` 是每条 accepted command 的 Goal-wide commit sequence，用于
审计、read model 和 receipt ordering，不是所有命令共享的 optimistic-concurrency
前置条件。底层 aggregate 仍以 `provider_generation` 串行提交；CAS loser 必须根据
自己的 target todo 与命名 precondition 决定是否内部 rebase，而不能仅因另一个独立
todo 已提交就要求调用方重新发一条 operation。

未知 command type fail closed。`renew_lease`、`release_lease`、过期 lease reclaim、
stale-fence writeback 校验、`complete_todo_with_successor`、transfer 或 delegated
assignment、任意 todo/gate mutation、quota reservation 与 external effect，都需要
后续 runtime 合同与 qualification。Production shared mode 前必须完成 renew/release/
reclaim 与 stale-fence 校验；此处省略是 scope control，不代表 claim-only runtime 已
完整。非空 write scope 与跨 todo scope-overlap 拒绝同样需要后续 command contract
与 qualification。只有 source completion、successor creation/assignment、evidence
pointer 与 receipt 能 atomic commit 时，completion 加 successor creation 才可进入
后续切片。

## 6. 谁做判断，谁负责保存

### 6.1 Authority 是记账员

LoopX authority 负责：

- request normalization 与 digest；
- actor、todo、dependency、gate 与 authorization 校验；
- 目标 todo 与命名 precondition 的业务冲突判定，以及无关 head 前进后的有界
  CAS rebase；
- `authority_revision` commit sequence 与 todo revision transition；
- 铸造 time、lease id、lease epoch 与 expiry；
- receipt 内容与 replay classification；
- privacy filtering 与 command-specific invariant。

### 6.2 Provider 只负责把账存稳

Provider contract 刻意不含语义：

```text
load()
  -> (aggregate | none, provider_generation)

compare_and_put(
  expected_provider_generation,
  aggregate
)
  -> applied(new_provider_generation)
   | conflict(current_provider_generation)
   | ambiguous
   | failed
```

Provider 必须对完整 aggregate 做确定性序列化，并提供 atomic conditional
replacement、durable success、same-key
read-after-write reconciliation，并在无法证明写入是否提交时返回 typed ambiguous。
它不得解析 LoopX command、铸造 clock/lease、裁决 eligibility 或合成 authority
receipt。领域 `operation_id` 与 request-digest replay 合同只存在于 authority 及其
原子保存的 receipt index 中，不是 provider API 参数。Provider 可以生成私有的
publication-attempt identifier，但该 identifier 不具有 LoopX authority 语义。

调用这些方法之前，provider instance 或 handle 已绑定一个 `goal_id` 与 provider
key；动词中省略 `goal_id` 并不表示该 key 是 global。

在这个二动词合同下，receipt index 不能作为单独 document 发布。先发布 receipt
可能为从未发生的 transition 记录成功；先发布 state 则可能在 crash 后丢失唯一
凭证。将来若要拆分，必须有 provider-neutral 的 multi-record transaction 或
commit-marker protocol，并通过新的合同 review。

### 6.3 三个版本号不是一回事

| 版本域 | Owner | 含义 | Consumer |
| --- | --- | --- | --- |
| `provider_generation` | Provider | 条件替换已存字节的 opaque token | 仅 authority/provider seam |
| `authority_revision` | LoopX authority | 接受一条 command 后的 per-goal 逻辑 commit sequence | 审计、receipt 与 read model；不作为所有业务命令的共享前置条件 |
| `lease_epoch` | LoopX authority | Ownership 的 per-todo fencing generation；新 lease generation 时推进，普通 renewal 不推进 | Executor 与获准 writeback |

Backend 常会对每条 accepted command 推进一次 generation，但数值相等永远不是合同。
Migration、repair 或 provider metadata 可以改变 provider generation，而不授予新的
LoopX authority revision。

对 NoKV 而言，它的 document generation 只实现 `provider_generation`。LoopX
authority 继续负责另外两个版本域与 document 内的 receipt。

## 7. 回执先全部保留，压缩以后再谈

v0 使用 `retain_all_v0`：任何已提交 receipt-index entry 都不得 GC、过期或从
snapshot 中省略。这是 correctness-first 的证明边界，不是 production-scale retention
承诺。

若 receipt-index entry 已存在，但其原始 receipt 缺失或无效，authority 将其视为
provider-protocol violation 并 fail closed。它不能 fallback 到 provider publication
history，也不得从当前 head 重建 receipt。

有界 retention window、receipt segmentation 或 external receipt ledger 都需要后续
RFC：它必须保持 atomic proof，并定义窗口之外的行为。在此之前，compaction 可以
重写字节，但必须携带完整 receipt index。

## 8. 默认本地模式不变，共享模式必须显式迁移

### 默认本地模式

- 现有 project registry、Markdown active state、run history、可选 task lease、
  status、quota 与 host behavior 保持不变。
- 安装 provider 不会启用 shared authority。
- 当前 event-store bridge 仍报告 Markdown 为真相源，不允许自动 promotion。

### Shared-authority mode

Shared mode 是按 Goal 显式选择。经 review 的实现必须：

1. 钉住 source registry、active state 与 privacy boundary；
2. 迁移期间停止或 fence 本地 writer；
3. 只把 scope 内的 coordination field 规范化为初始 aggregate；
4. 校验 todo/claim/lease/gate parity 与空 receipt index；
5. 记录 shared-mode declaration 及 authority endpoint/provider binding；
6. 让所有 P0 写都经过在线 authority；
7. 对已迁移字段，仅把 Markdown、local lease view、rollout row 与 status 渲染为
   projection。

Bootstrap 是受 fence 保护、发生在受控 shared write 之前的行政迁移，不是 P0 agent
command：它可以用选定的现有 todo 和空 receipt index 创建初始 aggregate。它的
source digest 与 mode declaration 必须耐久保存，让 restart 能区分 bootstrap 与尚未
初始化的 provider。

第一次 shared write 之前，迁移可以回滚到未改动的本地 source。发生第一次 shared
write 后，禁止自动 fallback 到本地 writer，否则会产生两个 authority。恢复必须
修复 authority，或执行另行 review 的 fenced export 与 mode transition。

Provider shadowing 与 read-only canary 可以采集 evidence，但两者都不改变真相源。
Promotion 必须显式发生，并遵循现有 fail-closed migration discipline。

## 9. 断网时怎么办，哪些数据不能出机器

Shared-mode authority 不可用时：

- cached projection 只有标记 stale 后才可读取；
- 不接受新的受控写入；
- 已授权的本地计算只能在现有 lease 与 effect boundary 内继续；
- 不自动 fallback 到本地文件写入。

本 RFC 不规定 wake latency 或 heartbeat topology。Delivery 可以在 Agent IM RFC 下用
pull、push 或 IM daemon，但消息已送达永远不能证明 coordination command 已提交。

Shared aggregate 与 receipt 可以包含紧凑的 public-safe 或显式 scoped private
metadata：stable id、无 credential 的 repository identity、精确 code revision、digest、
gate/dependency ref、claim/lease field 与按 privacy class 标注的 opaque pointer。不得
包含 credential、raw evidence、raw todo prose、transcript、raw log 或本地绝对路径。

## 10. 第一阶段怎么验收

全部检查均可由机器验证：

1. 两个 actor 从同一 provider generation claim 同一 todo，恰好一个得到
   `applied`；loser 得到 target-specific `conflict`，且没有 lease；winner 的 todo
   仍为 `open`，ownership 由 `claimed_by` 与 lease 表达；
2. 两个 actor 从同一 provider generation claim 同一 Goal 下两个独立 todo；在本
   reference 中二者 `write_scopes=[]`，且目标范围内的 authorization、dependency、
   gate 均未变化。第一次 CAS 的 loser 在 reload 与相关 precondition 重验后内部
   rebase，最终两者都得到 `applied`；Goal audit sequence、两个 todo revision 与
   两条 receipt 均只推进一次；
3. 以相同 operation id 与 digest 立即 replay，返回原始 receipt 且不改变状态；
4. 历史 A/B/A replay 在同一 deterministic provider fake 保留 aggregate、重建
   authority handle 后仍成立，并在 B 推进 head 后逐字段返回 A 的原始 receipt；
5. 相同 operation id 搭配不同 normalized digest 时被拒绝，state 与 receipt index
   均不改变；
6. Provider CAS 周围的 fault injection 永远不能暴露无 receipt 的 state 或无 state
   的 receipt；
7. ambiguous provider response 通过 reload receipt index reconcile：找到 receipt
   才恢复成功；同 generation 下缺失则 failed/unproved；generation 前进后缺失也必须
   重验并由一笔新的 successful CAS 才能得到 `applied`；
8. 对未知 todo、stale target/precondition、不符合 eligibility、dependency blocked 或 gate
   blocked 的 claim，拒绝且不创建 state 或 receipt；
9. 持续无关 provider contention 耗尽内部 retry budget 时返回 typed `failed`，不生成
   当前 operation 的 receipt，也不伪装成业务 conflict；
10. 保留的 receipt 经 reload fixture 后仍存在，不发生 receipt GC；
11. 测试分别处理 provider generation、authority revision 与 lease epoch；
12. privacy scan 不得发现 credential、raw body、transcript 或绝对路径；
13. 默认本地模式的行为不变，shared mode 永不 fallback 到未 fenced 的本地 writer。

配套 provider probe 是候选实现的 evidence，不构成弱化上述 normative check 的许可。
性能测量与具体部署 topology 被刻意设为 non-normative。

## 11. 分阶段交付

### 实施前置条件：先让本地文件模式经过同一协调合同

在接入 live NoKV 或其他远端 provider 之前，runtime 应先把当前 todo/lease 写路径中的
领域判断抽成 provider-neutral coordination core，并让一个 file-backed provider 通过
同一组 command、precondition、receipt 与 typed outcome 合同。这个重构应先以 shadow
方式对照当前 Markdown active state 和 task-lease 文件，资格化读写 parity、幂等、CAS
冲突、崩溃恢复与一键回退；只有经过单独 review 的 promotion 才能让 file aggregate
成为本地 canonical，并把 Markdown/lease 退为 projection。NoKV 随后复用同一 authority
与合同，只替换 `load` / `compare_and_put` provider。该前置条件不创建覆盖 registry、run
history、quota、scheduler 或 evidence 的通用存储抽象，这些账继续遵守第 3 节的 owner
边界。

#### Stage 1 Part 2 边界

这一切片只做行为保持的抽取：把现有 writer 已经执行的 todo lifecycle、task-lease
lifecycle 与 `handoff_mode` 规则收敛进纯决策 core。Markdown goal state 与
task-lease 文件仍是 canonical。此次抽取不会为目前没有 revision publisher 的 todo、
authorization、dependency 或 gate 域凭空制造 revision；也不会把今天相互分开的
claim 与 lease verb 偷换成上文的 atomic `claim_work`。后者属于未来的 shared
aggregate。

后续 provider 工作必须始终分开三层：

1. `DomainDecision` 只根据显式 coordination snapshot 与 command，纯函数式地给出
   apply / reject / no-change 判断。
2. Authority execution 及其 result 负责加锁、重验、提交该判断，并最终持有 durable
   semantic receipt。
3. Provider result 只报告 `loaded | missing | conflict | unavailable | failed` 等存储
   observation 与 opaque provider generation；它既不是领域判断，也不是 semantic
   receipt。

Stage 1 Part 2 不声称已经提供 durable semantic receipt 或 A/B/A replay；它们需要
Stage 2 的 aggregate 与 provider shadow。该 aggregate 必须把 `handoff_mode` 当作
真实且由 revision 覆盖的决策输入。Provider 合同绝不能把 `missing` 折叠成
`unavailable` 或 `failed`。`provider_generation`、`authority_revision` 与
`lease_epoch` 始终是三个独立版本域。同样，restore 可以保存 frozen bytes 与
lineage，却不会因此获得当前权威；把恢复状态晋升为 live authority head，必须经过
显式的 lineage 与 binding fence。

File-backed provider shadow 属于 Stage 2；这一切片尚未开始它。

完成续接（continuation）的持久化读回
（`durable_completion.py`：`read_persisted_todo_record` /
`project_durable_completion_outcome`）是一个 provider read point：它在完成写入之后、
settlement 之前重新读取已落盘的 lifecycle record（Markdown 优先，event projection
兜底）。落盘记录带有显式的 `completion_continuation`；done 记录缺少该字段、或该字段
与 successor / no-follow-up 字段矛盾时，seam 都 fail closed，因此持有完成状态的
provider 必须逐字节保存这个字段。一旦远端 provider 成为 canonical，这个 seam 翻转为
provider-first，且不改变下述 typed outcome 合同。

### P0：合同与 deterministic proof

- 本 ownership matrix 与显式 shared-mode boundary；
- 确定性的 `loopx_command_v0` normalization 与 request digest；
- 显式 bootstrapped todo 上的 `claim_work` authority transition；
- 单 head、state-plus-receipt CAS；
- target/precondition-scoped conflict 与无关 head 前进后的内部 CAS rebase；
- 同一 seam 后的 deterministic 与 NoKV provider candidate；
- 在所声明证据边界内的 A/B/A、identity mismatch、crash window、eligibility、
  privacy 与 no-GC 检查。

### 后续 runtime qualification 与需 review 的切片

- Lease renewal、显式 release、过期 lease reclaim 与 stale-fence writeback rejection；
  production shared mode 前必须完成这些能力；
- durable completion continuation projection
  （`successor | no_followup | active_goal`），带 fail-closed 矛盾规则
  （`no_followup` + successors、悬挂的 declared successor），并由 provider 以相同
  语义复现；
- atomic `complete_todo_with_successor` 与 accepted evidence pointer；
- transfer 与受限 delegated assignment；
- 经 Agent IM 的 delivery/wake integration；
- 独立 run-history synchronization 与 artifact storage；
- distributed quota reservation/accounting；
- provider promotion、authentication、service recovery、HA 与 multi-tenancy；
- `retain_all_v0` 之后的 receipt retention 或 segmentation。

## 12. 还需要 Owner 决定什么

1. 下一个 runtime slice 是否先闭合 renew/release/reclaim 与 stale fencing，还是与
   atomic complete-with-successor 一起 qualification？
2. 哪些紧凑的 project-registry authorization field 构成 versioned authority input，
   谁可以发布新的 authorization projection？
3. 第一次 shared-mode write 后，reviewed rollback/export procedure 是什么？
4. 哪个 provider 与 deployment 为第一次 bounded shared-mode canary 提供资格？
   Provider 选择不改变 authority contract。
5. Production 使用前，什么 retention 与 capacity policy 可以替代或落实
   `retain_all_v0`，且不丢失历史凭证？

---

## 附录 A：这版证据能证明什么

Reference provider 与 probe 位于
`examples/nokv-shadow-provider/`，并有
[配套证据文档](./shared-goal-authority-state-provider-v0-evidence.zh-CN.md)。本 PR 的
deterministic candidate 只证明 claim/receipt core：state 与 receipt 的 same-CAS、
并发 claim、A/B/A 原始 receipt 重放、request-digest mismatch、crash boundary 恢复，
以及版本域相互独立的示例。它不实现或认证 lease renewal/release/reclaim、
stale-fence writeback、production authorization-projection publisher、保留 receipt
的 compaction、默认模式 parity、shared-mode migration 或真实 NoKV restart/recovery。
因此，
`python3 examples/nokv-shadow-provider/probes.py contract` 通过并不表示上面的完整 P0
验收门通过。历史 latency 或 fault 结果只具有参考意义，不构成 durability、recovery、
HA 或 production qualification 声明。

## 附录 B：交接模式决策记录（2026-08-10）

本附录把 PR #2787 评审中已同意的方向落成文字，作为实施前置条件的一部分。
只改文档，不改任何运行时行为。

### 起因

用真实 CLI 验证时复现了一个事实：领任务的两本账可以各说各话。一个 agent 先拿到
某个 todo 的硬租约，另一个 agent 之后仍能软认领同一个 todo，两边都成功。分叉之后
的实际行为更关键：

- 后来的软认领会让先前的活租约直接失效：持约人续租、重新领取都被拒绝；
- 完成栅栏恰好在这种矛盾状态下自动失效：软认领方不带钥匙就能完成；
- 持约人反而完不成：授权检查先看软认领，租约凭证根本轮不到被检查。

也就是说，今天两本账一旦分叉，软认领方全胜，租约不单独构成执行权。第 4 节中
"执行权由 lease/fence 表示"描述的是目标合同，正文已随本修订改口。

### 决定

不做两本账之间的互相同步，改为每个 goal 声明一种交接模式（`handoff_mode`），
用模式把两种领法隔开。字段暂放在 goal 状态文件头部（front-matter），跟着文件
跨端走；共享模式上线后由共享权威托管。三个取值：

- 不填或 `legacy`：与今天完全一样，两种领法都开放。分叉的口子在此模式下仍然
  存在；这是有意保留的默认值，不是疏漏。
- `soft_claim`：该 goal 只用软认领。acquire/renew/transfer 被拒绝；release 与
  inspect 保留，用于清理和查看遗留租约。
- `hard_lease`：改动已有 todo 的认领关系必须持有它的活租约；所有把已有 todo
  置为 done 的转移（`complete` 与 `supersede`）都必须带钥匙；"矛盾态自动失效"
  改为响亮报错。新建 todo 时顺手指定认领人仍然允许——新 todo 不可能已有租约。
  有一个由 harness 自己持有的例外保住"带钥匙"这个不变量、又不逼 presenter 在
  人工等待期间一直持约：完成 user 角色的 `user_gate` todo 且没有显式租约凭证时，
  完成栅栏会在同一把 per-goal 租约锁下自己铸出钥匙、验证、并在提交后释放；
  已存在的时间有效租约永远不会被顶掉。

配套约定：

1. 默认 `legacy`，存量 goal 行为零变化；洞还在，实现 PR 必须明说。
2. 字段落点如上；registry 与租约文件都是单机的，只有 goal 状态文件跨端。
3. 跨端窗口：模式靠文件同步传播，两端可能短暂看到不同的值。现在只能收敛、
   不能消灭，如实声明；共享模式才能关死。
4. `hard_lease` 留一扇门：既有的委托授权（todo_lifecycle_authority，附说明
   理由）可以不持租约改认领，结果里带明确的越门标记，可审计。不新增任何
   绕过开关。
5. 切换模式要求静止：goal 内仍有未完成的认领或活租约时拒绝切换，并列出
   阻挡者。v0 不提供强制切换。

### 现状（2026-08-18）

门禁已经落地：状态文件前置的 `handoff_mode` 字段与上述 `legacy | soft_claim |
hard_lease` 语义、只允许静止态切换的 `loopx handoff-mode show|set`、以及带
`handoff_gate_overridden` 标记的委托授权门；上面的 user gate 自动铸钥匙作为后续
补充落地。`legacy` 仍是默认值，分叉洞按设计保留。门禁落地后发现的两扇侧门随本次
修订一并关上：`supersede` 与 `complete` 过同一道租约栅栏；强制重建状态
（`bootstrap --force`）保留已声明的模式而不是把它重置回 `legacy`。下一阶段，即
第 11 节协调合同后面的 file-backed provider shadow，尚未开始。

### 与分阶段交付的关系

对应 #2787 评审结论中的五阶段计划：先在 characterization 阶段把今天的真实行为
（含上面三条分叉事实）做成用例入册；门禁本身是一次显式声明的行为变更，作为
独立 PR 在 file provider shadow 之前落地，避免分叉数据污染 shadow 对账基线；
本地 canonical promotion 把 claim 与 lease 收进同一本账后，这类分叉从结构上
不再可能，门禁自然被吸收。读侧与卫生修复（status 显示真实租约、完成后销掉已
验证的租约）不涉及判断语义，已先行提交。

characterization 阶段的负向用例在原清单上补充：软认领盖掉活租约、完成栅栏在
矛盾态失效、授权检查先于租约栅栏、尚未设防的认领变更入口、租约获取读取投影
与状态文件锁之间的窗口。
