# Domain Capability Packs

Status: design target.

Principle: LoopX defaults to a generic control plane. It should
guarantee state, evidence, boundaries, handoff, and validation routing before it
tries to make domain judgments. Domain packs can make LoopX smarter, but
they must be explicit about capability and permission.

## Why This Exists

Long-running projects often start to look domain-specific. An ML experiment
agent, a benchmark agent, a deployment agent, and a documentation agent all need
durable state and compact evidence, but only some of them should know about
primary metrics, dataset windows, training jobs, or promotion decisions.

The default control plane should therefore do two things:

- recognize that a domain pack might help;
- stop before enabling domain-specific autonomy until the registry or owner
  records that permission.

This avoids a quiet escalation from "track my goal" into "interpret and launch
domain work." It also keeps LoopX useful for ordinary engineering todos
that do not have experiment boards, primary metrics, guardrails, or production
job handles.

## Contract Shape

`domain_pack_contract_v0` is a registry-owned goal-boundary extension:

```yaml
domain_packs:
  ml_experiment:
    enabled: false
    autonomy: suggest_only
    allowed_actions:
      - observe_external_jobs
      - ingest_metrics
      - classify_results
      - propose_replan
    capability_requirements:
      - external_evidence_poll
    primary_metric_authority: explicit_board_only
    auto_launch_requires: board_selected_and_verified
```

Allowed `autonomy` values:

| Value | Meaning |
| --- | --- |
| `suggest_only` | Detect signals and recommend enabling a pack. Do not write domain conclusions. |
| `advisory` | Write compact results, hypotheses, and replan proposals. Do not launch, stop, restart, or sync production code. |
| `delivery` | Perform authorized domain actions only inside the goal boundary, quota guard, capability gate, and validation/writeback lifecycle. |

Default behavior:

- `enabled=false`: status may say "this goal looks like an ML experiment; enable
  the ml_experiment pack if that is intended."
- `autonomy=suggest_only`: the pack may explain why it would help, but it does
  not write experiment results or replan decisions.
- `autonomy=advisory`: the pack may write compact evidence, structured result
  summaries, and proposed replans, but it still cannot launch jobs.
- `autonomy=delivery`: launch/stop/restart/sync actions require explicit goal
  boundary authorization, fresh quota, selected and verified board authority,
  preflight validation, and compact writeback.

The first enablement should be a visible registry or owner decision. Later
turns may use the enabled pack autonomously only within that recorded goal
boundary.

## Generic Capabilities

These capabilities are not ML-specific and should be available in the default
LoopX control plane.

| Capability | Default Role |
| --- | --- |
| `observable_artifact_handle_v0` | Describe external jobs, CI runs, benchmark attempts, evaluations, deploys, or other long tasks with an observable handle, allowed poll command, artifact refs, terminal markers, and read boundary. |
| `validation_surface_map_v0` | Require each executable todo to name how it will be validated: code tests, document scans, external evidence, review packet, or blocker writeback. |
| `result_event_v0` | Record terminal state, evidence pointer, validation status, outcome classification, and next action without assuming a domain metric schema. |
| `reward_style_hint_preview` | Provide read-only candidate-ranking hints from compact reward/todo evidence. Hints may explain ordering but cannot override user gates, claims, scopes, capabilities, workspace guard, or goal boundary. |
| `handoff_packet_v0` | Package objective, current state, validation, risk, next action, and stop condition for a human or another agent. Domain packs may add fields, but handoff itself is generic. |
| `status_frontstage_plain_language_projection` | Explain what happened, what is blocked, what comes next, and what user action is needed in ordinary language. Domain packs may add specialized cards. |

These should stay safe for any project type. A project-specific adapter decides
what handles, refs, and validations it can expose, but the protocol shape is
generic.

## ML Experiment Pack

The ML experiment pack is a domain capability pack. It should stay default-off
because it carries assumptions that ordinary engineering work may not share.

Pack-controlled capabilities:

| Capability | Why It Is Domain-Specific |
| --- | --- |
| `ml_experiment_result_v0` | Uses primary metric, baseline delta, guardrail metrics, decision windows, aligned evaluation, and train-only guardrail concepts. |
| `dataset_window_contract_v0` | Models date/hour coverage, matched windows, missing-hour handling, fairness labels, and sample comparability. |
| `hypothesis_ledger_v0` | Tracks mechanism family, route, positive and negative evidence, near-neighbor exclusions, retirement rules, and portability. |
| `experiment_replan_v0` | Chooses next experiment batches, exploration/exploitation allocation, quota use, promotion, and retirement proposals. |
| `external_training_job_adapter` | Polls external training or evaluation jobs, ingests metrics, checks workspace markers, terminal markers, and lineage. |
| `auto_launch_experiment` | Launch/stop/restart/sync actions are delivery authority, not generic control-plane behavior. |
| `dreaming_experiment_proposal_v1` | Generates candidate mechanisms, research directions, and archive suggestions from experiment history; useful, but advisory until reviewed. |

The pack should never infer that a metric board, dataset path, training system,
or launch command is authorized merely because text in a todo looks familiar.
Authority comes from the registry, goal boundary, and compact owner decision.

## Detection

`domain_pack_detection_v0` is a suggest-only detector. It may inspect public-safe
goal metadata and compact state for signals such as:

- experiment board or evaluation artifact references;
- primary metric or guardrail labels;
- external job evidence handles;
- repeated metric/classification/result todos;
- explicit owner language asking for experiment advisory or delivery.

The detector returns suggestions, not permissions:

```json
{
  "schema_version": "domain_pack_detection_v0",
  "suggested_pack": "ml_experiment",
  "confidence": "medium",
  "reason_codes": ["primary_metric_label", "external_job_handle"],
  "allowed_next_action": "suggest_enablement",
  "requires_owner_or_registry_decision": true
}
```

If the pack is disabled, the agent may recommend enabling it and may continue
generic control-plane work. It must not write experiment conclusions, mark a
winner, launch jobs, or treat a domain hint as a gate bypass.

## Result Flow

When an ML experiment pack is enabled in advisory mode, the generic result event
still wraps the domain result:

```yaml
result_event_v0:
  terminal_state: done
  evidence_pointer: compact_metrics_artifact
  validation_status: validated
  outcome_classification: outcome_progress
  next_action: propose_replan
  domain_extension:
    kind: ml_experiment_result_v0
    primary_metric_status: improved
    guardrail_status: clean
    decision_status: candidate_not_winner_yet
```

The generic fields keep status, quota, review packets, and frontstage surfaces
stable. The domain extension adds useful interpretation only after the pack is
enabled.

## Roadmap

P0: split the boundary.

1. Design and validate `domain_pack_contract_v0`: `enabled`, `autonomy`,
   `allowed_actions`, `capability_requirements`, and boundary semantics.
2. Implement `domain_pack_detection_v0` as suggest-only. It can recognize
   experiment-shaped goals, but it cannot enable itself.
3. Promote `observable_artifact_handle_v0` as a default generic capability for
   long-running work.

P1: add ML experiment advisory mode.

4. Define `ml_experiment_result_v0` over compact metric/evaluation artifacts.
5. Define `dataset_window_contract_v0` for date/hour coverage, intersection,
   fairness labels, and conclusion eligibility.
6. Define `hypothesis_ledger_v0` for mechanism families, positive/negative
   evidence, near-neighbor exclusions, and promote/retire conditions.
7. Add `experiment_replan_preview` that proposes candidates and validation
   needs without launching jobs.

P2: add controlled delivery.

8. Implement `ml_experiment` delivery mode behind explicit registry boundary,
   board selection, preflight verification, quota, capability gates, and
   writeback.
9. Add an `ml_experiment_frontstage` card that explains the current best route,
   why it is or is not a winner, what evidence is pending, and which user
   feedback would change the plan.
10. Add an `experiment_dreaming_lane` for advisory candidate generation and
    archive suggestions. Promotion to executable agent todo requires operator
    review.

## Non-Goals

- Do not ship ML experiment assumptions in the default control plane.
- Do not auto-launch or stop external jobs from detection alone.
- Do not infer primary metric authority from arbitrary text.
- Do not store raw metrics dumps, private job logs, credentials, local paths,
  or production artifacts in public docs or generic status projections.
- Do not let reward-style or replan hints override gates, claims, scope,
  capabilities, workspace guard, or goal boundary.
