# Benchmark Rerun Review 2026-06-16

Source boundary: compact benchmark-run ledger, benchmark-case-analysis, active
LoopX state, and public process/observable handles only. This review did
not read raw logs, raw task text, raw trajectories, verifier output tails,
credentials, upload paths, or leaderboard material.

## Current Comparison Rule

Primary SkillsBench comparison now means:

- baseline route: `codex-acp-blind-loop-baseline`
- treatment route: `loopx-blind-loop-treatment`
- no Codex `/goal` mode in either arm
- no official reward, pass/fail, verifier error, or verifier output forwarded
  to the agent during the loop
- max rounds: 5
- stop an arm immediately after official reward reaches `1.0`
- record offline `round_rewards` and `first_success_round`

Older reward-feedback positives remain useful ablation evidence, but they are
not primary no-reward LoopX uplift evidence.

## Immediate Decisions

| Rerun class | Cases | Decision |
| --- | --- | --- |
| Do not rerun now: baseline solved in round 1 | `ada-bathroom-plan-repair`, `organize-messy-files`, `citation-check`, `3d-scan-calc`, `bike-rebalance`, `travel-planning` | Keep as success/non-regression controls. Re-run treatment only after a prompt or stop-policy change that could regress easy cases. |
| Do not rerun until setup route changes | `dapt-intrusion-detection` | The max-5 blind-loop baseline preflight stopped before agent rounds with `skillsbench_docker_apt_setup_risk_preflight_blocked`; `case_attempt_budget_should_count=false`. Treat the old reward-feedback uplift as unresolved, not contradicted, until the apt setup route is repaired or a non-apt-risk replacement is selected. |
| Do not launch matching treatment: baseline solved in round 1 | `suricata-custom-exfil` | After the runtime-tools/package-manager repair, the no-upload `codex-acp-blind-loop-baseline` retry reached official scoring and passed with official score `1.0` in round 1. Treat this as setup-route repair validation plus a baseline-solved control, not a treatment priority. |
| Do not rerun until setup/runner blocker changes | `setup-fuzzing-py`, `adaptive-cruise-control`, `fix-build-agentops` | Current evidence is setup/apt/compose failure before solver scoring. Repeat only after a materially different apt/setup repair or a fail-fast preflight route. |
| Do not rerun now: clean max-5 blind-loop positive | `paratransit-routing` | Baseline exhausted five blinded rounds at `0.0`; treatment reached official `1.0` in round 1 with stop-at-1 and no reward/verifier feedback. Keep as the first primary blind-loop positive control. |
| Max-5 rerun complete: do not duplicate | `debug-trl-grpo` | Baseline held official `0.25` across all five blinded rounds. Matching treatment closed at official `0.0`, with round rewards `1:0.25,2:0.25,3:0,4:0,5:0`. This strengthens the continuation-risk regression diagnosis; repeat only after a concrete prompt or stop/stabilize policy change. |
| Max-5 rerun complete: keep as neutral guard | `llm-prefix-cache-replay`, `azure-bgp-oscillation-route-leak` | Both now have max-5 blind-loop evidence and stayed neutral at `0.0/0.0`. Keep them as no-uplift guards; do not spend another same-policy repeat. |
| Do not rerun now: clean two-round neutral guards | `software-dependency-audit`, `react-performance-debugging`, `civ6-adjacency-optimizer`, `manufacturing-codebook-normalization`, `pddl-airport-planning` | These are useful no-uplift controls. Promote one to max-5 only after a concrete prompt/round-policy change needs a representative neutral guard. |
| Terminal-Bench: keep historical/control-plane evidence, avoid broad rerun | `multi-source-data-merger`, `nginx-request-logging`, `large-scale-text-editing`, `build-cython-ext`, `financial-document-processor`, `git-multibranch`, and other pass/resolved rows | Many rows are historical runner-repair evidence or baseline-solved controls under old Terminal-Bench routes. Re-run only if selected as a fresh Terminal-Bench pilot with a current comparable route. |
| Terminal-Bench: repair/attribute before rerun | `make-doom-for-mips`, `pytorch-model-recovery`, `headless-terminal`, `mteb-retrieve` | Need timeout phase attribution, exception hypothesis, verifier attribution, or setup-probe interpretation before another same-case repeat. |

## Recommended Near-Term Rerun Order

1. Treat `debug-trl-grpo` max-5 as closed regression evidence. It did not
   improve with more blind rounds: baseline stayed `0.25` across all five
   rounds, while treatment fell to `0.0` after round 2.
2. Treat `llm-prefix-cache-replay` max-5 as closed neutral evidence. It stayed
   `0.0/0.0` for five blinded rounds, so it should no longer be the first rerun
   candidate.
3. Do not keep retrying `dapt-intrusion-detection` under the unchanged route:
   the max-5 baseline now has a compact pre-agent setup blocker,
   `skillsbench_docker_apt_setup_risk_preflight_blocked`, with no raw task,
   log, verifier, or trajectory material read.
4. Treat `suricata-custom-exfil` as setup-route repair validated and now
   baseline-solved. The retry after the runtime-tools/package-manager patch
   reached official scoring, passed with official score `1.0`, and recorded
   `first_success_round=1`. Do not launch the matching treatment because a
   first-round baseline pass is not a current uplift candidate.
5. Keep neutral and success controls out of the default rerun queue unless the
   prompt or stop policy changes.

## Stable Takeaways

- The old SkillsBench uplift story is reward-feedback evidence, not primary
  no-reward LoopX evidence. `llm-prefix-cache-replay` has now failed the
  max-5 blind-loop recheck at `0.0/0.0`; `dapt-intrusion-detection` did not
  reach agent rounds under the max-5 route because the fail-fast preflight
  classified an apt setup risk. It remains unresolved rather than usable for a
  primary uplift claim.
- Interaction count alone is not the answer. `debug-trl-grpo` showed that
  prompt/scope framing can regress partial credit under the same two-round
  budget, while baseline-safe framing recovered to baseline; the max-5 rerun
  strengthened that conclusion because baseline stayed at `0.25` for five
  rounds while treatment degraded from early partial credit to `0.0`.
- Baseline-solved cases are valuable, but as non-regression controls, not
  uplift candidates.
- Setup-blocked cases should not be repeated as full benchmark attempts until
  the setup route changes. The `suricata-custom-exfil` retry demonstrates the
  current runtime-tools/package-manager repair can convert a prior pre-agent
  setup blocker into a real official result.
- No-apt task selection is necessary but not sufficient. `tictoc-unnecessary-
  abort-detection` is no-apt but already has a compact product-mode compose
  setup blocker, so it is not the first replacement. `suricata-custom-exfil`
  then proved the same point in the opposite direction: no-apt preflight passed,
  but the real baseline still failed in Docker compose before agent rounds. The
  next useful work is setup-route repair/classification, not more same-route
  treatment launches.
- Runner stdout/stderr must stay private during real benchmark launches. The
  SkillsBench bridge now redirects BenchFlow/Docker output into a private job
  log and exposes only compact capture metadata, so future case analysis can
  keep raw logs out of heartbeat-visible output and public review artifacts.
- Terminal-Bench rows still matter as runner-hardening and historical
  route-canary evidence, but the immediate max-5 rerun program should stay on
  SkillsBench unless Terminal-Bench is explicitly selected as the next fresh
  pilot.

## Current Minimal Rerun Queue

| Priority | Case | Why | Stop / do not run when |
| --- | --- | --- | --- |
| P1 | Benchmark queue re-rank after setup-route validation | `suricata-custom-exfil` now validates the runtime-tools/package-manager repair, but it solved as baseline official `1.0` in round 1, so it is not a useful treatment priority. | Do not run the matching `suricata` treatment. Pick the next lane only if it can test LoopX value under the current max-5 no-reward protocol without known setup blockers. |
| P2 / after policy change | one neutral guard, preferably `software-dependency-audit` or `react-performance-debugging` | Useful only to test whether a new prompt/round policy damages clean `0.0/0.0` controls. | Do not run under the unchanged current policy; `azure-bgp-oscillation-route-leak` already provides one max-5 neutral guard. |
| P2 / after policy change | one solved guard from `ada-bathroom-plan-repair`, `organize-messy-files`, `citation-check`, `3d-scan-calc`, `bike-rebalance` | Useful only to test whether treatment damages easy first-round success. | Do not run under the unchanged current policy; these are already first-round success/non-regression assets. |

## Setup-Route Repair Update

2026-06-16T23:49+08: the SkillsBench ACP runtime-tools patch was hardened
without reading raw task text, raw logs, raw trajectories, verifier output, or
credentials. The dnf/microdnf/yum branches now avoid force-installing `curl`
when `curl-minimal` already provides the command, fall back through
`curl-minimal` then `curl` only when needed, and require final `curl`, `tar`,
and `xz` executable checks. The same package-manager behavior is applied to
the image-build-time Dockerfile runtime-tools patch.

Validated surfaces: `py_compile`, `skillsbench-benchmark-run-smoke`,
`benchmark-run-ledger-smoke`, `benchmark-case-analysis-smoke`,
`loopx check`, and `git diff --check`.

Next validation is exactly one no-upload `suricata-custom-exfil` baseline
retry/probe under private runner-output capture. Do not launch the matching
treatment until that baseline reaches agent rounds or official scoring.

## Setup-Route Probe Result

2026-06-17T00:04+08: the exactly-one no-upload `suricata-custom-exfil`
`codex-acp-blind-loop-baseline` retry completed with official score `1.0`,
`first_success_round=1`, runner launch preflight `passed`, and compact result
history classification `skillsbench_codex_acp_blind_loop_baseline_result_v0`.
Runner stdout/stderr stayed under private capture; the public record uses only
compact result, controller counters, and ledger metadata. This closes the
setup-route validation batch and downgrades `suricata-custom-exfil` to a
baseline-solved control rather than a treatment target.
