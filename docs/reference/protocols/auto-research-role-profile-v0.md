# auto_research_role_profile_v0

`auto_research_role_profile_v0` defines how a LoopX auto-research worker knows
who it is before it loads any role-specific playbook. It bridges three existing
surfaces:

- the shared LoopX control plane, which grants identity and authority;
- worker-local role playbooks, which define how to act inside a phase;
- repository or workspace `AGENTS.md`, which defines long-lived local rules.

The contract exists because Arbor and LoopX use skills differently. Arbor can
keep identity mostly inside a Coordinator / Executor topology, then load skills
as phase playbooks. LoopX is decentralized: several workers may run in separate
Codex sessions over one state graph, so identity must be explicit control-plane
state rather than something inferred from a skill name or pane title.

## Ownership Split

| Surface | Owns | Does not own |
| --- | --- | --- |
| LoopX control plane | `agent_id`, `role_id`, claim, capability token, phase, write boundary, gate state, and stop condition. | The detailed reasoning checklist for an implementation phase. |
| Worker-local role playbook | Commands, checklists, artifact schema reminders, review prompts, and phase-specific failure modes. | Authority to write, promote, merge, publish, or bypass gates. |
| `AGENTS.md` | Repository-local and workspace-local rules such as private boundary, PR hygiene, first-screen review, protected paths, and local launch policy. | Dynamic role assignment or current frontier selection. |
| Host launcher | Visible panes, environment variables, attach/stop controls, and takeover affordances. | Research truth, promotion decisions, or hidden scheduling authority. |

This split keeps playbooks useful without letting them become a second source of
identity. A worker can load the same `loopx-auto-research` playbook in different
roles, but the profile tells it which section applies and which writes are
allowed.

## Profile Shape

The profile is public-safe and small enough to embed in a launcher packet,
frontier item, bootstrap prompt, or future kernel API.

```json
{
  "schema_version": "auto_research_role_profile_v0",
  "goal_id": "loopx-auto-research-demo",
  "agent_id": "codex-auto-research-runner-1",
  "role_id": "evidence_runner",
  "display_name": "Evidence runner",
  "phase": "attempt_running",
  "capability_token": "evidence_runner",
  "todo_id": "todo_auto_research_demo_001",
  "hypothesis_id": "hyp_state_a2a_round",
  "allowed_actions": ["claim_attempt", "edit_allowed_scope", "run_dev_eval", "write_evidence"],
  "write_scope": ["solution.py", "experiments/**"],
  "protected_scope": ["task.py", "eval.py", "data/**"],
  "required_skill": "loopx-auto-research",
  "skill_section": "Evidence runner",
  "agents_overlay": ["workspace/AGENTS.md"],
  "stop_conditions": [
    "quota should-run returns false",
    "frontier is empty or claimed by another agent",
    "protected scope would be edited",
    "private material or credentials are required",
    "operator gate is projected"
  ],
  "handoff_outputs": [
    "research_evidence_event_v0",
    "branch_or_artifact_ref",
    "retry_or_retirement_rationale"
  ],
  "successor_todos": [
    {
      "after_action": "run_dev_eval",
      "when": "dev_supported_without_holdout",
      "target_agent_id": "codex-main-control",
      "target_role_id": "evidence_runner",
      "task_class": "advancement_task",
      "action_kind": "run_holdout_eval",
      "text": "Run held-out validation for the dev-supported hypothesis."
    }
  ]
}
```

Required fields:

- `goal_id`, `agent_id`, `role_id`, `phase`, and `todo_id` identify the current
  worker and work item.
- `capability_token` must match a capability in
  `auto_research_role_state_machine_v0`.
- `allowed_actions`, `write_scope`, `protected_scope`, and `stop_conditions`
  bound what the worker may do.
- `required_skill` and `skill_section` route the worker to the correct how-to
  instructions after identity is resolved.

Optional fields such as `hypothesis_id`, `agents_overlay`, `handoff_outputs`,
and `successor_todos` make the profile more ergonomic but do not grant
authority. A successor todo declaration is a small role-local handoff rule: when
the worker completes `after_action` and the `when` condition is satisfied, the
pane-local tick may write the named LoopX todo for `target_agent_id`. It is not a
graph-wide planner, and it must still pass quota, todo metadata, and
public/private boundary checks before another agent can run it.

## Resolution Order

Every visible auto-research worker should resolve its instructions in this
order:

1. Read the role profile from the launcher packet, frontier item, or bootstrap
   prompt.
2. Run `quota should-run --goal-id ... --agent-id ...` and confirm the selected
   todo still matches the profile.
3. Read the current role/state-machine contract for allowed transitions.
4. Load the required skill and only the section named by `skill_section`.
5. Read applicable `AGENTS.md` overlays for repository and workspace rules.
6. Act within `allowed_actions` and `write_scope`, then write only the listed
   handoff outputs and role-declared successor todos.

If any source conflicts, the worker fails closed in this order:

1. operator gate or private/security boundary;
2. control-plane quota, claim, capability, or write-scope mismatch;
3. repository `AGENTS.md` safety rule;
4. skill checklist disagreement;
5. launcher pane label or cosmetic prompt text.

## Auto-Research Role Profiles

The v0 demo should expose four logical always-on profiles. A host may render
fewer panes only when the merged duties are explicit in the profile and the
records still name the role that produced each transition.

| Role id | Skill section | Primary phase | Writes | Must stop when |
| --- | --- | --- | --- | --- |
| `research_curator` | Research curator | `contract_ready`, `promotion_gate` | `research_contract_v0`, owner gate todos, protected-boundary notes. | The next step would select a winner, run an experiment, or publish unsupported evidence. |
| `hypothesis_mapper` | Hypothesis mapper | `hypothesis_proposed`, `retired` | `research_hypothesis_v0`, successor todos, no-follow-up rationale. | Novelty requires the same source that inspired the idea, or negative evidence would be hidden. |
| `evidence_runner` | Evidence runner | `frontier_selected`, `attempt_running` | Branch refs, dev/holdout eval evidence, retry packets, role-declared successor todos. | Protected scope changes, promotion decisions, or private/raw artifacts are needed. |
| `evidence_verifier` | Evidence verifier | `evidence_recorded`, `evaluated`, `promotion_gate` | Held-out validation evidence, evaluation summary, promotion/retirement candidates, gate todos. | Evidence is dev-only but would be presented as promoted, or held-out data is missing when required. |

Future roles such as gate steward, synthesis narrator, and frontier janitor are
split candidates, not required v0 panes. They should be introduced only when
evidence from the demo shows that a transition duty needs a separate owner.

## Worker-Local Playbook Strategy

Use one worker-local `loopx-auto-research` playbook that contains role sections:

- `Research curator`
- `Hypothesis mapper`
- `Evidence runner`
- `Evidence verifier`
- `Visible takeover and stop controls`

This keeps each visible worker aligned without exposing auto-research as a
global LoopX skill for ordinary project agents. Split into role-specific
worker playbooks only after a visible run shows repeated confusion that a single
role-routed playbook cannot prevent. The split decision should cite evidence
such as wrong section loading, unauthorized writes, hidden negative evidence, or
missed stop conditions.

The playbook body should not invent current work. It should tell the worker to
read the role prompt/profile context and run role-local quota/frontier commands
through the pane-local LoopX wrapper inside the Codex TUI. This mirrors Arbor's
useful "load a checklist at the exact phase" behavior while preserving LoopX's
decentralized identity model.

## Demo Launcher Implications

A visible tmux or terminal launcher should silently materialize the profile and
start one fresh interactive Codex CLI TUI per role:

```bash
export LOOPX_GOAL_ID=loopx-auto-research-demo
export LOOPX_AGENT_ID=codex-auto-research-runner-1
export LOOPX_ROLE_ID=evidence_runner
export LOOPX_ROLE_PROFILE_REF=auto_research_role_profile_v0
exec codex -c model_reasoning_effort=high -C "$LOOPX_PROJECT" "$ROLE_PROMPT"
```

The pane title is cosmetic. The profile and quota/frontier projection are the
authority, but raw profile/frontier JSON should stay in local artifacts or an
explicit machine channel. The launcher must keep attach, interrupt, and stop
commands visible so the user can take over without reading hidden logs.

## Acceptance Checks

An implementation satisfies this contract when:

- launcher and frontier packets expose `auto_research_role_profile_v0` for each
  visible worker without printing raw profile JSON on the first screen;
- each profile names `agent_id`, `role_id`, `phase`, `capability_token`,
  `allowed_actions`, `write_scope`, `protected_scope`, `required_skill`,
  `skill_section`, and `stop_conditions`;
- the default demo uses the four logical v0 role identities, with owner takeover
  as a visible control surface rather than a research role;
- the role-aware skill says identity comes from the profile and quota/frontier,
  not from the skill itself;
- `AGENTS.md` overlays can add stricter local rules but cannot expand a role's
  authority beyond the control-plane profile;
- validation proves no leader/coordinator pane is required for the demo to be
  understandable or interruptible.
