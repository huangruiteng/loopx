# LoopX Product Capabilities

This directory groups LoopX product capabilities by real usage path. Keep kernel
control-plane code generic; put scenario-specific protocols, implementation
modules, CLI entrypoints, and smokes under the capability they serve.

Current capability paths:

- [periodic-report](periodic-report/README.md): evaluate cadence and material
  progress triggers, then compose deterministic provider-neutral report runs
  with source, artifact, archive, and delivery receipts.
- [issue-fix](issue-fix/README.md) ([中文](issue-fix/README.zh-CN.md)): turn
  public GitHub issue/PR signals into focused fixes, explainable reviewer
  routes, authority-gated PRs, and monitored lifecycle outcomes.
- [content-ops](content-ops/README.md): collect public/private content signals
  into reviewable source, angle, draft, feedback, and publish-gate packets.
- [value-connectors](value-connectors/README.md): install and run public-safe
  external-value connector starters, beginning with body-free GitHub public
  channel metadata probes, plus gated candidate profiles such as X/browser
  social work and finance market snapshots.
- [explore](explore/README.md): record long-running exploration results as a
  compact topology (nodes, edges, findings) and project them into a
  Feishu/Lark Base result board and result card.

Do not add a capability path until there is at least one real CLI entrypoint and
one smoke test. Future ideas belong in product planning docs until they have
executable evidence.
