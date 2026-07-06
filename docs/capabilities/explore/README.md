# Exploration Result Layer

Status: prototype adapter contract v0.

Long-running exploration goals (for example a Codex loop studying an external
software domain through LoopX) produce results that operators want to read as
a topology, not as an agent action log: what has been explored, where the loop
is blocked and why, and what was found. This capability keeps those results in
a compact, public-safe, append-only log and projects them into a Feishu/Lark
Base result board plus one interactive result card.

## State Contract

- Reads: `goals/<goal-id>/explore-result-log.jsonl` under the LoopX runtime
  root (`loopx_explore_result_event_v0` events appended by `loopx explore
  node|edge|finding`), and the local board config `.loopx/lark-explore.json`.
- Writes: the explore result log (append-only), the local board config
  (`loopx_lark_explore_local_config_v0`, including the result-id to Lark
  record-id map), and, only with `--execute`, Lark Base rows through
  `lark-cli`.
- Write owner: the operator-triggered CLI. Agents append result events; only
  an explicit `--execute` run touches the shared Lark surface.
- Proof of transition: every sync payload lists the exact `lark-cli` commands
  it ran or would run, per-row record ids, and the refreshed record map that
  the next sync reuses.

## Result Event Model

One JSONL event per line, `loopx_explore_result_event_v0`, three kinds:

| Kind | Identity | Purpose |
| --- | --- | --- |
| `node` | `--node-id` (or derived from title) | An explored question, area, hypothesis, experiment, or artifact. Status: `open`, `exploring`, `blocked` (requires `--blocked-reason`), `resolved`, `dead_end`. Re-record the same id to update it. |
| `edge` | derived from `from/type/to` | Typed relation: `subtopic_of`, `depends_on`, `answers`, `supports`, `refutes`, `leads_to`. |
| `finding` | `--finding-id` (or derived from title) | A discovery, optionally attached to a node. Status: `tentative`, `confirmed`, `refuted`. |

Events are sanitized at record time: compact text limits, credential-like
markers rejected, and evidence refs must be public relative refs or opaque ids
(for example `ov:doc:lustre-survey`), never local absolute paths.

## Projection And Topology

`loopx explore summary` folds the log into
`loopx_explore_result_projection_v0`: latest state per node/edge/finding,
status counts, the blocked list with reasons, the exploring frontier, a
parent/`subtopic_of` topology tree, and Mermaid flowchart source.
`loopx explore graph --graph-format mermaid|json [--out <file>]` exports the
topology for a Feishu doc, whiteboard, or any Mermaid renderer.

## Lark Mapping

| LoopX concept | Lark surface |
| --- | --- |
| node | `Nodes` table row keyed by `LoopX Result ID`; `Status=blocked` rows carry `Blocked Reason` |
| edge | `Edges` table row keyed by `LoopX Result ID`; `From Node Link` and `To Node Link` are linked-record cells pointing at `Nodes`, so the Base data model itself carries the topology |
| finding | `Findings` table row keyed by `LoopX Result ID`; latest event wins |
| row lineage | `Row Lifecycle`, `Supersedes`, `Superseded By`, `Source ID` columns |
| dashboard card | transport-free interactive card content from the same projection |

Record identity follows the Lark Kanban adapter contract: rows are matched by
the `LoopX Goal ID` + `LoopX Result ID` columns, remembered in the local
config as `result_records`, and the map is rebuilt from the remote table
before executed upserts.

The text `From Node` / `To Node` columns remain stable public ids for
automation and review, while the linked-record columns are the Feishu-native
graph substrate. A Base plugin, relationship-aware view, or Feishu dashboard
component can read those links directly; LoopX must not downgrade the graph
back to a screenshot-only artifact.

## CLI Surface

```text
loopx explore schema
loopx explore node --goal-id <id> --title <t> [--node-id ...] [--status ...] [--blocked-reason ...] [--parent ...]
loopx explore edge --goal-id <id> --from <node> --to <node> --type <edge-type>
loopx explore finding --goal-id <id> --title <t> [--node ...] [--status ...] [--confidence ...]
loopx explore summary --goal-id <id>
loopx explore graph --goal-id <id> [--graph-format mermaid|json] [--out <file>]
loopx explore feishu-setup [--base-url ...] [--execute]
loopx explore feishu-sync --goal-id <id> [--sink-visibility owner-only|shared] [--execute]
loopx explore feishu-card --goal-id <id> [--card-file <file>] [--message-id om_...]
```

`feishu-setup` and `feishu-sync` are dry-run unless `--execute` is set; the
dry-run payload contains the full command plan for review.

## Review Boundary

Rows and cards deliberately exclude raw agent transcripts, worker commands,
credentials, and local absolute paths. Evidence lives behind compact public
refs; the private material itself stays in the goal's normal local state or
memory backend. `--sink-visibility shared` additionally redacts private
links and external ids through the shared Kanban redaction rules before rows
leave the machine. Card content is build-only: sending or updating the actual
Lark message is the job of an approved gateway (bot or lark-cli) after the
operator permits the write.

## Validation

```bash
python3 examples/explore-result-layer-smoke.py
```

The smoke proves the projection contract (folding, blocked reasons, tree,
Mermaid), record-time path rejection, dry-run default, idempotent second sync
by remembered record id, shared-visibility redaction, transport-free card
content, and the CLI surface against a temp registry, without live Lark
credentials.
