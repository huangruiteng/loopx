# DeepSWE Five-Arm Benchmark Harness (v1)

How we evaluate five agent configurations ("arms") on the DeepSWE task set
(113 SWE tasks). Runner/methodology code only — no API/gateway config, no trajectories.
Run against LoopX revision `2cef51d` (this branch's base).

## The five arms
| Arm | Transport | Goal / LoopX | Continuation |
|---|---|---|---|
| `plain` | codex app-server | no Goal, no LoopX | single pass |
| `goal` | codex app-server | native Codex Goal | app-server continues while Goal active |
| `heartbeat` | `codex exec` (fresh, then `resume`) | LoopX Goal/Todo | recurring supervisor wakes |
| `codex-cli` | `codex exec` (CLI) | LoopX control plane | external `loopx turn run-once --host codex-cli`, multi-segment |
| `ssh-goal` | codex app-server | LoopX + native Goal (official full path) | same thread/Goal; LoopX clears blocked + restarts turn |

- Arm dispatch: `pier_cn.py` (`MR_CODEX_ARM=plain|goal|loopx-native|loopx-native-codex-cli|loopx-native-heartbeat`)
- Arm classes: `goal_codex.py` (`PlainAppServerCodex`, `GoalCodex`, `LoopxCodex`)
- Runners: `loopx_wen_native_runner.py` (ssh-goal), `loopx_codex_cli_runner.py` (codex-cli),
  `loopx_heartbeat_supervisor.py` (heartbeat)
- Delivery gate: `workspace_delivery.py` (recover agent work from linked git worktrees into
  `/app` so the collected patch is non-empty)
- Admission: `preflight_loopx_rerun.py` (pins LoopX revision, delivery self-test)

## Validity (strict)
`exception_info == null`, independent `verifier/reward.json` present & consistent, task
checksum matches, and a **non-empty committed patch** exists. Goal/Todo state is lifecycle
evidence only; the independent verifier is the sole correctness authority. `partial > 0`
alone does NOT count as valid delivery.

## Results — v1 (113 tasks, per-task best valid)
| Rank | Arm | Solved | Solve rate | Partial | F2P | P2P |
|---|---|---:|---:|---:|---:|---:|
| 1 | heartbeat | 70/113 | 61.9% | 0.9739 | 0.886 | 0.993 |
| 2 | codex-cli | 66/113 | 58.4% | 0.9546 | 0.884 | 0.996 |
| 3 | goal | 60/113 | 53.1% | 0.9620 | 0.868 | 0.997 |
| 4 | ssh-goal | 58/113 | 51.3% | 0.9654 | 0.883 | 0.997 |
| 5 | plain | 54/113 | 47.8% | 0.9206 | 0.745 | 0.997 |

P2P (regression) ≈ 1.0 for all arms; spread is driven by F2P and solve rate.
LoopX arms (heartbeat/codex-cli) and goal outperform the plain baseline.

> Model & gateway endpoints are configured via `MR_*` env vars (not included).
> Internal hosts/paths replaced with placeholders (`127.0.0.1`, `<REPO_ROOT>`, `<HOME>`).
> v2 (latest LoopX main) evaluation is in progress and will be published separately.
