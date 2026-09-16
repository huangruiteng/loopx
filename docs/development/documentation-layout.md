# Documentation Layout And Migration Policy

LoopX documentation serves several audiences: people trying the product,
operators running long-lived goals, contributors changing the control plane,
and maintainers inspecting protocols or research evidence. This policy keeps
those paths distinct without hiding useful material or breaking stable links
for cosmetic reasons.

## Target Information Architecture

| Path | Owns | Does not own |
| --- | --- | --- |
| `docs/guides/` | Task-oriented onboarding and operator walkthroughs | Product strategy or machine contracts |
| `docs/concepts/` | Explanations of durable LoopX concepts and mental models | Step-by-step operations |
| `docs/operations/` | Goal, todo, cadence, attention, and authority workflows | Provider-specific implementation details |
| `docs/architecture/` | System boundaries, design decisions, and RFCs | Current CLI reference |
| `docs/product/` | Product direction, runtime experiences, surfaces, and use cases | Protocol definitions |
| `docs/integrations/` | Runtime, host, collaboration, and external-system adapters | Core control-plane semantics |
| `docs/reference/contracts/` | Stable human-readable contracts | Exploratory proposals |
| `docs/reference/protocols/` | Versioned, implementation-oriented protocols | Narrative product direction |
| `docs/development/` | Contributor workflows, testing, and repository policy | End-user onboarding |
| `docs/showcases/` | Public-safe cases and reproducible demonstrations | Raw private evidence |
| `docs/research/` | Public research, benchmark evidence, and route packets | Stable first-line documentation |
| `docs/archive/` | Superseded or dated records kept for historical value | Active guidance |

The `docs/` root is a compatibility surface, not the default destination for
new files. It should contain the documentation home and a small set of stable,
high-traffic anchors. New material belongs in the narrowest owning directory.

## Coverage Map

The repository currently has useful material in every target category, but
three areas are overloaded:

| Current surface | Current problem | Migration treatment |
| --- | --- | --- |
| `docs/README.md` | Mixes onboarding, reference, product direction, research, and governance in one long list | Replace with a short audience-and-task router; preserve links through category indexes |
| `docs/*.md` | Concepts, contracts, integrations, operations, and roadmaps share one flat namespace | Keep only proven stable anchors; move lower-traffic files by owner and repair inbound links |
| `docs/product/*.md` | Runtime experiments, product foundations, surfaces, and use cases are interleaved | Group under `foundations/`, `runtimes/`, `surfaces/`, and `use-cases/` |
| `docs/reference/protocols/*.md` | Versioned contracts are flat and hard to scan | First group the index by domain; move files only with a separate protocol-path compatibility review |
| `benchmark/` | Current benchmark research needs a small RFC-linked home outside product packages | Keep protocols and public-safe practice here; place retired implementations and immutable experiment snapshots according to the canonical [archive placement rules](../../benchmark/README.md#archive-placement) |

This is a coverage-preserving migration. Unique claims, public evidence, and
useful links must either remain at their current path or appear in a new
canonical index. A shorter landing page is not permission to delete material.

## Stable Root Anchors

The first migration keeps these high-traffic paths stable:

- `docs/architecture.md`
- `docs/integration.md`
- `docs/state-interaction-model.md`
- `docs/status-data-contract.md`
- `docs/quota-allocation.md`
- `docs/heartbeat-automation-prompt.md`
- `docs/project-agent-todo-contract.md`
- `docs/public-private-boundary.md`

Their location can be reconsidered only when there is concrete evidence that
callers have migrated or a real compatibility mechanism exists. GitHub does
not provide transparent Markdown redirects, so creating a prettier tree is not
enough reason to break a widely linked path.

## Migration Rules

1. **Move by ownership, not by filename similarity.** A document belongs where
   its future changes will be reviewed, not where its title happens to fit.
2. **Preserve unique information.** Build a before/after coverage map for each
   index and keep every still-valid claim and public link reachable.
3. **Repair every repository caller.** Update Markdown links, examples, smokes,
   source comments, and generated navigation in the same change as a move.
4. **Treat external compatibility explicitly.** Keep a stable path when it is
   part of public onboarding, release notes, protocol documentation, or common
   contributor links. Do not leave dozens of placeholder files merely to make
   a directory look empty.
5. **Keep indexes selective.** A category index explains what belongs there
   and highlights canonical entry points. It is not required to repeat every
   historical filename.
6. **Separate current truth from evidence.** Stable guidance links to evidence;
   research packets do not become first-line operational instructions.
7. **Fail closed on private material.** Internal conversations, personal
   attribution, private URLs, local paths, credentials, raw transcripts, and
   permission diagnostics do not enter public docs.
8. **Validate the rendered path.** Check relative links, anchors, Mermaid, and
   the first visible section of changed landing pages before delivery.

## Staged Migration

### Stage 1: Navigation And Obvious Ownership

- add short indexes for architecture, concepts, operations, integrations, and
  product subdomains;
- publish public-safe RFCs below `docs/architecture/rfcs/`;
- move low-traffic root files whose owner is unambiguous;
- group product documents by foundations, runtime, surface, and use case;
- keep stable root anchors in place;
- add focused relative-link validation.

### Stage 2: Protocol Discovery

- group the protocol index by control plane, runtime integration, domain
  capability, evidence, and release/quality;
- inventory code and external references before moving any versioned protocol;
- keep protocol filenames and version suffixes stable.

### Stage 3: Research Lifecycle

- provide topic indexes for active findings, reusable evidence, dated packets,
  and archived decisions;
- keep source-backed artifacts inspectable;
- archive superseded packets without rewriting history.

## Placement Checklist

Before adding a public document, answer:

1. Who is expected to act after reading it?
2. Is it guidance, a concept, a product decision, a protocol, evidence, or a
   historical record?
3. Which existing index owns that reader and change reason?
4. Does the document contain only public-safe sources and examples?
5. What focused validation proves its links and presentation remain usable?

If no category owns the document, refine its purpose before creating another
top-level file.
