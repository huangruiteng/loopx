# Presentation Surface Layout

LoopX has enough human-facing surfaces that they should be treated as one
presentation layer rather than scattered frontend, renderer, and connector
helpers.

The presentation layer is the intelligent display middle tier: it reads
LoopX's public-safe state, folds it into reviewable projections, renders it for
humans, and syncs it to external display surfaces. It does not decide quota,
mutate todos, bypass gates, or own connector credentials.

## Repository Boundary

| Layer | Canonical path | Role |
| --- | --- | --- |
| Frontend apps | `apps/presentation/dashboard/` | Browser surfaces such as dashboard, frontstage, and developer cockpit. |
| Display renderers | `loopx/presentation/renderers/` | Pure renderers over already-built payloads, such as status Markdown. |
| Display sinks | `loopx/presentation/sinks/` | External display outputs, such as Lark/Feishu cards and Base tables. |
| Display projections | `loopx/presentation/projections/` | Intermediate public-safe read models for graph, table, card, or feed views. |
| Capability facades | `loopx/capabilities/*` | User-facing capability names and compatibility imports when a display sink is also a capability. |
| Control plane | `loopx/control_plane/` and state APIs | Source of truth for goals, todos, gates, claims, quota, evidence, and replanning. |

## Relationship To Value Connectors

Value connectors bring external signals into LoopX under a scoped plan and
gate. Presentation sinks export LoopX-owned public-safe state to a human
display. They can cooperate, but they should not live in the same module just
because both mention an external product.

For example, a GitHub or Lark value connector may produce a compact signal.
The presentation layer may later show that signal in the dashboard, a graph
projection, or a Lark Base table. The connector still owns ingestion and
authority checks; the presentation layer owns display shape and public/private
redaction.

## Placement For Explore Topology Results

Explore has two different responsibilities and should not be moved as one
piece:

- exploration evidence and topology events: keep under the explore capability
  or a future control-plane explore/read-model boundary, because this data feeds
  vision, replan, successor todos, and user gates;
- display-oriented graph/table/card projections: place under
  `loopx/presentation/projections/explore/` when they are only reshaping
  public-safe explore state for humans;
- Lark/Feishu Base sync for nodes, edges, and findings:
  `loopx/presentation/sinks/lark/explore_results.py`;
- CLI entry point: `loopx/cli_commands/explore.py`;
- optional user-facing facade: `loopx/capabilities/explore/` if the command is
  marketed as a capability pack.

This keeps explore useful as a replan input instead of reducing it to a board,
while still keeping display sinks next to other intelligent presentation work.
