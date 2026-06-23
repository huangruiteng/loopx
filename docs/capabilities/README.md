# LoopX Product Capabilities

This directory groups LoopX product capabilities by real usage path. Keep kernel
control-plane code generic; put scenario-specific protocols, implementation
modules, CLI entrypoints, and smokes under the capability they serve.

Current capability paths:

- [issue-fix](issue-fix/README.md): turn public GitHub issue/PR signals into
  caller-approved local issue branches and PR-review evidence.
- [content-ops](content-ops/README.md): collect public/private content signals
  into reviewable source, angle, draft, feedback, and publish-gate packets.

Do not add a capability path until there is at least one real CLI entrypoint and
one smoke test. Future ideas belong in product planning docs until they have
executable evidence.
