# Product Direction

This folder keeps stable product-direction notes that are broader than one
runtime contract, benchmark route, or launch draft.

- [Product vision](vision.md): how Goal Harness grows from an engineering
  control plane into a human-friendly control plane for long-running agent work,
  including the creator-operator productization case.
- [Server-client product shape](server-client-product-shape.md): the medium-term
  product model where the server owns durable state, delivery/planning queue
  boundaries, and governed proposal promotion, the client acts as the user's
  intent proxy, and executor loops perform bounded work with evidence writeback.
- [Non-technical operator status model](nontechnical-operator-status-model.md):
  first-screen card model for people who need to understand agent progress,
  blockers, next moves, and feedback paths without reading logs or CLI output.
- [Reward-style replanning hints](reward-style-replanning.md): public-safe
  design for turning explicit reward, corrections, and steering feedback into
  compact candidate-ranking hints without raw chat, hidden profiling, or hard
  gate semantics.
- [Naming decision packet](naming-decision-packet.md): why the project should
  keep `Goal Harness` as the brand while testing `lifetime-goal control plane`
  as category/tagline language.
