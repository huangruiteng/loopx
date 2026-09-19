# RFC: Optional Semantic Assistance for LoopX — TypeSafe/Jev Directions, Priorities and Graceful Degradation (v0)

- **RFC status:** Draft, proposed for maintainer review; not accepted.
- **Delivery maturity:** Proposal; documentation only. No Jev runtime integration or model qualification is delivered.
- **Created / Last normative revision:** 2026-09-19.
- **Implementation baseline:** `9f1916960306b3650d795895b89f331eeae2516e`; relevant owners audited in source, with the official-main delta through `cc8e28d8b58a9b15e928d7e2cee16097172567d1` checked separately. Not a whole-tree/runtime certification.
- **Authors / owners:** Existing domain owners retain each direction. A cross-direction maintainer steward is to be named; this is not a new runtime authority.
- **Language mirror:** [中文版](optional-semantic-assistance-jev-v0.zh-CN.md)
- **Related contracts:** [overall roadmap](loopx-overall-roadmap-v0.md), [Decision Context](../../reference/protocols/decision-context-architecture-v0.md), [Goal acceptance](../../reference/goal-acceptance-observations.md), and the domain map in section 4. Existing domain RFCs retain authority.

## Document map and maintenance contract

Sections 1–10 define proposed boundaries, directions and acceptance; Section 11 defines bounded delivery; Section 12 lists open decisions. Appendices retain history and evidence. Section 4 separates existing sources from recommendations. D1–D6 are document references, not global enums, task states or a requirement to open six PRs. The Chinese document is a semantic mirror; keep both normative versions synchronized. A direction's rank grants no execution, data-egress or promotion approval.

New commands, fields and modules are proposals unless explicitly identified as existing. Admission of one direction does not admit the other five. Priorities are not measured accuracy, benefit or delivery-date commitments.

## 1. Decision summary

Discuss six LoopX/Jev integration directions, ordered by product value, fit with existing ownership, evidence readiness, error consequences, cost and exitability. Select one named direction for an end-to-end first slice; do not build a generic intelligent controller first.

**Necessary LoopX workflows must not require a new Jev account or API key.** Jev is optional assistance, not a mandatory judge. Missing or disabled configuration preserves existing behavior. When an explicitly requested enhancement lacks credentials, availability, budget or usable results, resume the scenario's defined baseline and explicitly disclose the unperformed model judgment.

Three boundaries always apply:

1. Degrade optional assistance, never identity, permission, source, acceptance, settlement, lease or required-review obligations.
2. A model-free path does not gain equivalent natural-language understanding. Preserve actual capabilities and disclose omissions; do not fabricate probabilities or a clean judgment.
3. A key or installed skill is not activation, private-source permission or upload consent. Do not silently call another cloud model or download a local model when Jev is unavailable.

This RFC does not authorize automatic replan, pause, redirect, PR merge, Goal mutation, gate discharge or bypass of a configured verifier. D4/D5/D6 adoption that changes worker context, ordering or action inputs requires separate admission under existing influence and authority policies.

## 2. Problem, goals and invariants

Users need long-running work to remain tied to outcomes despite valid fields and apparent activity. Developers need to find reusable concepts, reviewers need relevant evidence, and users need discoverable materials and skills. Jev may assist with unstructured meanings, but must not become another prerequisite for installation, ordinary execution or CI.

Success is not six working API calls. It is observable incremental value in one real scenario, with a useful, honest baseline when no key is available.

### Invariants

- **I1 — Core authority is unchanged.** Fallback or high confidence cannot admit work previously refused. The model cannot veto a deterministic protection.
- **I2 — Default-off has no new effects.** Do not read credentials, create a client, call the network, create files or attach worker hooks. Existing ordinary command output remains unchanged.
- **I3 — The baseline is real.** Each direction states its model-free outputs, absent capability and decision owner. Do not invent a local detector merely to claim graceful degradation.
- **I4 — Unknown remains visible.** Not run, service failure, abstention, low certainty and stale basis are distinct; none proves no drift or a passed review.
- **I5 — Facts, inference and actions stay separate.** Exit codes, revisions and actual artifact reads remain observations; model output is advice; existing authority determines action.
- **I6 — Reading and upload have separate admission.** Goal/Agent/project and source permission precede destination, data-class, budget and retention approval.
- **I7 — Domain ownership remains singular.** D1 does not absorb D2/D3 policy. An inference adapter is not a source reader, context retriever or competing evaluator.
- **I8 — Bounded and removable.** No implicit retries, unbounded queues or silent model switching. Disable/uninstall preserves original workflow semantics.
- **I9 — Reuse without speculative frameworks.** Do not build a provider registry or task DSL before a second real scenario demonstrates a shared transport need.
- **I10 — Validation credit is separate.** Missing keys may skip live tests; they cannot make model qualification pass. Delivery and promotion are independent.

## 3. Six directions and priorities

### 3.1 Ordered portfolio

| Rank | Direction | Priority | Incremental Jev role | Useful baseline without Jev | Maximum first-stage influence |
|---|---|---|---|---|---|
| D1 | Progress and goal-deviation observation | P1, highest core-product value | Interpret alignment and material novelty from the goal, artifacts and bounded history | Existing typed repeat, frontier, writeback, acceptance and operator inspection; prose-level drift is not assessed | Operator-only judgment, no execution change |
| D2 | New-term and owner-reuse advice | P1, low-risk developer entry | Compare locally discovered candidates with existing contract meanings | Bounded no-npm local probe, which still needs its own delivery, plus owner hints and human decisions; full-tree checks retained | Advice only; no registration, merge or candidate suppression |
| D3 | PR outcome/evidence comparison | P2, after D1/D2 | Compare issue outcome, diff and independent evidence | Existing exact-head review, problem_context obligations, tests and human/existing-Agent review | Additional review hints, no approval |
| D4 | Material, evidence and recall reranking | P2 | Judge semantic relevance among authorized candidates | Each caller's original ordering, exact reads, freshness and coverage requirements | Separate operator ranking view; no worker-input change |
| D5 | Skill/capability suggestion | P2, after D4 | Select a few relevant allowed and available candidates, or none | Existing catalog, host discovery, explicit choice and permission checks | No install, activation or execution |
| D6 | Replan-candidate comparison and historical repetition risk | P3, research and later-stage | Compare already legal alternatives for alignment, repetition and missing evidence | Existing planner, ordering, typed obligations, recovery and human decisions | Operator comparison, no plan commit or new obligation |

This is a value/risk recommendation, not demonstrated model quality. D1 is the default first product slice. When its acceptance/evidence basis is not ready, explicitly select D2 as a lower-risk complete pilot instead; do not promote canonical authority or invent Goal intent to start Jev work. Neither D1 nor D2 is a universal prerequisite for the other.

### 3.2 D1: Progress and goal deviation

**Owner:** Proposed Decision Context scenario. Existing progress, Replan and acceptance retain authority. Initially evaluate only a local same-Goal/same-Agent completed-work window with an effective owner-authorized acceptance contract.

**Input:** Objective, non-goals, criteria, task bindings and revision; host-read before/after artifacts and validation readback; ordered deduplicated Turns; separately labeled author claims. Never infer current intent from worker claims, filenames or opaque IDs. Exact reading does not prove semantic truth.

**Two independent questions:** Alignment (direct progress, required prerequisite, off contract, insufficient evidence) and novelty (material new evidence, no material new evidence, insufficient evidence). Results are local/private and do not enter ProgressResultClass or EffectiveAction.

**Degradation:** Show available existing detections, validation and missing sources; model judgment is null. Absence of repeated fingerprints does not establish absence of task drift. A missing canonical basis cannot fall back to guessed Markdown intent. Independent gates remain effective.

**Acceptance:** Real progress, necessary tests/research, negative experiments, legitimate waiting, ID-only changes, opposite self-descriptions, authorized goal changes, same-Turn retries, missing evidence and injection controls. Compare with the full original workflow, not one function. No-key execution preserves original decisions and rejections.

### 3.3 D2: Vocabulary and owner reuse

**Owner:** Semantic developer tooling and the local probe proposed by #4743, not a D1 runtime subflow. The probe is separate delivery, not assumed available from an issue description.

**Input:** Explicit old/new diff mode, carriers and new values, symbol/slot, bounded owner descriptions and candidate contracts. Explicitly named untracked source files are supported without sweeping private ignored files. Discover first, suggest relations second; a new concept with no registry resemblance must still appear.

**Jev:** Suggest a supplied owner worth investigating, no suitable candidate, or insufficient evidence. Do not automatically write admitted_as or infer equivalence from equal literal sets.

**Degradation:** Preserve all local candidates, structural duplicate/overlap hints and disposition questions. A justification or reuse_existing label cannot suppress an unresolved candidate. Existing semantic-review obligations remain.

**Acceptance:** New unmatched state sets, identical values with different meanings, actual owner imports versus justification-only duplication, prose edits, unsupported TS, no npm and no key. Measure only the incremental model advice, not baseline discovery as model recall.

### 3.4 D3: PR delivery evidence

**Owner:** Existing pull-request-review exact-head workflow and evidence contract.

**Input:** Outcome requirements, scoped diff, real tests/artifact readback, author claims and unverified items bound to the same base/head. Exact-read references first; equal aggregates do not establish per-site equivalence.

**Jev:** Flag possible claim/evidence mismatch, prerequisite-only delivery and areas needing deeper review. It is not a reviewer, verifier or merge gate.

**Degradation:** Continue the existing queue, code reading, problem_context, independent validation and human/existing-Agent workflow. Missing mandatory review continues to prevent readiness; a missing key never implies APPROVE, not_applicable or relaxed evidence.

**Acceptance:** Valid fixes, serializer/wrapper-only changes, justified prerequisites, identical facts with different marketing, changed head and missing evidence. Offline Jev cannot change review completion conditions.

### 3.5 D4: Evidence/material reranking

**Owner:** The actual Decision Context, Material Lifecycle or Turn Recall caller, with independent adoption review; do not merge their registries.

**Input:** Bounded, permission-filtered candidates, query, revisions, freshness and mandatory/P0 flags. The model cannot follow URIs or widen source scope.

**Jev:** Comparable per-candidate relevance judgments; keep confidence distinct from relevance. Retain the full candidate set and baseline ordering. Initially provide a separate operator view.

**Degradation:** Use original ordering and mandatory-read rules. Partial score failures, timeout or incomparable scores revert the entire ranking instead of deleting unscored items as zero. Do not hide P0 sources, conflicts, missing coverage or staleness.

**Acceptance:** Separate candidate recall from reranking quality. High relevance cannot make an unauthorized or stale claim trusted. Model-free ordering and identity must match baseline. Automatic worker-context changes require a new treatment and data/budget approval.

### 3.6 D5: Skill/capability suggestion

**Owner:** Existing capability catalog, host discovery and project_skill_delivery installation contract.

**Input:** Task needs and descriptions of allowed, compatible, available candidates. Installed, discoverable, enabled and authorized are separate states.

**Jev:** Return bounded supplied candidate IDs or none. Recommendation is not installation or execution; no arbitrary imports/commands.

**Degradation:** Preserve existing discovery, default routing and explicit selection. Missing Jev cannot make installed skills disappear or create a download action.

**Acceptance:** Irrelevant/none-match suggestions, disabled/unready/unauthorized candidates, unknown returned IDs and changed profiles. Existing skill listing/use continues under original permissions. Do not upload all skill contents merely to claim token savings.

### 3.7 D6: Replan alternatives

**Owner:** Existing Replan/Explore/planner. Decision Context supplies evidence only for a demonstrated caller, not duplicate candidate-generation policy.

**Input:** Existing bounded alternatives that satisfy original authority and preconditions, current goal, attributable historical attempts and evidence. Unavailable recall makes history incomplete, not empty.

**Jev:** Compare alignment, possible repetition and evidence gaps. Missing material cannot imply never attempted. Probabilities confer no execution authority.

**Degradation:** Continue original planner, recovery, obligations and human path. Required new Replan evidence is not waived because Jev is unavailable, and missing Jev alone cannot create a new gate.

**Acceptance:** Existing refusals preserved; renamed old attempts, genuinely new probes, incomplete history, same-Agent scope and changed goals. Diagnostic value and intervention value are separate. Automatic selection, scheduler changes, pause/redirect/replan need a separate named L3 decision, not an implicit deliverable.

## 4. Existing system and RFC relationships

| Existing boundary | Reusable capability | Authority not replaced |
|---|---|---|
| Decision Context | Default-off, source reads, revisions, evidence/proposal separation, provider fail-open | Review settlement, no_change, cursors, outcomes |
| Progress/Replan | Exact typed repeat, frontier/writeback policy | Canonical progress, obligation discharge, spend |
| Goal acceptance/Direction Baseline | Existing acceptance for D1; material-direction linkage stays independent | No invented full Goal-intent revision or read receipt |
| Semantic RFC/#4447/#4743 | Owners, registration, checks and local authoring candidates | No replacement of F1–F6 or expanded tracker closure |
| PR Review | Exact-head queue, evidence and explicit authority | No inferred evidence truth, approval or merge |
| Reliability Diagnostics | Existing L1/L2/L3 distinctions | Original zero-egress/no-raw-content L1; cloud evaluator is not that collector |
| Post-writeback/Effect/TS migration | Named intent outside primary transaction and existing ownership | No network inside writeback locks or duplicated TS policy |
| Skill delivery/extensions | Explicit discovery, install, enablement, doctor and uninstall | Suggestions grant no domain authority or implicit install |

### 4.1 Source-grounded placement and dependency map

| Direction / concern | Existing source or RFC | Observed boundary and implementation consequence |
| --- | --- | --- |
| D1 evidence | [Decision Context runtime](../../../loopx/capabilities/decision_context/runtime.py), [sources](../../../loopx/capabilities/decision_context/sources.py), [profile](../../../loopx/capabilities/decision_context/profile.py) | Source acquisition, exact reads and scoped activation exist. `context_provider` retrieves context; it is not a semantic inference interface. Extend this owner with an explicit assessment path, preserving source review/cursor settlement. |
| D1 goal basis | [acceptance authority](../../../loopx/control_plane/goals/acceptance_authority.ts), [acceptance contract](../../../loopx/control_plane/goals/acceptance_contract.ts), [Direction Baseline RFC](goal-direction-baseline-v0.md), [Alignment RFC](shared-goal-alignment-and-governed-amendment-v0.md) | Canonical acceptance holds objective, non-goals, criteria and task bindings. Direction Baseline is still a proposal, and this RFC cannot manufacture full Goal-intent revision authority. Read an already effective acceptance revision; do not promote a provider to obtain one. |
| D1 existing detector | [progress observation](../../../loopx/control_plane/work_items/progress_observation.py) | `typed_progress_repeat_trigger` compares consecutive valid equivalent typed rows, deduplicates attributable Turns, and triggers for unchanged/blocked. It is not a prose drift detector. The newer official-main Replan changes preserve this limitation and move additional discharge semantics to TypeScript. |
| D2 authoring | [Semantic Vocabulary RFC](semantic-vocabulary-convergence-v0.md), [inventory script](../../../scripts/generate_semantic_inventory.py), [inventory](../../../loopx/semantics/inventory.py), [#4743](https://github.com/huangruiteng/loopx/issues/4743) | Full-tree inventory and advisory ranking exist; the script calls `build_inventory` before reporting. The bounded diff/no-npm authoring probe remains a design request. Build that real baseline before calling its optional advice delivered. No automatic issue closure or approval of its suggested registry fields follows here. |
| D3 review | [review contract](../../../loopx/capabilities/pr_review_queue/review_contract.py), [result check](../../../loopx/capabilities/pr_review_queue/result_check.py), [Intelligent Review RFC](intelligent-review-presentation-surfaces-v0.md) | PR evidence review belongs to `pr_review_queue`. Intelligent Review supplies typed presentation, a possible later consumer only; model advice remains a later optional stage. `check_review_result` checks declared evidence consistency, not its truth. Jev cannot replace exact-head review. |
| D4 retrieval | [Decision Context](../../../loopx/capabilities/decision_context/README.md), [Reward Memory](../../../loopx/capabilities/reward_memory/README.md), [memory utility RFC](post-outcome-memory-utility-attribution-v0.md) | Reuse the actual caller's candidate provenance and ordering. Outcome attribution does not qualify ranking influence. The historically named [cross-session memory RFC](cross-session-memory-substrate-v0.md) delivers bounded Todo continuation, not a general retrieval store. |
| D5 skills | [Project Skill Delivery](../../../loopx/capabilities/project_skill_delivery/README.md), [extension placement](../../reference/extensions.md) | Discovery, installation, enablement and domain permission are distinct. Suggestions consume the existing allowed catalog; no second installer/registry. |
| D6 planning | [Explore](../../../loopx/capabilities/explore/README.md), [Research Exploration RFC](research-exploration-control-plane-v0.md), [Manager Handoff RFC](capable-manager-semantic-handoff-v0.md) | The planner/manager owns candidate generation and adoption. Context lookup or model comparison cannot become a second planner or discharge an obligation. |
| Automation / policy | [post-writeback hooks](provider-neutral-post-writeback-capability-hooks-v0.md), [Effect Interpreter](agent-loop-effect-interpreter-v0.md), [TS migration](typescript-control-plane-migration-v0.md), [reliability RFC](long-running-agent-reliability-diagnostics-governed-delivery-v0.md) | M1 is explicit CLI observation. Later automatic invocation must use the existing named intent/lifecycle contract, outside primary transactions. Shared state/effect authority remains typed TypeScript; the zero-egress L1 collector stays separate. |

The [overall roadmap](loopx-overall-roadmap-v0.md) remains the portfolio owner:
D1/D4 fit S6/S11, D2/D3 the engineering S8/S12 journey, D5 S8/S12,
and D6 S11. This proposal does not reorder R1/G1 or claim those milestones.
The official-main delta adds coordination/recovery and Replan improvements;
none is evidence of Jev integration. Current source, draft dependencies and
future acceptance remain separate in the table above.

## 5. Common integration and degradation contract

### 5.1 Minimal structure

```text
Existing domain entry and eligibility
    +-- baseline workflow / candidates / evidence
    +-- explicitly opted-in assistance
          check configuration, egress, budget, current input and credential
          +-- not admitted: baseline + explicit not-evaluated result
          +-- admitted: bounded Jev call -> strict decode and basis check
                         +-- unusable: baseline + visible failure/abstention
                         +-- usable: baseline + separate advice
```

Baseline does not mean replaying a side-effectful workflow. Use existing outputs/snapshots or pure policy; never complete, spend or write the same work twice for comparison. Original domain authorization remains. Do not call the model inside critical transactions or hold Goal/receipt/lease locks over network I/O.

Only initial D1 belongs in Decision Context; D2/D3 retain their owners. Extract truly shared transport/deadline/decoding after a second real caller, not a speculative marketplace, global mode matrix or registry for six discussion items.

### 5.2 Disabled, baseline and assisted availability

These are product behavior descriptions, not three required global enums:

- **Disabled:** Preserve existing behavior. Do not inspect even an available key. Explicit inspection can describe disabled status without changing ordinary commands.
- **Baseline operation:** A scenario was explicitly requested but Jev lacks credentials, permission or availability. Return useful local results with explicit non-execution of assistance.
- **Assisted advice:** An admitted result is valid and still applicable. Show it separately; do not relabel the baseline as model-certified.

A key never activates a scenario by itself. No Jev key does not imply that the worker's original model provider needs no credentials. This RFC removes an additional Jev dependency; it does not make cloud Agents fully offline.

### 5.3 Degradation matrix

| Condition | Jev behavior | Original workflow | Diagnostic result |
|---|---|---|---|
| Disabled/no new configuration | No client, key lookup or network | Unchanged | Disabled only through explicit inspection |
| Requested, missing key | Skip locally; zero network attempts | Continue original path, including holds | not_run/missing_credential; no judgment |
| Key exists, upload not authorized | No send, no alternate endpoint | Original rules | not_run/egress_not_authorized |
| Auxiliary budget exhausted | No send, no false work-spend receipt | Original work-budget rules still apply | not_run/budget_unavailable |
| Required source unavailable/basis conflict | No current judgment or lower-authority guessed basis | Preserve original source/gate failures | basis_unavailable/source_incomplete |
| HTTP 401 | Record failure, end attempt, do not keep trying keys | Enhancement is not required | failed/authentication_failed |
| 429/529/temporary outage | Fall back for this invocation; no unbounded wait/retry | Continue baseline | failed/rate_limited or unavailable |
| Timeout/network loss/process interruption | Record may_have_been_sent when uncertain | Do not roll back primary transaction | Failed; unknown cost is not zero |
| Bad request/invalid response/NaN/model mismatch | Reject model result; expose implementation defect | Original decision unchanged | failed/contract_error or invalid_response |
| Valid response but abstention/low certainty | Retain answer and uncertainty; do not apply it to ranking/action | Original path | Completed but not used, not a fake API failure |
| Basis change/disable/late result | Cannot use as current advice | Original state | Historical/unusable |

Provider failures may be isolated; programming defects must not disappear inside `except Exception: pass`. Authority-store failure cannot fall back to stale Markdown and admit work. Baseline blocked remains blocked; baseline requires-review still requires review.

### 5.4 Result and exit semantics

Section 5.8 defines the proposed local result envelope, not a Core-packet extension. Identify the baseline reference, whether inference was attempted/completed, reasons, actual provider/model (no actual model when never run), use decision and judgment. Absent inference requires null/omitted judgment, probability and confidence, not false/0/1 substitutes.

The outer domain retains command exit semantics: original success may include enhancement-not-run; original failure cannot become success. A dedicated doctor or explicit model-qualification command may report unavailable/nonzero for missing credentials, but must not become an ordinary-work prerequisite. Do not impose universal exit 0.

Required review, verifiers and future governed seams retain their evidence obligations. This optional policy cannot bypass them. A future mandatory model requires separate fail-closed/manual-path and no-key decisions, not a reinterpretation of this RFC.

### 5.5 Configuration, inputs and compatibility

Each caller uses its existing configuration owner to opt into scenario/provider/data/budget/retention. D1's existing profile v0 is strict; section 5.9 proposes an explicit v1 transition owned by Decision Context, not a profile imposed on all domains. Old binaries must not silently discard new egress restrictions. A key cannot upgrade a profile.

Keep the adapter optional and lazy-loaded: ordinary imports, install and tests must not initialize a third-party SDK, download a model or access the network. Standard-library HTTP does not automatically guarantee total deadlines, redirect behavior, TLS, size limits or redaction; verify them. Pin the model for a trial and record the actual response model; never silently change to latest.

### 5.6 Alternate providers and caches

Default fallback is the original workflow, not another LLM. Already-authorized human/Agent review continues without a new model call created by this design. Future alternates need explicit provider lists, per-provider egress/budget/qualification. Do not reuse unrelated environment keys or another model's confidence thresholds.

No new implicit cached-result fallback in v0. Historical records remain historical. If exact cache use is later admitted, bind input bytes, source revisions, questions, model, policy, authority and freshness; mark cached. Disabled configuration cannot continue assistance from cache. Goal-ID-only or text-similarity matching is insufficient.

### 5.7 Recommended first vertical and ownership

Select **D1, an explicit operator CLI pilot**, as the proposed first slice.
Missing D1 evidence yields `basis_unavailable`; it does not automatically switch
the user to D2. Choosing D2 instead is a recorded scope decision with its own
local-probe prerequisite. All names below are proposed, not runnable today.

Placement record before implementation:

- **Capability:** existing catalog id `decision-context` (packet id
  `decision_context`); no new built-in semantic-assistance capability.
- **Provider:** proposed `jev` inference provider, extension-delivered in
  proposed `packages/loopx-jev/`. Reuse the existing extension lifecycle rather
  than creating another provider registry. Do not add production packaging in
  this documentation change.
- **Core owner:** the nearest Decision Context module owns the completed-work
  window, local baseline, input admission and private result readback. The
  package handles bounded transport and decoding. Neither `DecisionSourceProvider`
  nor the recall `ContextProvider` receives a new hidden meaning.
- **Policy:** reuse the existing typed acceptance/progress/Replan owners; do not
  copy their rules into Python or the provider. In particular, official-main
  Replan discharge has advanced beyond the older Python implementation at this
  branch baseline. Scenario-local advice is not a new shared state vocabulary.

Proposed entry journey:

1. `loopx decision-context assess-progress` takes the existing Goal/Agent/profile
   scope and one explicitly bounded completed-work window. Its baseline mode
   performs only authorized local reads; a separate explicit execution opt-in
   admits inference. Final flag spelling is owned by the implementation review.
2. Read effective canonical acceptance via `inspect_goal_acceptance`; retain its
   revision/digest and ready task bindings. Read host-verified artifact versions,
   validation outcomes and deduplicated Turn identities. Mark author claims as
   claims. If authority or required material is unavailable, report the local
   facts and gaps without inventing an assessment basis.
3. Reuse source `scan`/`exact_read` and coverage semantics with transient content;
   keep existing cursor proposals uncommitted. Return typed repeat and available
   acceptance/validation facts as the baseline. Do not execute validation commands
   or replay work merely to generate this read-only comparison.
4. Check scenario opt-in, Goal/Agent scope, source permission, destination/data
   consent, credential and auxiliary budget before inference-only expansion or
   send. Missing key makes no network attempt. Assemble only allowed text.
5. Invoke the provider once, with a total deadline, request/response bounds and
   no redirects or implicit retries. Recheck acceptance/source/profile revisions
   and enablement after response. A late or changed-basis result is historical.
6. Display baseline, source gaps and independent alignment/novelty advice, with
   private readback via proposed `assessment-status`. Readback never infers,
   settles a review, advances a cursor or changes work state.

The existing private pending-settlement file is **not** the model result store:
its profile/cursor CAS binds review settlement. Add only a bounded private
assessment/attempt record needed for readback and ambiguous-send recovery;
retain the existing private-file protection/atomic-write pattern without
reusing its settlement schema or creating another Goal/usage authority.

### 5.8 Minimal local result and attempt contract

A proposed `decision_progress_assessment_v0` record belongs only to D1.
The following terminal results must be encoded as a validated discriminated union,
not prose classifiers or combinations of independent booleans:

| Variant | Required information | Forbidden interpretation |
| --- | --- | --- |
| `not_run` | local reason, baseline/coverage, basis when available; dispatch `not_sent`; no judgment or actual model | no inference is not a clean assessment |
| `failed` | bounded failure reason, dispatch `not_sent` or `may_have_been_sent` or `response_received`; usage observed/estimated/unknown | unknown cost is not zero; failure cannot approve work |
| `completed` | pinned/actual model, both typed answers, question/policy revision, source basis, usage provenance; advice use `displayable`, `abstained`, `low_certainty` or `stale` | completed inference is not completed work or a review receipt |

Basis binds Goal/Agent, acceptance revision/digest, task bindings, ordered
window identities, artifact revisions and allowed-input digest, plus profile
and question-policy revision. Hashes stay private. Unavailable history has an
explicit gap; it is not an empty attempt history. Missing answer keys, unexpected
options, non-finite/out-of-range probabilities or incompatible actual models
are failed decoding, not abstention. Validate the complete supplied option set
and distribution sum with a documented numeric tolerance.

Use two independent Choice questions: alignment has `direct_progress`,
`necessary_prerequisite`, `off_contract`, `insufficient_evidence`; novelty has
`material_new_evidence`, `no_material_new_evidence`, `insufficient_evidence`.
These are proposed D1-local answer values, not additions to Core enums. A valid
insufficient-evidence answer is abstention; low certainty is a separate
calibrated use policy. When reasons overlap, use status precedence is stale,
abstained, low_certainty, then displayable; retain the detailed reasons.
Preserve both distributions; do not average them into a
single progress score or infer causal success from novelty.

Attempt identity binds an explicit request id and the exact basis/input/policy.
A conflicting reuse is rejected. Keep attempt lifecycle separate from terminal
results: `reserved` → `in_flight` → `terminal`, with atomic request-id admission
and allowance reservation in this private scope. A concurrent duplicate receives
`pending` without another send; it cannot fabricate a terminal failure or replay.
Persist a conservative send intent before
network dispatch; after a crash it is potentially sent, never automatically
resubmitted. A repeated request reads the retained record without a billable
retry and labels it historical/replayed, not fresh inference. Concurrent callers
reserve only the configured auxiliary allowance; ambiguous usage remains charged
conservatively until reconciled. If no trustworthy bound/accounting mechanism is
available, decline the assistance rather than borrow worker-delivery quota.
This is auxiliary accounting, not a new work-spend receipt or scheduler.

### 5.9 Configuration, entry points and downgrade

Recommend `decision_context_profile_v1` under the same owner: preserve all v0
fields and semantics, adding a separate optional inference section, disabled
when absent. Never hide inference inside `context_provider.config`.
Inference enablement is subordinate to outer `enabled` and `enabled_agents`;
it cannot grant a parallel scope. The section must specify scenario/provider, pinned model,
credential reference (never a secret value), allowed destination and data classes,
request/response size, total deadline, concurrency and auxiliary usage limits,
retention and audience. Implementation review freezes concrete limits before
live use; zero/unbounded/unknown budget cannot silently mean unlimited.

M1 retains the v0 requirement that an enabled profile has a source or context
provider: D1 requires at least one explicitly authorized local artifact source
in addition to canonical acceptance. Acceptance alone is not a source binding;
do not require a dummy recall provider to satisfy validation.

New readers accept unmodified v0 as inference-disabled. Old readers reject v1,
so activation requires verified reader compatibility; do not rewrite a shared
profile behind an older process. Upgrade is explicit, preserves v0 fields and a
private backup, and performs inspect/readback before enabling. Downgrade first
disables and drains assistance, then restores a validated v0 profile; never
silently strip restrictions while inference remains active. Unknown versions
or fields fail closed for assistance. Other domains keep their own configuration.

The actual existing config UI is descriptor-driven:
[capability configuration](../../../loopx/capabilities/configuration_ui.py) and
[Goal settings](../../../apps/presentation/dashboard/src/features/personal-workspace/goal-capability-settings.tsx).
There is no registered Decision Context editor at the audited baseline. Therefore
M1 deliberately delivers **CLI operator use only**, using the existing private
profile owner; it claims no Dashboard/Lark/worker journey. This RFC changes no
editor or UI. A later UI slice must register with those existing descriptors,
reuse the same profile/result projection, show missing-key/stale/error/disabled
states, and validate preview/apply/readback and the packaged frontend. Lark may
receive only a separately authorized public-safe projection, never private
assessment content by default.

### 5.10 Jev transport qualification boundary

The [official API](https://docs.typesafe.ai/api) uses a `state`, a keyed map of
`questions` and a requested `model`, returning keyed answers and the actual model.
D1 uses Choice; require both answers and strict option validation. Disable SDK
automatic retries or use a transport with equivalent bounded behavior. Authentication,
request validation, rate limiting and overload must remain distinguishable.

[Confidence](https://docs.typesafe.ai/confidence) is a distribution statistic;
Noul has no separate confidence field. It is not authorization or an independently
measured chance that a LoopX outcome is correct. Calibrate by scenario and language.
The [models page](https://docs.typesafe.ai/models), read on 2026-09-19, lists
`jev-1.13.0`; this is a trial candidate, not a qualified dependency. Moving aliases
are unsuitable for frozen comparisons. Public documentation is interface evidence,
not a live response, a retention agreement, or proof of value for Chinese workloads.

## 6. Alternatives and choices

Choose six discussion directions, one real delivery and domain-specific baselines rather than mandatory keys, a second fallback semantic engine, lexical overlap relabeled as probability, a global model state machine, confidence-to-action shortcuts, Jev inside the old L1 collector, or hidden model failover.

Preserving deterministic rules is not redundant dual authority: they own mandatory operation/verification while inference owns optional interpretation. Count entropy reduction only when same-responsibility duplication is removed. Useful new assessment also adds maintenance cost, which must be measured independently.

## 7. Safety, privacy and influence

Source/schema/identity/egress failures close assistance; workflow availability preserves original state. Minimize uploaded material. No full trajectories, arbitrary repository content, credentials or unapproved private benchmarks. Treat artifacts/comments/logs as untrusted input; the model has no tools or choice of destination. Never execute model-supplied references or commands.

Judgments may be private; hashes are not anonymization. Audience and retention are explicit, and raw material cannot enter public evidence, status, PRs or logs. Recorded provenance/answers establish processing history, not truth or transferable peer receipts.

Keep original L1 collection unchanged and declare inference egress separately. D1 first serves operators; D3 assistance grants no merge authority. Automatically injecting D4/D5/D6 into worker context is an influence requiring evaluation even without commands. Reversibility is not an approval exemption.

## 8. Migration, disablement and rollback

Documentation alone changes no runtime. Enable one approved scenario at a time, with feature-off characterization first. Disabling prevents new calls and unsent attempts and invalidates use of in-flight results. Retain/delete only this feature's private records under policy, never original Goal/receipt/cursor/lease state.

Code rollback cannot recall sent bytes or fees. Scenario owners handle mixed versions, config conversion and compatible readers without silently removing restrictions. Packaging must prove original commands work after adapter uninstall. A profile referencing an absent optional provider reports unavailable rather than crashing at import time.

## 9. Validation and acceptance

The following are requirements, not reported test results.

| ID | Case | Required result |
|---|---|---|
| F01 | Feature off, no key, ordinary entry | No key lookup/client/network/new file; baseline success and rejection unchanged |
| F02 | Explicit assistance, missing key | Useful baseline output, not_run, zero network attempts, no fabricated judgment |
| F03 | Key exists but disabled/egress denied | No upload, borrowed key or alternate provider |
| F04 | Original permission/receipt/source hold plus missing/optimistic model | Hold preserved; no auto-approval or verifier bypass |
| F05 | 401/422/429/529, timeout, invalid response | Visible bounded failure and baseline; honest uncertain dispatch/cost; no unlimited retries |
| F06 | Low certainty, abstention, missing question/candidate score | Separate completed-but-unused and failure; full ranking falls back to legal baseline order |
| F07 | Wrong scope or in-flight basis change | No send or stale result; no peer identity reuse/current relabeling |
| F08 | Default CI has no key/network consent | Offline contract and real-entry tests run; live qualification skipped/unverified |
| F09 | D2 without npm; D5 missing skill/provider | Supported local forms still produce signal; Jev failure cannot remove baseline discovery/use |
| F10 | Concurrency, replay, disable, restart, ambiguous dispatch | Bounded reservations; no duplicate side effects or automatic billable reattempt |
| F11 | Import/install/uninstall | No mandatory SDK/network/model download; legacy config and ordinary status preserved |
| F12 | Injection, opposite self-claims, low-scored required material | No authority escalation, false facts or hidden mandatory coverage; errors observable |

Offline injected responses test conformance, not Jev intelligence. Live qualification is explicit opt-in with authorized data/budget; missing keys produce skipped/unverified, never a fixture masquerading as live.

Each direction freezes an independent rubric, representative data, development/holdout task families, false alerts/misses/abstention and cost metrics. Common measurements are availability, baseline parity, failures, latency and extra usage. Do not average incompatible Choice/Score/Noul confidence into a global intelligence score.

D1 compares the full original chain; D2 the local probe; D3 the existing review; D4/D5 original candidate workflows; D6 the original planner. Prove observation value, recommendation value and causal intervention value separately. A direction may stop for lack of value.

### 9.1 D1 acceptance procedure

Implementation tests must invoke the actual new CLI with isolated synthetic
Goal/Agent/source fixtures and an injected provider, not only call a decoder.
Use fail-on-call spies for credential access, transport and Core writes. Compare
ordinary CLI results and authorization refusals with the frozen pre-change
baseline; then exercise the explicit no-key report, scope/basis failures,
provider error matrix, process interruption, concurrent reservations and readback.
For the first operator pilot, F09 is deferred with D2/D5, not marked passed.
Run the real authority backend integration required by any touched authority
path; never mutate active Goal state for these tests.

Value evaluation is a separate opt-in experiment. Freeze artifact-based cases,
independent human labels, rubrics, language strata (Chinese and English), held-out
task families and a usage ceiling before collecting answers. Compare the full
existing workflow with the same workflow plus visible advice. Report false
alerts, missed drift, abstention/coverage, disagreement, latency and auxiliary
usage with denominators; keep necessary prerequisites, negative experiments,
legitimate waits, ID-only novelty, contradictory author claims and injection
cases. Set numerical adoption thresholds before the trial, not after observing
results. No uplift is a valid stop decision; neither API availability nor a
high model confidence establishes operator value.

Current documentation-only checks (not M1/M2 acceptance):

```bash
uv run --extra test python examples/docs-governance-smoke.py
uv run --extra test python examples/docs-asset-integrity-smoke.py
git diff --check
```

## 10. Operational experience

Explicit entry points should say: "Baseline workflow available; Jev is not configured, so no model semantic judgment was made." Do not repeatedly demand a key, create a user gate, send notifications or create Todos for missing credentials. Repeated errors update bounded status rather than flooding per-Turn attention.

Reading status does not invoke inference. When available, record requested/actual model, source/question revisions, use decision, distributions, latency and cost provenance. Proven not-sent means zero remote attempts; ambiguous dispatch does not mean zero cost. Automatic background retries are out of initial scope; a later periodic caller must specify cooldown, queue, budget and recovery probes separately.

After credentials recover, only the next authorized request evaluates current material. Do not backfill history or replay all failed attempts. Disablement overrides caches and in-flight results. Auxiliary inference spend is not a successful worker-delivery quota receipt.

## 11. Normative delivery plan

| Stage | Minimum delivery | Entry/exit | Exclusions |
|---|---|---|---|
| M0 | Six ranked directions, common degradation, first owner/scope | Recommended Q1/Q2/Q3 recorded; bilingual/reference checks; maintainer acceptance remains open | No six empty interfaces |
| M1 | One scenario's complete off/no-key/failure baseline plus optional advice | Default D1; explicitly choose D2 if D1 basis is not ready; real applicable F01–F12 | Not merely a client; no mandatory Jev key or Core authority/settlement change |
| M2 | Live qualification and operator-value trial for that scenario | Separate keyed environment, authorized data, frozen budget; may find no advantage | API success is not promotion |
| M3 | Second real scenario, then demonstrate adapter reuse | Proven reuse and owner isolation; independent fallback acceptance | Do not impose D1 config on all capabilities |
| M4 | Reorder remaining D3–D6 from observed results | Independent ownership, value and privacy review | No promise to implement all six |

The discussion RFC can finish M0 and await runtime decisions; implementing every direction is not a prerequisite for reviewing the RFC. [#4447](https://github.com/huangruiteng/loopx/issues/4447) and [#4743](https://github.com/huangruiteng/loopx/issues/4743) retain their independent scope and closure conditions. Automatic control remains a separate proposal, not hidden M5.

## 12. Open decisions

| Question | Recommendation | Owner and blocking scope |
|---|---|---|
| Q1 First direction/order | D1 explicit CLI pilot in 5.7; D2 requires a recorded alternative-scope decision | Product/domain owner; blocks only corresponding M1 |
| Q2 Shared-code location | Local first; extract actual common transport after second caller | Relevant maintainers; no global semantic authority |
| Q3 Config/version/no-key output | D1 v1 migration in 5.9; separate inference section; preserve v0 and ordinary output | Profile/CLI owner before M1 |
| Q4 Data/model/budget | Explicit destination/classes, pinned model, bounded single attempt, no auto retry | Privacy/operations/evaluation owner before live |
| Q5 Alternate models | No automatic alternate initially; future explicit opt-in/qualification | User/capability owner; never blocks local baseline |
| Q6 Ranking/skill/plan influence | Operator-only first; independent worker-adoption treatment | Host/Goal/security owner for that influence |
| Q7 Promotion to mandatory gates | Not approved; later mandatory verifier needs fail-closed/manual policy | Existing authority owner; confidence is not approval |

## Appendix A: Execution ledger (non-normative)

### 2026-09-19 — Initial source-aligned proposal

- **Baseline:** `9f1916960306b3650d795895b89f331eeae2516e`; targeted upstream delta through `cc8e28d8b58a9b15e928d7e2cee16097172567d1`.
- **Delivered:** Bilingual design, six-direction owner map, recommended D1 CLI slice and failure/rollback/validation contracts.
- **Evidence boundary:** Source and official interface documentation reads; this entry does not attest a runtime test or model trial.
- **Known gaps:** M1 implementation, live conformance, value evaluation and UI/worker adoption remain unshipped by this proposal.
- **Normative effect:** Initial sections 1–12 proposed for review; no acceptance inferred.

## Appendix B: Decision log

| Date | Recommendation | Approval owner / state | Alternative | Sections |
| --- | --- | --- | --- | --- |
| 2026-09-19 | D1 operator CLI; existing capability; optional Jev package; explicit profile v1 | Decision Context / product maintainers; not yet approved | D2 after its local probe; a separate config format if compatibility research justifies it | 3, 5, 11, 12 |

## Appendix C: Evidence registry

| Evidence | Claim / locator | Result and boundary |
| --- | --- | --- |
| E1 | Source ownership map in 4.1 at the named baseline | Read; implementation facts only, no runtime certification |
| E2 | Official-main delta through the named SHA; Replan and coordination owners | Read; no Jev implementation observed in that bounded delta |
| E3 | [TypeSafe API](https://docs.typesafe.ai/api), [confidence](https://docs.typesafe.ai/confidence), [models](https://docs.typesafe.ai/models), accessed 2026-09-19 | Interface documentation only; no API call or quality qualification |
| E4 | [Building guidance](https://docs.typesafe.ai/concepts/how-to-build-with-system-one), [skill suggestion example](https://docs.typesafe.ai/cookbooks/skill_suggestion) | External design references; no transfer of benchmark results or authorization to LoopX |
| E5 | F01–F12 and section 9.1 | Proposed acceptance, unexecuted for this feature; missing live qualification is not a pass |

## Appendix D: Rejected shortcuts

No-key default approval; rules disguised as probabilities; key-based activation;
silent provider failover; a new intelligence control plane first; opaque IDs as
semantic evidence; fixtures claimed as live; unaccounted retries; universal
confidence thresholds; new registry fields without a real caller. PR evidence
review stays with `pr_review_queue`; typed presentation is a consumer, not its
replacement. Retrieval relevance is not verified memory utility.

## Appendix E: Engineering reduction criterion

Every implementation PR states the real caller, baseline, optional increment,
no-key behavior, retained obligations and added/removed maintenance costs.
The future-facing pass here chooses one local inference seam and rejects six
unused interfaces; shared transport is deferred until a second caller proves
reuse. Stop experiments without value. Independence from Jev is an executable
product property, not a disclaimer only visible after configuring a key.
