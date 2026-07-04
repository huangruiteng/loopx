# multi_agent_three_layer_minimality_contract_v0

`multi_agent_three_layer_minimality_contract_v0` defines the reusable layering
rule for LoopX multi-agent products:

1. **User layer:** declares intent and a few product-level options.
2. **Preset layer:** supplies domain defaults, role semantics, handoff hints,
   and product evidence or metric adapters.
3. **Kernel layer:** owns the reusable multi-agent mechanics.

The goal is not only to minimize the user's snippet. The preset must also stay
thin so auto-research can be a reusable example for future multi-agent products
rather than a second product-specific runner.

## Ownership

| Layer | Owns | Must Not Own |
| --- | --- | --- |
| User | Objective, rounds, optional role overrides, and optional data/eval entrypoint. | Tmux/Codex TUI launch, pane-local tick commands, quota/frontier protocol details, worker plumbing, per-agent vision/replan state, or machine JSON routing. |
| Preset | Domain roles, handoff hints, metric/evidence loop, and domain defaults. | Generic runner lifecycle, real Codex TUI panes, workspace/trust-safe launch, pane-local A2A tick, todo/evidence/status protocol, per-agent vision budgets, replan state transitions, or compact human status. |
| Kernel | Multi-agent runner, real Codex TUI panes, workspace/trust-safe launch, pane-local A2A tick, todo/evidence/status protocol, CLI-enforced per-agent vision budgets, vision/replan state transitions, compact human status, and default role prompt scaffolding. | Domain-specific research, benchmark, support, or sales semantics. |

## Contract Shape

The reusable helper lives in `loopx/capabilities/multi_agent/contract.py`:

```python
build_three_layer_minimality_contract(
    product_id="customer-support",
    preset_id="support_triage_preset",
    user_intent_fields=["inbox", "rounds"],
    preset_responsibilities=["triage_roles", "handoff_hints"],
)
```

It returns:

```json
{
  "schema_version": "multi_agent_three_layer_minimality_contract_v0",
  "principle": "user_and_preset_stay_thin_kernel_owns_reusable_mechanics",
  "user_layer": {
    "owns": "intent"
  },
  "preset_layer": {
    "must_remain_reusable": true
  },
  "kernel_layer": {
    "cross_product_reuse_required": true
  }
}
```

## Auto-Research Preset

Auto-research is one preset on top of the generic kernel. Its preset layer owns
research roles, handoff hints, the metric/evidence loop, and domain defaults.
It does not own the runner, TUI panes, workspace/trust-safe launch,
pane-local A2A tick, todo/evidence/status protocol, per-agent vision budgets,
or replan state transitions.

This keeps the public promise honest: a small auto-research recipe should prove
that other products can also reuse the same kernel with their own thin preset.

## Public Line-Count Claim

The public "few lines of auto-research" claim counts declarative recipe lines,
not the shared kernel implementation.

For the default auto-research demo, the bounded claim is:

| Layer | Counted Lines | Meaning |
| --- | ---: | --- |
| User | 1 | `loopx auto-research start "<open question>" --execute` |
| Auto-research preset | 4 | default role specs: curator, mapper, runner, verifier |
| Generic kernel | 0 | shared runner, Codex TUI panes, fixed wake prompt, pane-local tick, todo/evidence/status protocol |

So the honest slogan is: one user line plus a four-line preset can start a
decentralized A2A research loop on the shared LoopX kernel. The slogan must not
claim that tmux launch, Codex TUI bootstrap, quota/frontier, evidence routing,
or status projection are reimplemented inside the auto-research preset.

## Acceptance

A change satisfies this contract only when:

- the user recipe remains a few intent fields, not runner configuration;
- the preset has no host process lifecycle or pane-local tick implementation;
- the preset has no product-specific fork of per-agent vision/replan mechanics;
- the generic kernel contract stays domain-agnostic;
- another multi-agent product can reuse the same kernel without importing
  auto-research code.
