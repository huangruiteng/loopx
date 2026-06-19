# Goal Harness Self-Repair Patterns

Use this file as a compact diagnosis table. Add a row whenever a real incident
teaches a reusable control-plane lesson.

| Pattern | Symptoms | Evidence To Read | Likely Root | Durable Repair |
| --- | --- | --- | --- | --- |
| `state_projection_gap` | `quota should-run` says `should_run=true` or `must_attempt=true`, but user and agent open todo counts are both zero while `Next Action` still contains executable work. | quota payload, active state `## Agent Todo`, `## User Todo`, `Next Action`, `refresh-state` warnings. | Active state prose has drifted away from machine todo projection. | Expand executable prose into `- [ ]` agent todos, add refresh-state warning/smoke if projection missed it. |
| `user_todo_projection_gap` | `interaction_contract.user_channel.action_required=true` or open user todos exist, but heartbeat/final message only says "owner gate" or does not name the concrete decision. | quota payload `interaction_contract`, `user_todo_summary`, active state user todos, recent final messages. | User-channel projection or agent final-response rule is too vague. | Fix prompt/projection so required user todo/question is surfaced; only say "具体 user todo 未投影" when action is required but absent. |
| `normal_no_user_todo_misflagged` | `action_required=false` and user open count is zero, but the agent reports a state projection fault. | quota payload and user todo summary. | Rule over-applied the "todo not projected" fallback. | Allow "无用户待办/无需通知"; update heartbeat/prompt smoke if needed. |
| `blocked_priority_fallback_hidden` | A core P0 path is user-gated, safe P1/P2 fallback runs, but the user is not told what blocked the P0 path. | quota `safe_bypass_allowed`, active priority stack, final heartbeat text. | Fallback execution hid the higher-priority blocked item. | Report concrete blocker plus fallback progress; expose `blocked_priority_fallback` in state/payload if missing. |
| `boundary_projection_gap` | `recommended_action` asks for work in a scope that is absent from `goal_boundary.write_scope`, such as runner edits blocked by repo-only scope. | quota `recommended_action`, `goal_boundary.write_scope`, authority/owner decision records. | Checkpointed owner decision did not project into current write boundary. | Repair boundary projection or ask controller/user; do not consume repo-only handoff steps that cannot touch the needed scope. |
| `stale_recommended_action` | The agent repeats "launch or preflight" after the active state or evidence already narrowed the next action. | latest active state, quota payload timestamp/content, recent history rows. | Recommended action was not regenerated from the newest state. | Refresh state, update recommender/projection tests, and write an exact next action. |
| `tiny_turn_under_delivery` | Many heartbeats make only one small doc/prose edit despite quota permitting a coherent batch. | recent history durations, active priority stack, user feedback, todo completion rate. | Agent optimized for avoiding mistakes rather than delivering a bounded batch. | Run steering audit, choose a larger verifiable batch, and record why it remains within boundary. Consider cadence/budget policy updates if repeated. |
| `todo_succession_gap` | A non-trivial feature todo is marked done after PR/smoke success, but rollout, product-path audit, docs, telemetry, benchmark proof, or operator-decision follow-up is only mentioned in prose or not recorded at all. | completed todo note/evidence, recent PR/run history, active `Agent Todo`, active `Next Action`, related design docs. | Agent treated an implementation slice as feature completion, or Goal Harness lacked a reminder to create the successor todo. | Keep the lifecycle simple: do not add many feature states. Complete the old todo and create the next concrete agent/user todo with `--next-agent-todo`/`todo add`, or record a compact no-follow-up rationale. |
| `plan_todo_writeback_gap` | The agent explains a route change, top-20 todo list, P0/P1 plan, or deprecation policy to the user, but the active Goal Harness todos / Next Action / refresh-state payload do not contain the same commitments. | latest user-facing plan, quota `todo_write_hint`, active `Agent Todo`, `User Todo`, `Next Action`, recent refresh-state runs. | Agent used chat as memory after understanding the plan; Goal Harness prompt/skill did not make plan publication a writeback trigger. | Treat user-facing Goal Harness plans as writeback triggers: add/update concrete todos or refresh state before final, or explicitly mark the plan speculative/no-writeback with rationale. Add skill/prompt wording when this recurs. |
| `benchmark_product_path_mismatch` | Treatment uses a surrogate state file or prompt route that differs from the real Codex App + Goal Harness path, making uplift attribution unstable. | benchmark runner inputs, per-call Codex CLI transcript, state file paths, installed skill/prompt snapshot. | Benchmark route drifted from product route. | Add posthoc parity checks for state path, CLI interaction trace, heartbeat/state/skill inputs, and protocol version before claiming result. |
| `user_reward_lesson_projection_gap` | The user explicitly corrects a high-value product route, priority, or operating rule, but later turns follow an older todo/recommended_action as if the correction never happened. | recent user correction, latest quota/status, active-state `Next Action`, open todos, recent run history, interaction pattern catalog. | The correction stayed in chat/model belief instead of becoming a durable human-reward/operating-lesson constraint, successor todo, or state projection. | Promote the correction into active goal state and pattern catalog; add/update an agent todo for runtime projection; refresh state so `quota should-run` selects the corrected rule before continuing. |
| `reward_feedback_leak` | Later benchmark rounds receive verifier tail, pass/fail, or reward details that one arm should not see. | benchmark prompt/continuation logs, compact ledger, verifier wrapper. | Evaluation loop leaked reward signal. | Record per-round reward privately for metrics, but do not feed it to agents unless the experiment explicitly studies feedback. |
| `commit_hygiene_drift` | Broad commit includes temporary smokes, raw logs, local state, or unrelated docs. | `git status`, `git diff --stat`, `git ls-files --others --exclude-standard`, AGENTS.md. | Worktree was staged by chronology rather than reviewer logic. | Use explicit pathspecs, split commits, keep only durable smokes, and update AGENTS/skill if the failure mode recurs. |
| `docs_surface_sprawl` | Root docs become hard for contributors to navigate; research/drafts/history compete with stable contracts. | `docs/README.md`, root docs count, docs governance smoke. | Documentation lacks audience and lifecycle ownership. | Move archive/outreach/research/reference material into indexed subdirs and keep new docs linked from an index. |

## Minimal Evidence Packet

For most repairs, capture:

```text
goal_id:
observed_surprise:
quota_state:
interaction_contract:
user_todo_open_count:
agent_todo_open_count:
recommended_action:
goal_boundary_write_scope:
active_state_next_action:
recent_history_summary:
responsible_layer:
repair:
validation:
```

Keep this packet compact and public-safe. Store only summaries in public docs;
raw logs and private traces stay in ignored local paths.
