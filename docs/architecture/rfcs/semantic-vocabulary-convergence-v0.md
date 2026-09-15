# RFC: Semantic Vocabulary Convergence and Commit-Time Drift Checks (v0)

- **RFC status:** Draft
- **Delivery maturity:** Partial (M0 registry, generated inventory, and drift smoke ship with this RFC)
- **Authors / owners:** LoopX contributors; control-plane kernel maintainers own approval
- **Created:** 2026-09-15
- **Last normative revision:** 2026-09-15
- **Implementation baseline:** `1dc6ad8d8`
- **Related contracts:** `loopx/semantics/vocabulary_v0.json`,
  `loopx/semantics/inventory_v0.json`,
  `loopx/control_plane/turn_transaction_contract.json`,
  `loopx/control_plane/coordination/coordination_state_contract_v0.json`,
  [Turn Envelope v0](../../reference/protocols/turn-envelope-v0.md),
  [Turn Loop Controller v0](../../reference/protocols/turn-loop-controller-v0.md),
  [TypeScript Control-Plane Migration v0](typescript-control-plane-migration-v0.md)
- **Language mirror:** [中文版](https://github.com/huangruiteng/loopx/blob/main/docs/architecture/rfcs/semantic-vocabulary-convergence-v0.zh-CN.md)

## Document map and maintenance contract

This RFC ships an English document and a `semantic-vocabulary-convergence-v0.zh-CN.md`
semantic mirror; both carry a language link and must be revised together when a
normative section changes.

- Sections 1-10 are the durable design and acceptance contract.
- Section 11 is the normative delivery plan.
- Section 12 contains unresolved decisions; proposed answers are not approval.
- Appendices hold the non-normative execution ledger, decision log, evidence
  registry, and rejected alternatives.

RFC maturity and delivery maturity are independent. Dated progress entries do
not amend normative sections.

---

## 1. Decision summary

1. **What becomes authoritative.** Two files under `loopx/semantics/`. The
   curated registry `vocabulary_v0.json` names each kernel and cross-runtime
   vocabulary, the exact `module::Symbol` allowed to define it, the relations
   between vocabularies (same concept, shared field name, subset), the total
   projections, and the budgets the repository ratchets down. The generated
   inventory `inventory_v0.json` maps every closed-set carrier under `loopx/`:
   string enums, `Literal` aliases, named closed sets, TypeScript `as const`
   arrays, and every constant name defined in more than one module. A public
   smoke, `examples/semantic-vocabulary-drift-smoke.py`, checks the code against
   both inside the default `pytest` sweep on every pull request; premerge and
   the full-public fleet are additional surfaces (Section 10). A change that widens a
   vocabulary, forks a constant, adds a carrier, or weakens the registry must
   edit the registry or regenerate the inventory in the same diff, so the
   reviewer sees the semantic change as a change.
2. **What remains unchanged.** Runtime behavior, wire formats, and the enum
   classes themselves. Each enum keeps living in its owner module; the registry
   is checked against code by AST and text scan, it does not generate code and
   product code never imports it.
3. **Default and opt-in boundary.** The check is always on for the repository.
   It has no runtime flag because it never runs inside the product.
4. **Principal constraint.** Fail closed, deterministic, and not weakenable by
   a data edit alone. An unregistered literal in either runtime, a second
   defining module, a budget overrun, a registry value no module carries, a
   stale inventory, an owner declared without a symbol, or a coverage count
   below the recorded floor each fails the smoke. The dispatch forms the scan
   recognises live in the smoke, not in the registry. The smoke reads only
   tracked sources and prints no private data.
5. **Not approved by this RFC.** Merging the three Turn outcome enums into one,
   splitting the three `effective_action` slots, deleting any legacy should-run
   field, deleting any Python twin module, or renaming any existing value.
   Those are later milestones with their own gates under the schema-reduction
   rule in `AGENTS.md`.

## 2. Problem and motivation

LoopX has grown by many small agent-driven PRs. Each PR added the vocabulary it
needed where it needed it. The result is not wrong behavior but drift: the same
concept spelled several ways, the same constant defined in several files, the
same field name carrying different vocabularies, and open string sets that any
module may widen without anyone noticing. Reviewers cannot tell from a diff
whether a new literal is a new state or a typo, and documentation cannot stay
in step with a set nobody enumerates.

The semantic surface is repository-wide, not a Turn-kernel problem. Measured on
the baseline by the inventory generator over 1169 source files under `loopx/`:

| Carrier | Count | Notes |
| --- | --- | --- |
| Python string enums | 102 | 29 in the control plane, 17 in capabilities, 6 in extensions |
| Named closed sets (`NAME = frozenset/tuple` of strings) | 490 | 66 are field lists, 31 kinds, 31 states, 29 statuses |
| `Literal[...]` aliases | 8 | |
| TypeScript `as const` arrays | 40 | 21 have an equal Python set; 14 have none |
| Named string constants | 2002 | 754 are `*_SCHEMA_VERSION` |
| Same name, same value, two runtimes | 166 | legitimate py/ts twins |
| Same name, same value, one runtime | 25 names / 58 definitions | forks; 7 are schema versions |
| Same name, different values | 18 names / 59 definitions | see below |

Concrete failures audited on the baseline:

- `TURN_ENVELOPE_SCHEMA_VERSION` was defined three times:
  `loopx/control_plane/quota/turn_envelope.py:16`,
  `loopx/control_plane/quota/turn_envelope.ts:13`, and a private copy in
  `loopx/control_plane/turn_driver/driver.py:31`. M0 removes the copy.
- `HANDOFF_MODES` was defined by the TypeScript owner and again as a literal
  tuple in `control_plane/testing/authority_e2e_fixtures.py:33`. M0 derives the
  fixture tuple from the `HandoffMode` enum.
- The same value set carries two names across runtimes:
  `MATERIAL_DELIVERY_OUTCOMES` in `work_items/delivery_outcome.ts` equals
  `VISION_OUTCOME_CHECKPOINT_MATERIAL_OUTCOMES` in
  `goals/goal_frontier/outcome_continuity.py`. Both equal `DeliveryOutcome`
  minus `surface_only`; nothing said so.
- Conflicting definitions with the same name: `DECISION_CONTEXT_CAPABILITY_ID`
  is `decision_context` in `capabilities/decision_context/packets.py:18` and
  `decision-context` in `extension_provider.py:24`; `MCP_REQUIREMENT` is
  `mcp==1.28.1` in `kunluncode_goal_mode/cli.py:28` and `mcp<2` in
  `claude_goal_mode/scripts/install.py:83`. Sixteen further names are generic
  module-local constants (`SCHEMA_VERSION`, `COMMAND`, `CAPABILITY_ID`) whose
  collision is harmless today and invisible tomorrow.
- The Turn result kinds exist twice by hand: `LoopXTurnResultKind` in
  `transaction.py:28` and `TURN_RESULT_KINDS` in `settlement.ts:49`. They
  match; no test asserted it. The same holds for eleven other py/ts pairs
  (settlement step, binding and failure kinds, receipt-bound phases, scheduler
  transitions, Todo completion continuation and recovery, delivery outcome,
  delivery workspace kinds, Goal amendment classes, Todo decision scopes).
- `effective_action` is an open string set with no enum on either runtime.
  Thirty-one distinct literals are dispatched on by string comparison in
  Python and TypeScript. Two of them (`observe_replay`, `block_replay`) are
  written by `turn_journal.ts:656` into the replay observation slot of the
  Turn Envelope and are not should-run verdicts at all. Two more
  (`quota_action_selection_deferred`, `quota_action_selection_rejected`) are
  quota error codes that `cli_commands/quota.py:279` copies into the slot.
  `AgentScopeFrontierAction` values are written into the
  `agent_scope_frontier.effective_action` slot of the same envelope. One field
  name, three vocabularies. `user_gate.py:162` compares the slot against
  `skip`, which no producer writes.
- Three near-isomorphic Turn outcome vocabularies coexist:
  `LoopXTurnResultKind` (12), `LoopXTurnRoute` (8), `LoopDisposition` (8),
  with `repair`/`repair_required` and `replan`/`replan_required` as different
  spellings of one verdict. The route-to-disposition projection is a private
  dictionary in `loop_controller.py:126`; nothing declared that it is total.
  The load-bearing table in `decide_loop_disposition` (result kind, retryable,
  attempt budget, decision user action, durable no-follow-up) exists only as
  prose in the controller protocol document.
- Six should-run decision fields the documentation already calls legacy are
  still mentioned by 7 to 35 Python modules each, with no ratchet stopping new
  consumers.
- 43 same-basename `.py`/`.ts` module pairs exist under `loopx/control_plane`
  while the migration RFC is replacement-first. The count had no guard.
- The repository already runs an AST-backed control-plane debt ratchet
  (`loopx/canary/maintainability_ratchet.py`) with a reviewed exception
  lifecycle, but it measures module metrics and dependency direction, not
  vocabulary shape. Vocabulary drift had no ratchet.

The current owners cannot solve this locally because every fix is
cross-module by definition: the Turn driver, quota, todos, capabilities, and
the TypeScript runtime each own one spelling of the same idea.

### Invariants

- **I1 Single owner.** Every registered vocabulary or constant has exactly the
  defining modules the registry lists, and the registered symbol name is
  defined nowhere else under `loopx/`. Everyone else imports.
- **I2 Closed sets.** Every value a registered vocabulary may carry is listed.
  The code carries no unregistered value in either runtime and the registry
  lists no value the code does not carry.
- **I3 Cross-runtime parity.** When a vocabulary has a Python and a TypeScript
  owner, both carry the identical set.
- **I4 Total projections.** A registered projection names every source value
  exactly once, either mapping it or declaring it rejected.
- **I5 Ratchets only fall.** Retirement, twin, and inventory budgets may be
  lowered in any PR. Each budget is additionally pinned by a `BUDGET_ANCHOR`
  (or `RETIREMENT_ANCHOR`) literal inside the smoke, and each floor by a
  `COVERAGE_ANCHOR`, following the `RFC_MODULE_BUDGETS` anchor pattern in
  `tests/control_plane/test_m6_quality_gates.py`, with one deliberate
  difference: the registry value must **equal** the anchor. The precedent
  compares with `<=`, which lets a budget tightened below the anchor be raised
  back to the anchor later without any code edit. Equality makes every
  tightening a two-file diff and every loosening a code edit a reviewer sees.
- **I6 Same-diff visibility.** A semantic change and its registry edit or
  inventory regeneration land in one reviewable diff.
- **I7 Deterministic and public-safe.** The check reads tracked sources only,
  needs no network or credentials, and its failure text names files and
  values, never private data.
- **I8 Coverage only grows.** The number of registered vocabularies, owner
  symbols, projections, relations, schema versions, and scanned suffixes is
  recorded as a floor. An owner is `module::Symbol` or `null`; a bare module
  path is rejected, and a null owner requires a literal scan. The dispatch
  forms the scan recognises are fixed in the smoke. A registry edit therefore
  cannot silently narrow what the guard sees.
- **I9 Both carrier shapes are measured.** A vocabulary reaches the code either
  as a string constant (`NAME = "value"`) or as a multi-value carrier (an enum,
  a named closed set, a `Literal` alias, a TypeScript `as const` array). Both
  get the same collision rule: one name defined in two modules with identical
  values is a twin, with different values a fork. Collision budgets count the
  shared-vocabulary subset only; module-local convention names such as
  `SCHEMA_VERSION`, `COMMAND`, or `*_LABEL` stay visible in the inventory totals
  but are not drift.
- **I10 On the pull-request path.** The drift smoke runs inside the default
  `pytest` sweep through `tests/architecture/test_semantic_vocabulary_drift.py`,
  so it fails closed on every pull request that runs the Python tests. Fleet
  discovery under `examples/` and the `repo-architecture-budget` premerge
  profile are additional surfaces, not the obligation: the fleet runs after
  merge and on a schedule, and premerge selects by changed-path tokens.
- **I11 Roles are distinct.** A vocabulary has one owner, some producers, some
  interpreters, and some pass-throughs (Section 5, "Roles of a vocabulary").
  Only the owner defines the set and only producers write values. Mentioning,
  comparing, serializing, or displaying a value confers no ownership. An
  interpreter or pass-through that starts writing a value has become a
  producer and must be registered as one. Enforced from M0.5.
- **I12 Every kernel value is produced.** For a `kernel` vocabulary, every
  value not listed under `compatibility_only` has at least one production site
  the fixed production forms recognise or a `variable_sourced_values` entry. A
  value that is only compared is dead or compatibility-only, never canonical.
  `skip` in `effective_action` is the first expected failure. Enforced from
  M0.5; at M0 the literal scan accepts a compared value as carried.
- **I13 Producers write registered values only.** A production site that
  writes a value outside the registered set fails closed, independently of
  whether any consumer compares it. Production is stricter than comparison: a
  consumer comparing an unregistered value is dead code, a producer writing one
  is protocol drift. Enforced from M0.5; the M0 literal scan covers both forms
  together.
- **I14 Scope is declared, not inferred.** A name defined in several modules
  is a fork unless the registry declares it `bounded_context` and lists the
  contexts and one owner symbol per context. Declared names leave the fork
  budget; a rename does not change the budget's meaning and is not a fix.
  Enforced from M0.5; at M0 `SOURCE_SURFACES` is counted as a fork and noted.

## 3. Scope and non-goals

### In scope

- The registry file, its schema, and the ownership rule for editing it.
- The generated inventory, its generator with `--check`, and its unit test.
- The drift smoke and its placement in the premerge and full-public fleets.
- The vocabularies registered at M0: the four Turn-kernel sets
  (`turn_result_kind`, `turn_route`, `loop_disposition`, `effective_action`),
  `agent_scope_frontier_action` and `lease_action`, and twenty cross-runtime
  sets whose Python and TypeScript owners carry equal values on the baseline;
  the route-to-disposition projection; nine relations; the Turn Envelope schema
  version; the six legacy should-run fields; the control-plane twin count; and
  the inventory fork and conflict budgets.
- The later milestones that turn `effective_action` into a typed enum, split
  its three slots, publish the projection through the contract, and retire
  legacy fields and twins under existing repository rules.
- The scan root is the `loopx/` package. "Repository-wide" in this RFC means
  every carrier under `loopx/`, in both runtimes, not every file in the git
  tree. The inventory `root` and every `literal_scan.roots` entry say `loopx`
  and the smoke reads nothing else.

### Non-goals

- Changing any runtime decision, payload shape, or wire format.
- Scanning `apps/` (about 90 TypeScript files on the baseline) or `examples/`
  (a dozen `effective_action` assertions in smokes). Those are consumers and
  test doubles, not producers; a smoke that asserts an unregistered value is
  invisible to M0 and is accepted as such until a milestone widens the root,
  which would also raise the merge-order cost in Section 10.
- Curating every closed set by hand. The inventory maps all of them; only
  vocabularies that cross a module or runtime boundary and are dispatched on
  are curated with owners, values, and relations.
- Replacing `turn_transaction_contract.json` or
  `coordination_state_contract_v0.json`. Those remain the owners of their
  phases and records; this registry may reference them, not restate them.
- Replacing `maintainability_ratchet.py`. It owns module metrics and dependency
  direction; this registry owns vocabulary shape. Whether their exception
  lifecycles merge is Section 12, Q7.
- A prose glossary as the enforcement mechanism. A glossary is a useful
  companion and is tracked in Section 12, but it cannot fail a build.

## 4. Current-system contract

Facts on baseline `1dc6ad8d8`:

- `turn_transaction_contract.json` is the one contract read by both runtimes:
  `effect_program.py:160-166` loads the phase tuple and
  `turn_journal.ts:1` imports the JSON. This is the template the registry
  follows for a shared source of truth.
- `coordination_state_contract_v0.json` goes further and generates
  `coordination_state_contract_generated.py` and
  `coordination_state_contract.generated.ts` through
  `scripts/generate_coordination_state_contract.py --check`, guarded by
  `tests/control_plane/test_coordination_state_contract.py`. This is the
  template the inventory generator follows now and the generation stage
  proposed in M2 follows later.
- The canary runner discovers every tracked `examples/**/*-smoke.py`
  (`loopx/canary/runner.py:392`), so a smoke at `examples/` needs no
  registration in `planner.py` or `premerge.py`.
- `loopx/canary/maintainability_ratchet.py` is the existing AST-backed
  control-plane debt ratchet. It carries reviewed exceptions with a
  `retirement_plan` and detects stale exception ids. Its subject is module
  size, `Any` density, decision-point counts, and forbidden dependency
  direction; it does not read enum or constant values.
- `AGENTS.md` already requires typed enums for state classification, forbids a
  second source of truth in Python for control-plane authority, requires a
  scope-fit review before adding a module, and requires maintainer approval for
  any schema reduction. This RFC adds the check that makes those rules
  observable in a diff; it does not change them.
- Package data for `loopx.control_plane` already ships `*.json`;
  `pyproject.toml` gains one line so `loopx.semantics` ships its two JSON files
  the same way.

## 5. Proposed architecture

### Ownership and authority

The registry is owned by the control-plane kernel maintainers. Any contributor
may lower a budget or add a value together with the code that carries it. Only
a maintainer may approve raising a budget, removing a value, or moving an owner
module, and the approval is recorded in Appendix B.

Forbidden alternate authorities: a second registry, a per-module list that
restates registered values, or a prose table that claims to be normative for a
registered vocabulary.

**Scope of a name (planned for M0.5, not in M0).** The collision rules are
keyed by name, so they cannot tell a fork from four bounded contexts that
happen to reuse one identifier. `SOURCE_SURFACES` is the first case: its four
definitions in `global_risks.py`, `global_todos.py`, `summary_all.py`, and
`pr_review.py` each list the data sources of that one CLI command, and the
value sets are meant to differ. It is counted in `multi_value_forks` today and
must not be "fixed" by renaming, because a rename lowers the number without
changing the code's meaning. The M0.5 scope slice adds top-level `scope_declarations` with at
least `global` and `bounded_context`; a bounded-context name is declared once
with its owning contexts, and declared names are removed from the semantic
fork budget while the raw inventory count remains visible (I14, the schema rows below, and the M0.5 row in Section 11). Until
then the fork budget is a ceiling that contains this one known
misclassification, recorded in the registry's `inventory_ratchets` note.

### Roles of a vocabulary

A module that mentions a value is not its owner, and a vocabulary has more
than one kind of participant. Consumer is the umbrella role for code that reads
or accepts a value; interpreter and pass-through are its two tracked subroles.
The registry distinguishes these roles because the check that makes sense differs
by role:

| Role | What it does | Registered | Check |
| --- | --- | --- | --- |
| Owner | Defines the closed set as one `module::Symbol` per runtime | Yes, since M0 | I1 to I3 |
| Producer | Writes a value into the field: assignment, dict or object literal, constructor keyword, `return` of a literal inside a listed deciding function, enum member on the owner | Yes for `kernel` vocabularies, from M0.5 | I12, I13 |
| Consumer | Reads or accepts a vocabulary value; this is the umbrella role for interpreters and pass-throughs | Usually no; relation is reported rather than curated | F3 |
| Interpreter | Consumer that branches on or maps the value: `if`, `match`, `switch`, membership test | No; found by the dispatch scan, ranked by `--report` | I2, F3 |
| Pass-through | Consumer that serializes, persists, forwards, or displays the value without changing its meaning | No | F3; persistence also needs F6 evidence |

Two rules follow. A value with no producer is dead or compatibility-only:
`skip` is compared in `todos/user_gate.py` and written nowhere, so M0 passes
it and M0.5 fails it until it is removed or listed under `compatibility_only`.
Production is stricter than comparison: M0.5 scans production forms on their
own and fails on an unregistered produced value (I13), while the M0 literal
scan keeps catching unregistered comparisons (I2). Interpreters and
pass-throughs are deliberately not registered; otherwise every consumer edit
would touch the registry, the churn Section 6 rejected for consumer counts.
Their relations to a vocabulary are advisory output of `--report`.

Production forms are fixed in the smoke at M0.5, like the dispatch forms:
Python `x["f"] = "v"`, `f="v"` as a constructor keyword of the envelope or
packet type, `return "v"` inside a function the registry lists as a producer,
and member access on the owner enum; TypeScript `f: "v"` in an object
literal, `x.f = "v"`, and the conditional expression. `variable_sourced_values`
stays for the values a producer builds from a variable the scan cannot follow.
Which vocabularies must list producers: `kernel` at M0.5; `cross_runtime` only
when a value is added or removed after M0.5; `cross_module` only if promoted
(Q8). Persistence is a property the production scan can answer: a producer
whose listed symbol is a journal or receipt writer marks the vocabulary
`persisted`, which is the fact Q2 and Q10 wait on.

### Formal model and proof boundary

The registry is a finite specification of a larger program semantics. Let
`V` be the set of registered vocabularies, `Val(v)` the admitted values of a
vocabulary `v`, and `S` the set of source sites. The model records relations,
not just names:

```text
D ⊆ S × V                         defines
P ⊆ S × V × Val(v)                produces
C ⊆ S × V × Val(v)                consumes or branches on
I ⊆ S × V × V                     interprets one vocabulary as another
T ⊆ S × V                         passes through without changing meaning
G ⊆ V × V × (Val ⇀ Val ∪ {reject}) projects
R ⊆ S × V × Version               persists a value durably
```

The minimum semantic obligations are:

1. **Producer closedness:** `Produced(v) ⊆ Val(v)`. A recognised producer
   cannot write a value outside the registered set.
2. **Canonical liveness:** `Canonical(v) ⊆ Produced(v) ∪ CompatibilityOnly(v)`.
   A value that is only compared is dead or compatibility-only, never
   canonical.
3. **Consumer domain closedness:** `Accepted(c) ⊆ Val(v)`, unless the consumer
   explicitly declares an external or partial domain.
4. **Scope separation:** a name collision is a semantic conflict only when the
   declared scopes overlap. Spelling alone cannot establish equivalence.
5. **Projection totality:** for every source value, a projection maps to a
   target value or explicit `reject`.
6. **Persistence compatibility:** a persisted vocabulary change preserves all
   readers or declares a versioned migration.

These are different proof obligations. M0 establishes owner-set equality,
cross-runtime parity, the declared executable projection, and inventory
freshness. Fixed literal forms and closed-set carriers provide bounded evidence,
not whole-program proof. M0.5 adds bounded producer and scope checks. Producer
discovery over dynamic code, behavioural equivalence of `same_concept`, and
persisted-reader compatibility remain unproved until their source-to-sink
edges are modelled. The registry stores this proof boundary in
`formal_model`; an `unproved` property is an explicit limitation, never an
implicit pass.


### State model and schema

`loopx/semantics/vocabulary_v0.json`, `schema_version`
`loopx_semantic_vocabulary_v0`. The key set is closed; an unknown top-level or
vocabulary key fails the smoke.

| Key | Content | Check |
| --- | --- | --- |
| `coverage_floor` | counts of vocabularies, owner symbols, literal-scan fields, projections, relations, schema versions; the scanned suffix set | Actual counts are at or above the floor, declared suffixes cover the floor set, and each floor equals its `COVERAGE_ANCHOR` (I8) |
| `vocabularies.<name>.owners` | `python` and `typescript`, each `path::Symbol` or `null` | Enum members, closed-set members, `Literal` alias, or `as const` array equal `values`; the symbol is defined only in owner modules (I1, I2, I3) |
| `vocabularies.<name>.tier`, `status` | `kernel`, `cross_runtime`, `cross_module`; `canonical`, `legacy`, `merge_candidate` | Closed enumerations |
| `vocabularies.<name>.literal_scan` | `field`, roots, suffixes | Every literal the fixed dispatch forms capture is registered; every registered value is captured or variable-sourced (I2) |
| `vocabularies.<name>.variable_sourced_values` | value to producer module | The producer still contains the quoted value |
| `scope_declarations.<name>` (M0.5a) | `bounded_context` and its context IDs, each with one `module::Symbol` owner | Every declared name resolves to one inventory fork, names every defining module exactly once, and is excluded only from `multi_value_forks_semantic`; undeclared forks remain visible (I14) |
| `vocabularies.<name>.producers` (M0.5) | `path::Symbol` sites that write the field, required for `kernel` | Every site writes registered values only; every value not under `compatibility_only` has at least one site or a variable-sourced entry (I12, I13) |
| `vocabularies.<name>.compatibility_only` (M0.5) | values kept so readers of persisted records still resolve them | Subset of `values`; zero production sites; each carries a `value_notes` reason and a retirement milestone |
| `formal_model` | finite universes, role relations and hierarchy, semantic obligations, and established/bounded/unproved claims | Exact schema, role hierarchy, and invariant ids are checked by the drift smoke; enforcement stages cannot be mistaken for completed proofs |
| `formal_model.enforcement_policy` | blocking-now, blocking-next, advisory, and unproved lanes | Every formal invariant appears exactly once and its lane agrees with its enforcement stage |
| `vocabularies.<name>.value_notes`, `deprecated_values` | per-value review notes; values slated for removal | Names must be registered values |
| `relations.same_concept` | groups of `vocabulary.value` members | Every member resolves |
| `relations.shared_field_names` | one field name, its slots and the vocabulary or values each carries | Every slot resolves |
| `relations.subsets` | superset vocabulary, excluded values, owners of the subset symbol | Owner symbols equal superset minus excluded |
| `projections.<name>.mapping` | source value to target value or `null` | Keys equal the source vocabulary; mapped values match the owner function; `null` routes raise (I4) |
| `schema_versions.<name>` | constant name, value, owner modules | The only defining modules are the listed owners and all carry the value (I1) |
| `retirement_ledger.<group>.fields` | per-field Python and TypeScript module budgets | Actual module counts are at or below budget, and the field set and every budget match `RETIREMENT_ANCHOR` (I5) |
| `dual_runtime_twins` | root and module budget | Tracked same-basename `.py`/`.ts` pair count is at or below budget; root and budget equal their code anchors (I5) |
| `inventory_ratchets` | budgets for same-runtime fork names and definitions, conflicting names and definitions, schema-version forks, multi-value twins and forks, and the shared-vocabulary conflict and fork subsets | Inventory summary counts are at or below budget, and each budget equals its `BUDGET_ANCHOR` entry (I5, I9) |

`loopx/semantics/inventory_v0.json`, `schema_version`
`loopx_semantic_inventory_v0`, is generated by
`scripts/generate_semantic_inventory.py` and must equal a fresh build. It
lists Python enums, closed sets, `Literal` aliases, TypeScript `as const`
arrays, and duplicate definitions split into cross-runtime twins, same-runtime
forks, conflicting values, and multi-value twins and forks, one entry per line.
Every multi-value collision carries each defining module and its value set, so
the divergence itself is reviewable rather than only its count. Consumer counts are printed by `--report`; merge-candidate groups are available
through `merge_candidate_groups` and not committed, so an
ordinary consumer edit does not touch the file; merge candidates are advisory
because an equal value set is not proof of one concept. Single-module string
constants are counted, not listed.

Values are additive. Removing a value, a field, an owner, or a relation is a
schema reduction and follows the `AGENTS.md` rule: enumerate the affected
surfaces, research producers and readers, lower the floor in the same diff, and
record maintainer approval.

### Command or event lifecycle

The check has one command: run the smoke. It is idempotent and has no side
effects. Failure text names the vocabulary, the offending files, and the values
so the fix is mechanical: register the value, import the constant, or lower the
scope of the change.

### Provider or extension contract

New vocabularies are added by a PR that adds the registry entry, raises the
coverage floor, and, where a TypeScript owner exists, names its `as const`
array. A vocabulary qualifies for curation when it is dispatched on by more
than one module or crosses the Python/TypeScript boundary; everything else is
mapped by the inventory without curation. Adding any carrier regenerates the
inventory in the same PR.

## 6. Alternatives and design choices

| Alternative | Why not now |
| --- | --- |
| Unify the three Turn enums into one in a single PR | Breaks I5 style incrementalism; the three enums have different owners and change reasons (settlement, route, controller). Register and project first, then merge only where a projection proves identity (Section 12, Q2). |
| Rely on `mypy` `Literal` types | Does not cover TypeScript, JSON payloads, or the CLI; the drift here lives at exactly those boundaries. |
| Documentation glossary only | Cannot fail a build; the repository already has eleven documents calling themselves a mental model and no glossary, which is the symptom. |
| Generate bindings from the registry immediately | Premature until owners are settled. Generation is M2 and follows the coordination contract precedent. |
| Grep-based lint in CI without a registry | Encodes the allowed set in the linter, which becomes a second registry with no review trail. |
| Extend `maintainability_ratchet.py` instead of a new registry | Its subject is module metrics and dependency direction with per-module ceilings; vocabulary shape needs values, owners, and relations. The two share the ratchet idea, not the data model. Merging exception lifecycles is Q7. |
| Put the scan regex in the registry | A regex in data can be narrowed in the same edit that widens a vocabulary; the M0 review showed the first pattern missed every TypeScript `===` site. Forms are fixed in the smoke and the suffix set is floored. |
| Commit consumer counts in the inventory | Every consumer edit would churn the file and make the freshness check noise. Counts stay advisory via `--report`. |

## 7. Safety, privacy, and compatibility

- No runtime path imports the registry at M0; product behavior is unchanged
  with the check present or absent.
- The scanner uses `git ls-files --cached -z` and reads the indexed source paths
  from the working tree. Untracked and ignored files are excluded; stage a new
  source path before regenerating the inventory. Tracked symlinks and invalid
  Python syntax fail closed. A checkout with Git metadata is required.
- Literal and TypeScript carrier scans recognize both single and double quotes.
  They remain structural text scans, not complete parsers or data-flow analysis.
- Literal-scan roots and suffixes, and the twin root and budget, are anchored in
  code. JSON alone cannot narrow these scopes or raise the twin budget.
- Failure text uses repository-relative source paths and registered identifiers.
- Legacy readers and writers are untouched. Budgets freeze their current spread
  without removing a single reference.
- Mixed versions are not a concern for a build-time check. When M2 introduces
  generated bindings, the generator's `--check` mode and the smoke both run so
  a stale generated file cannot merge.

## 8. Migration and rollback

- **Admission.** M0 lands with the registry and inventory matching the
  baseline exactly, plus two behavior-preserving edits so the owner check is
  green: the duplicate `TURN_ENVELOPE_SCHEMA_VERSION` in `driver.py` becomes an
  import, and the `HANDOFF_MODES` tuple in the authority e2e fixtures is
  derived from the `HandoffMode` enum.
- **Rollback.** Deleting the smoke, the `loopx/semantics/` package, the
  generator, its test, and the `pyproject.toml` line restores the previous
  state with no runtime effect. Later milestones each carry their own rollback
  in Section 11.
- **Point of no return.** None in M0. M3 field removals are the first
  irreversible step and are gated individually.

## 9. Validation and acceptance

| Claim | Test or evidence | Required result | Boundary / exclusions |
| --- | --- | --- | --- |
| Registry and inventory match the code at baseline | `python3.11 examples/semantic-vocabulary-drift-smoke.py` | `ok` with coverage, ratchet, budget, and twin report | Proves parity for registered vocabularies and mapped carriers only |
| Inventory is fresh | `python3.11 scripts/generate_semantic_inventory.py --check` | exit 0 | Structural map only |
| Scanner classification rules | `pytest tests/architecture/test_semantic_inventory.py` | pass | Fixture repository; rules from this RFC, not from output |
| A widened `effective_action` set fails closed in Python | Add an unregistered literal via `==`, membership, or conditional expression | Failure names the value and file | Mutation exercise; not a committed test |
| A widened `effective_action` set fails closed in TypeScript | Add an unregistered literal via `===` or a ternary | Same | Same |
| A forked constant fails closed | Redefine `TURN_ENVELOPE_SCHEMA_VERSION` or `HANDOFF_MODES` in a non-owner module, regenerate the inventory | Failure lists the extra defining module or the fork budget | Same |
| Python and TypeScript owners cannot diverge | Remove one entry from a registered `as const` array, or widen a registered enum | Failure names the missing or unregistered value | Same |
| The registry cannot be weakened by data alone | Declare a bare-module owner; drop an owner; narrow suffixes to `.py`; rename a vocabulary another relation references; add an unknown key | Each fails naming the rule | Same |
| A new carrier is visible | Add an enum without regenerating | Failure says the inventory is stale | Same |
| Conflicting spellings cannot grow | Add a third value for an already-conflicting name, regenerate | Failure names the definitions budget | Same |
| A multi-value collision cannot grow | Define one closed-set name in two modules with divergent values, or with equal values, and regenerate | `multi_value_forks` or `multi_value_twins` fails naming the new name | Mutation exercise; not a committed test |
| The registry cannot relax its own ratchet | Lower any `coverage_floor` count, raise any `inventory_ratchets` budget, or raise a retirement budget, in the same diff that removes the coverage it counts | `COVERAGE_ANCHOR`, `BUDGET_ANCHOR`, or `RETIREMENT_ANCHOR` fails naming the anchored value | Mutation exercise; moving an anchor is a code edit a reviewer sees |
| A tightened budget cannot drift back to a stale anchor | Lower a registry budget without touching the anchor | Failure says the registry value and the anchor differ | Equality, not `<=`; the fix is to lower the anchor in the same diff |
| The smoke is on the pull-request path | `pytest tests/architecture/test_semantic_vocabulary_drift.py` | pass; the test is collected by the default `pytest -q` sweep in `python-tests.yml` | The fleet and premerge surfaces are not the obligation (I10) |
| Premerge selects the smoke for a `loopx/` diff | `loopx canary premerge --changed-file loopx/control_plane/turn_driver/loop_controller.py` | the plan lists `examples/semantic-vocabulary-drift-smoke.py` under `repo-architecture-budget` | Selection is by trigger hint; the pytest wrapper is the guarantee |
| Measurement covers both carrier shapes and filters local naming | `pytest tests/architecture/test_semantic_inventory.py` | pass, including the collision and module-local-convention fixtures | Rules come from this RFC, not from scanner output |
| No behavior change from the two owner fixes | `pytest tests/test_loopx_turn_transaction.py tests/test_loop_turn_loop_controller.py tests/test_turn_loop_disposition.py tests/test_loopx_turn_managed_step.py tests/control_plane -k authority` and `loopx canary premerge --from-git-diff` | pass | Environment failures already present on `main` are excluded when reproduced on a clean tree |
| Docs governance accepts the RFC pair | `python3 examples/docs-governance-smoke.py` | pass | Checks mirror, links, index |
| Retirement budgets use standalone field tokens | `count_identifier_modules()` uses identifier boundaries for the six fields | `goal_boundary`: 30 Python modules under the new metric; the old substring metric was 35 | Conservative lexical measure; it removes compound-name false positives but does not prove semantic reader absence |
| The module-local convention filter is a code edit | Widen `MODULE_LOCAL_CONVENTION` in `inventory.py` and regenerate | `*_semantic` budgets fall with no code change elsewhere | Known boundary; the regex is in code so the widening is a reviewed diff, and the unfiltered totals stay budgeted |
| A registered value nobody produces fails (M0.5) | Run the production-form scan on the baseline | Fails naming `effective_action` and `skip`; passes after `skip` is removed or listed `compatibility_only` | First expected I12 failure; a compared-only value is not carried |
| A producer of an unregistered value fails (M0.5) | Write `effective_action: "brand_new"` in a listed producer site | Fails naming the site and the value even though no consumer compares it | I13; production is stricter than comparison |
| A bounded-context name leaves only the semantic fork budget by declaration (M0.5a) | Declare `SOURCE_SURFACES` with its four contexts; separately, rename one definition without declaring | Raw `multi_value_forks` stays 4, `multi_value_forks_semantic` is 3; a rename alone changes neither semantic accounting nor declaration | I14; the honest fix is a registry edit a reviewer sees, the rename is not a repair |
| An upstream merge can stale the committed inventory | Replay the scanner over the first parent and the merge of the last twenty `upstream/main` merge commits | 8 of 20 merges change at least one carrier | Measured cost of committing a snapshot; the handling rule is Section 10 and Section 12 Q9 |
| The formal model cannot silently lose a proof obligation | Remove an invariant, role, relation, or proof-boundary category from `formal_model` | The drift smoke fails on the exact formal-model shape | The model is a finite contract and proof ledger; it does not prove the listed properties by itself |

Known limits, stated so the check is not over-trusted:

- **Renames launder a collision.** Collisions are keyed by name, so renaming one
  side of a fork lowers the count without removing the drift. The advisory merge
  report is the review aid here; value-set equality cannot be a hard budget
  because `CONFIDENCE_LEVELS` and `EDGE_CASE_COMPLEXITIES` share `high/low/medium`
  while meaning different things.
- **Single-element carriers are invisible.** A closed set with one string member
  is not a vocabulary, so reducing a two-value set to one removes it from the
  inventory entirely.
- **The literal scan can misread unrelated comparisons on the same line.** A form
  such as `log("effective_action", kind === "repair_required")` is captured as an
  `effective_action` value. Registering the reported value to clear the failure
  would widen the vocabulary, so the correct fix is to register the field name
  and the literal together or restructure the line; the failure text names the
  file so this is visible in review.
- **Anchors are code, not history.** A PR can still move an anchor; it cannot do
  so without editing a named literal next to the registry change. Because the
  check is equality, a stale anchor is impossible, but the anchor also carries
  no memory of the lowest value ever reached; that history is the git log.

## 10. Operational contract

The standard premerge catalog limit increases from 9 to 10 checks so the new
vocabulary check does not displace the existing heartbeat/quota coverage. Quick
and deep tier limits are unchanged.

The check cannot affect a running system: it executes only in tests, premerge,
and CI. Its operator surface is the failure text. No observability, capacity,
or on-call contract applies.

Where it runs, and which surface is the obligation:

| Surface | Trigger | Selection | Role |
| --- | --- | --- | --- |
| `pytest` sweep, `python-tests.yml` | every pull request whose classification runs the Python tests | always collected via `tests/architecture/test_semantic_vocabulary_drift.py` | **The commit-time obligation (I10)** |
| `loopx canary premerge` | local, before opening a PR | `repo-architecture-budget` profile, trigger hints include `loopx/`, `examples/`, `scripts/`, `refactor` | Early local signal |
| Full public smoke fleet | push to `main`, daily schedule, manual dispatch | `examples/**/*-smoke.py` discovery | Post-merge confirmation; not a PR-required check by design |

Before this table existed the RFC said the smoke ran "in premerge and CI". On
the baseline that was true only after merge: premerge did not select the smoke
for a diff touching `loopx/control_plane/` alone, and the fleet workflow is
deliberately not a PR-required check. A fleet-discovered smoke is not a
commit-time check until a required PR job collects it.

**Merge-order hazard.** `inventory_v0.json` is a committed snapshot of the
whole `loopx/` tree, and the smoke fails when the tree and the snapshot differ.
Two pull requests that each add a carrier and each regenerate the inventory are
both green against the `main` they were built on; whichever merges second
leaves `main` with a snapshot missing the first one's entries, and the sweep on
`main` is red until someone regenerates. On the last twenty merges to
`upstream/main`, eight changed at least one carrier, so this is a weekly event,
not a corner case. The first upstream sync of this branch reproduced it: twelve
merged commits added one enum and three closed sets and the check failed
until regenerated. The handling rule is Section 12 Q9; until it is decided, the
rule is that the person who merges a PR after a red `main` regenerates the
inventory in a follow-up commit that touches only `inventory_v0.json`, and the
smoke's failure text names that command.

**Interpreter.** The smoke, the generator, and the scanner require the
project's Python (`>=3.11` in `pyproject.toml`); `zip(strict=True)` fails on
3.9. Fleet and premerge commands are spelled `python3` by repository convention
and run under the CI interpreter. A macOS system `python3` is 3.9, so local
premerge runs need a 3.11 environment on `PATH`; the docs spell the direct
commands as `python3.11` for that reason, and the planner entry is left as
`python3` on purpose.

## 11. Normative delivery plan

| Milestone | Shipped behavior | Entry gate | Exit evidence | Rollback |
| --- | --- | --- | --- | --- |
| M0 | Registry with 26 vocabularies and 9 relations, generated inventory with `--check`, drift smoke with fixed dispatch forms and coverage floor, two owner forks removed, RFC index entry | This RFC opened | Section 9 rows green; 20 mutation classes fail closed | Delete the smoke, `loopx/semantics/`, the generator, and its test |
| M0.5a | `scope_declarations` with `bounded_context` and per-context owners; semantic fork count separated from raw inventory count | M0 merged | Smoke checks every declared context owner; raw `multi_value_forks` remains 4 and `multi_value_forks_semantic` is 3; undeclared forks still fail the budget | Remove the scope declarations and semantic-fork budget |
| M0.5b | `producers` and `compatibility_only` on `kernel` vocabularies; production-form scan with the two role checks (I12, I13); retirement budgets counted by identifier with all six anchors lowered in one diff (Q11); merge-order rule from Q9 written into Section 10 | M0.5a complete; Q9 decided or its interim rule accepted | Smoke green with I11 to I14 enforced; `skip` resolved; Section 9 producer rows green; `turn_route` persistence answered for Q2 | Remove producer fields and role checks; budgets return to the pre-M0.5b anchors |
| M1 | `EffectiveAction` typed enum in one owner module; the replay observation and frontier slots split off (Q6); producers and consumers import it; registry `literal_scan` tightened to the enum | M0.5 merged; owner module chosen (Q3); slot split decided (Q6) | Smoke green; zero bare `effective_action` literals outside the owner; parity fixtures for status/should-run unchanged | Revert to literals; registry keeps the set |
| M2 | Route-to-disposition projection, the `decide_loop_disposition` decision table, and the cross-runtime sets published through a shared contract with generated Python and TypeScript bindings, following the coordination contract generator | M1 merged; Q2 and Q7 decided | Generator `--check` and smoke green; `settlement.ts` and `transaction.py` read the generated set | Regenerate from prior contract |
| M3 | Per-field retirement of legacy should-run fields, one field per PR, budgets lowered to zero and the field removed | Field has zero external readers proven by producer/reader research | Schema-reduction record per `AGENTS.md`; Appendix B entry | Restore field from the last writer |
| M4 | Twin budget lowered with each replacement-first cutover from the migration RFC | Each cutover PR | Budget edit in the same diff | None needed; budget follows code |

A ratchet without a target is a direction, not a plan. The table below is the
state at which this RFC is complete; each row is a registry budget or a
vocabulary property the smoke can check. Rows marked *open* wait on a Section
12 decision and are the reason the plan is a skeleton until those are recorded.

| Surface | Baseline (`1dc6ad8d8`) | Target when this RFC closes | Reached by |
| --- | --- | --- | --- |
| `effective_action` values | 33 literals, no owner symbol | one enum owner; `skip`, `observe_replay`, `block_replay`, and the two `quota_action_selection_*` codes gone from the decision slot; about 28 values | M1 |
| `effective_action` slots in one envelope | 3 vocabularies under one field name | 1, or a registered union if Q6 keeps the field | M1 (Q6) |
| Turn vocabularies | 3 sets, 28 values, 21 distinct, 7 redundant spellings | 3 sets kept; projection and decision table generated and checked; spellings unchanged unless Q10 sets a merge | M2 (Q2, Q10 *open*) |
| Same-runtime forks, semantic | 18 names | 0 | baseline PRs |
| Conflicting values, semantic | 2 names | 0 | baseline PRs |
| Multi-value forks | 4 (1 misclassified) | 0 after `scope` declares bounded-context names | M0.5 + baseline PRs |
| Multi-value twins | 19 | 0 | baseline PRs |
| Legacy should-run fields | 6 fields, 124 py / 10 ts module mentions | 0 fields | M3, identifier-counted |
| Merge-candidate groups | 32 unreviewed | every group classified; only `same_semantics` groups merged | classification PR, then per-group PRs |
| Control-plane py/ts twins | 43 | follows the TypeScript migration RFC; no target here | M4 |

### Two-track execution and enforcement lanes

The roadmap separates repairing existing semantic debt from improving the
measuring apparatus. Track A can proceed without waiting for a design decision:
remove real forks, conflicts, twins, and legacy readers one narrow PR at a time.
Track B improves what the guard can know: scope declarations, bounded producer
analysis, identifier counting, and merge-order handling. Track A reduces the
measured debt; Track B makes that measurement more faithful. M1 and later depend
on Track B where the current measurement is known to be incomplete.

```text
Track A: baseline debt repairs ───────────────────────────────┐
                                                               ├─> M1 typed slots
Track B: scope + producer model + metric boundaries ──────────┘       │
                                                                      ├─> M2 generated projections
                                                                      ├─> M3 legacy retirement
                                                                      └─> M4 runtime twin migration
```

The formal model uses four enforcement lanes so a difficult property does not
become an accidental merge blocker:

| Lane | Properties | Current meaning |
| --- | --- | --- |
| `blocking_now` | F5 projection totality | Enforced by the M0 smoke today |
| `blocking_next` | F1 producer closedness, F2 canonical liveness, F4 scope separation | Planned blocking checks after M0.5; not claimed by M0 |
| `advisory` | F3 consumer domain closedness | Reported evidence; it does not block ordinary consumer edits |
| `unproved` | F6 persistence/version compatibility | An explicit proof gap; it cannot be reported as passed |

The exit condition for a phase is its evidence row, not the existence of a
formula or a registry entry. A property moves from `unproved` to `advisory` only
when a bounded source-to-sink analysis exists, and moves to a blocking lane only
after its false-negative boundary is documented and mutation tests cover the
recognised forms. This keeps the contract strict about silent corruption while
allowing incomplete analyses to remain useful without blocking unrelated work.

The phases are therefore:

1. **M0:** keep the current structural guard and make its proof boundary
   explicit.
2. **M0.5:** implement `scope`, producer forms for the four Turn kernel
   vocabularies, and identifier-based retirement counts.
3. **M1:** split the overloaded `effective_action` slots and introduce one typed
   owner after Q3 and Q6 are decided.
4. **M2:** publish the full decision table and both projection hops through a
   generated cross-runtime contract.
5. **M3/M4:** retire legacy fields and reduce Python/TypeScript twins only when
   their reader and migration evidence is complete.

This roadmap is normative for dependencies and exit evidence. Issue #4447 may
carry owners, suggested dates, and operational checklists, but it must not
introduce a competing target state.


## 12. Open decisions

1. **Registry location.** Owner: kernel maintainers. M0 implements
   `loopx/semantics/` because the scope is repository-wide and neither
   `loopx/control_plane/` nor `docs/reference/` is; the package holds only the
   two JSON files and the scanner and is imported by no product code. This is
   a proposal until recorded in Appendix B. Needed before M1.
2. **Merge `LoopXTurnRoute` and `LoopDisposition`?** Owner: Turn driver owner.
   The projection is total but not injective (`blocked` and `wait` both map to
   `wait`), and `stop`, `terminal`, `contract_error` exist on one side only.
   The `same_concept` relations record the four shared verdicts.
   Recommendation: keep both, publish the projection in M2, revisit after the
   managed-step consumer matures. Needed before M2. The stated reason for
   keeping both is that merging would touch persisted Turn records; that
   premise is unverified. Before deciding, the M0.5 production-form scan (I12,
   Section 5) applied to `turn_route` should establish
   whether `turn_route` is ever written to the journal or a receipt, or only
   flows in-process; if the latter, the cost of a merge is far lower than this
   RFC assumes and Q10 applies.
3. **Owner module for `EffectiveAction`.** The registry declares no owner
   today because no symbol exists; the literal scan is the only check.
   Options: `quota/should_run_packet.py` (largest producer), a new
   `quota/effective_action.py`, or the TypeScript `turn_envelope.ts` with a
   Python import per the migration RFC. Recommendation: TypeScript owner with
   generated Python binding only if M2 lands first; otherwise
   `quota/effective_action.py`. Needed before M1.
4. **Companion glossary.** Whether to add `docs/reference/glossary.md`
   generated from the registry `meaning` fields and the inventory. Owner: docs
   maintainers. Recommendation: yes, in M1, generated so it cannot drift.
5. **Term-family naming rule.** Whether new identifiers in the `gate`,
   `scope`, `packet`, `handoff`, `settlement` families must cite a glossary row
   in review. This is a review rule, not a smoke; recommendation is to adopt it
   in the first-review roster once the glossary exists.
6. **Split the three `effective_action` slots.** The decision slot, the
   `agent_scope_frontier` slot, and the replay observation slot share one field
   name in one Turn Envelope and carry three vocabularies; `skip` is compared
   but never produced. Options: rename the observation and frontier slots,
   or keep one field with a registered union. Owner: Turn Envelope owner.
   Recommendation: rename in M1 so the enum in Q3 has one meaning. Needed
   before M1.
7. **Relation to `maintainability_ratchet.py`.** Whether the inventory
   ratchets adopt its reviewed exception lifecycle (`retirement_plan`, stale
   exception detection) or stay plain budgets. Recommendation: adopt it in M2
   when generation lands, so a fork with a documented reason can be excepted
   instead of budgeted. Owner: canary maintainers.
8. **Promotion rule from inventory to registry.** Whether a mapped carrier
   with three or more external consumer modules or a cross-runtime twin must be
   curated. Recommendation: yes as a review rule now, enforced by the smoke
   only after a quarter of inventory history exists. Owner: kernel maintainers.
9. **Inventory freshness across merges.** The committed snapshot goes stale
   when two carrier-adding PRs merge in sequence (Section 10, eight of the last
   twenty upstream merges). Options: (a) branch protection requires the PR to
   be up to date with `main`, which removes the hazard and slows every PR;
   (b) the merger owns a regenerate-only follow-up commit, which keeps the
   snapshot in git history and accepts a red `main` for minutes; (c) the
   inventory is not committed and CI generates it for the PR diff only, which
   loses `git blame` on carriers. Recommendation: (b) now, (a) if red `main`
   exceeds once a week. Owner: repository maintainers. This is an operations
   decision, not a code change; it belongs in the tracking issue's decision
   list, not its task list.
10. **Target state for the Turn vocabularies.** Section 11's target table
   keeps three sets and seven redundant spellings by default because Q2
   recommends keeping both. If the M0.5 production-form scan in Q2 shows `turn_route` is
   not persisted, the maintainers should choose between (a) three sets with a
   generated projection, the current plan, and (b) a two-phase merge (dual-
   write, then retire) to one spelling per concept. Without this decision the
   RFC has budgets but no definition of done for its headline problem.
   Owner: Turn driver owner. Needed before M2 closes.
11. **Retirement budgets by identifier.** The six legacy-field budgets now use
   `count_identifier_modules()`, so `goal_boundary_repair` is not counted as
   `goal_boundary`. This is a conservative lexical metric, not proof of zero
   semantic readers; computed accesses remain an evidence gap. Owner: kernel
   maintainers.

## Appendix A: Execution ledger (non-normative)

### 2026-09-15 — M0 opened with the RFC

- **Baseline:** `1dc6ad8d8`
- **Delivered:** registry with four vocabularies, one projection, one schema
  version, six legacy-field budgets, one twin budget; drift smoke; duplicate
  `TURN_ENVELOPE_SCHEMA_VERSION` in `driver.py` replaced by an import.
- **Evidence:** Section 9 rows; see Appendix C.
- **Known gaps:** the projection check imports the private
  `_route_to_disposition` until M2 publishes it.
- **Effect on normative design:** none.

### 2026-09-15 — M0 revised after review; scope made repository-wide

- **Baseline:** `1dc6ad8d8`
- **Trigger:** a review found the first literal scan blind to TypeScript
  (`===` never matched), two unregistered values already on the baseline
  (`observe_replay`, `block_replay`), and an owner check that silently skipped
  any owner written without a symbol.
- **Delivered:** registry moved to `loopx/semantics/vocabulary_v0.json` and
  widened to 26 vocabularies, 46 owner symbols, 9 relations, and a coverage
  floor; generated inventory `inventory_v0.json` with generator `--check` and
  unit test; smoke rewritten with fixed dispatch forms (comparison, assignment,
  ternary, membership, conditional expression), AST-based owner resolution,
  owner exclusivity, inventory freshness and fork/conflict budgets; the
  `HANDOFF_MODES` fixture fork derived from the enum.
- **Evidence:** Appendix C, E6 to E10.
- **Known gaps:** the load-bearing `decide_loop_disposition` table is still
  prose only (M2); the literal scan cannot attribute a literal to one of the
  three `effective_action` slots (Q6); the scan cannot follow values through
  variables, so two quota error codes are registered as variable-sourced with
  a producer check rather than proven.
- **Effect on normative design:** Sections 1 to 5, 8, 9, 11, 12 revised;
  I8 added. Recorded as the same-day revision of an unmerged draft.

### 2026-09-15 — M0 measurement repaired after a second review

- **Baseline:** `1dc6ad8d8`
- **Trigger:** a second review ran 14 attacks against the smoke. Seven escaped:
  lowering `coverage_floor` (individually or all at once), raising
  `inventory_ratchets` or a retirement budget, and — decisively — dropping an
  owner *and* lowering the matching floor in one diff. The floor lived in the
  same file it guarded and was compared with `>=`, so the registry could relax
  its own ratchet. I5 and I8 were prose, not machine-enforced.
- **Also found:** collision detection ran only over string constants, so the 599
  multi-value carriers were listed but never compared. Four same-name forks were
  already on the baseline, including `SOURCE_SURFACES` defined four times with
  four different value sets, plus 19 invisible twins. Separately, 16 of the 18
  `conflicting_values` names were module-local conventions (`SCHEMA_VERSION`
  sixteen times, `COMMAND`, `REQUEST_SCHEMA`, `SURFACE`), so the budget was
  mostly measuring local naming.
- **Delivered:** anchors `COVERAGE_ANCHOR`, `COVERAGE_SUFFIX_ANCHOR`,
  `BUDGET_ANCHOR`, `RETIREMENT_ANCHOR` in the smoke, closing all seven escapes;
  `multi_value_name_collisions` giving enums, closed sets, `Literal` aliases, and
  `as const` arrays the string-constant collision rule, with the four forks and
  19 twins budgeted at today's count; `MODULE_LOCAL_CONVENTION` keeping
  module-local names in the visible totals but out of the semantic budgets
  (`conflicting_values_semantic` 2, `same_runtime_forks_semantic` 18); advisory
  merge-candidate report over the 32 groups of distinct names sharing a value
  set; two scanner tests on a dedicated collision fixture; I9 added and the
  Section 9 limits stated.
- **Evidence:** Appendix C, E11 to E13.
- **Known gaps:** collisions are keyed by name, so a rename still launders one;
  single-element carriers are invisible; the literal scan can misread an
  unrelated comparison sharing a line.
- **Effect on normative design:** I5 and I8 restated as enforced rather than
  intended; I9 added; the Section 5 table and Section 9 rows updated. Moving an
  anchor is now the only way to relax a budget, and it is a code edit.
- **Open question sharpened:** Q7 may now collapse from "adopt the
  `maintainability_ratchet` exception lifecycle" to "share its anchor pattern",
  because this smoke already uses that pattern.

### 2026-09-15 — M0 placed on the pull-request path after a third review

- **Baseline:** `1dc6ad8d8`
- **Trigger:** a third review asked where the smoke actually runs. A premerge
  plan for a diff touching only `loop_controller.py` and `turn_envelope.ts`
  listed 32 commands and not this smoke; `full-public-smokes.yml` triggers on
  push to `main` and a daily schedule and is documented as intentionally not a
  PR-required check. The only surface that runs on every pull request is the
  `pytest` sweep, and the committed test covered the scanner on fixtures only.
  The RFC's "commit-time" claim therefore held only after merge.
- **Also found:** every anchor compared with `<=` (or `>=` for floors), copied
  faithfully from the `RFC_MODULE_BUDGETS` precedent. A budget tightened below
  its anchor in one PR could be raised back to the anchor in a later PR with no
  code edit, so the ratchet stalled at whatever value the anchor last held.
- **Delivered:** `tests/architecture/test_semantic_vocabulary_drift.py` runs
  the smoke as a subprocess inside the default sweep; the smoke is added to the
  `repo-architecture-budget` premerge profile beside the maintainability
  ratchet; all three anchor comparisons become equality; I10 added; Section 10
  gains the surface table.
- **Evidence:** Appendix C, E14 to E16.
- **Known gaps:** the pytest wrapper costs about three seconds per sweep;
  premerge selection still depends on a trigger hint matching the changed path.
- **Effect on normative design:** I5 restated as equality with the reason for
  departing from the precedent; I10 added; Section 9 gains three rows; Section
  10 rewritten from one sentence to a surface table.

### 2026-09-15 — M0 reviewed a fourth time: scope, merge order, target state

- **Baseline:** `503991dd2` merged; `upstream/main` at `2f84af990`, twelve
  commits ahead of the branch.
- **Trigger:** a fourth review asked what the guard's inputs depend on and
  what "repository-wide" covers. Merging the twelve upstream commits into a
  scratch tree staled the inventory (one enum, three closed sets); replaying
  the scanner over the last twenty upstream merges showed eight would have
  done the same. The RFC said repository-wide while the inventory root and
  every literal scan said `loopx/`; `examples/` holds a dozen
  `effective_action` assertions and `apps/` about ninety TypeScript files the
  smoke never reads.
- **Also found:** `SOURCE_SURFACES` is four CLI commands each listing its own
  data sources, not a fork; the name-keyed rule cannot express that. Retirement
  budgets count substrings (35 vs 30 identifier modules for `goal_boundary`).
  The plan had budgets but no target state, and its four entry decisions had
  no owner deadline.
- **Delivered:** Section 3 fixes the scan root to `loopx/` and names `apps/`
  and `examples/` as non-goals; Section 5 previews the M0.5 `scope` field with
  `SOURCE_SURFACES` as the first case; Section 9 gains three known-boundary
  rows; Section 10 gains the merge-order hazard and interpreter paragraphs;
  Section 11 gains the target-state table; Section 12 gains Q9 to Q11 and a
  verification note on Q2; the registry's `inventory_ratchets` gains a note on
  the misclassified fork. No code or budget changed.
- **Not done on purpose:** the premerge planner keeps `python3`, because every
  fleet command is spelled that way and the runner smoke asserts the text; the
  interpreter requirement is documented instead.
- **Evidence:** Appendix C, E17 to E20.
- **Effect on normative design:** Section 3 scope narrowed to match the code;
  Section 11 now has a definition of done; Section 12 gains three decisions.

### 2026-09-15 — Role and scope models written into the contract

- **Trigger:** the RFC used "producer" and "consumer" nineteen times without
  defining either, Q2 and Q10 depended on "a producer check" the document
  never specified, `scope` existed only as a preview paragraph, and Section 1
  still said the smoke ran "on every premerge and full-public run" after
  Section 10 had made the pytest sweep the obligation.
- **Delivered:** Section 5 gains "Roles of a vocabulary" (owner, producer,
  interpreter, pass-through) and three schema rows (`scope`, `producers`,
  `compatibility_only`); Section 2 gains I11 to I14, each marked as enforced
  from M0.5; Section 9 gains three M0.5 rows; Section 11 gains the M0.5
  milestone and M1 now gates on it; Q2 and Q10 point at I12 instead of an
  undefined check; Section 1 matches Section 10. No code, registry value, or
  budget changed; the M0 smoke does not yet enforce I11 to I14.
- **Effect on normative design:** four invariants added with an explicit
  enforcement milestone; the plan gains a definition of "produced" that M3's
  zero-reader gate and Q2's persistence question can both use.

## Appendix B: Decision log

| Date | Decision | Owner / approval | Alternatives | Normative sections changed |
| --- | --- | --- | --- | --- |
| — | none recorded | — | — | — |

## Appendix C: Evidence registry

| Evidence id | Claim | Baseline / environment | Artifact or command | Result | Privacy / validity boundary |
| --- | --- | --- | --- | --- | --- |
| E1 | Three definitions of the envelope schema constant | `1dc6ad8d8` | `rg -n 'TURN_ENVELOPE_SCHEMA_VERSION\s*=' loopx` | 3 files | Source only |
| E2 | 28 distinct `effective_action` literals across `loopx/` | `1dc6ad8d8` | the smoke's `literal_scan` | 28 | Pattern-bound; prose mentions excluded |
| E3 | 43 py/ts twins under the control plane | `1dc6ad8d8` | smoke twin report | 43 | Same-basename rule only |
| E4 | Legacy field spread | `1dc6ad8d8` | smoke budget report | see registry | Module mentions, not call sites |
| E6 | Global census of closed-set carriers | `1dc6ad8d8` | `python3.11 scripts/generate_semantic_inventory.py` summary | 102 enums, 490 closed sets, 8 aliases, 40 arrays, 2002 named constants, 166 twins, 25/58 forks, 18/59 conflicts | AST and `as const` text scan; module-level only |
| E7 | First scan pattern captured zero TypeScript sites | `1dc6ad8d8` | pattern applied to every `.ts` line containing `effective_action` | 0 of 7 dispatching files matched; `===` always failed | Pattern-bound |
| E8 | Two `effective_action` values unregistered on baseline while the first smoke was green | `1dc6ad8d8` | `turn_journal.ts:656` ternary | `observe_replay`, `block_replay` | Same |
| E9 | Owner check skipped a bare-module owner | `1dc6ad8d8` | first smoke's `if "::" in python_owner` | `effective_action` owner never checked | Code reading plus mutation |
| E10 | Twenty drift mutations fail closed (TS `===`, TS ternary, Python membership, Python `==` through `or ""`, bare owner, dropped owner, narrowed suffixes, renamed vocabulary, forked symbol, TS value removed, enum widened, projection changed, legacy field regrown, stale inventory, third conflicting spelling, dead value, lost variable producer, broken subset, forked schema version, unknown registry key) | `1dc6ad8d8` + local edit, inventory regenerated where the edit adds a carrier, restored after each run | temporary edit then the smoke with `python3 -B` | 20/20 exit 1 naming the rule, value, or file | Local exercise, not a committed test |
| E5 | Nine drift mutations fail closed (unregistered literal with and without digits, forked constant, TS kind removed, Python enum widened, projection changed, legacy field regrown, dead registry value, new py/ts twin) | `1dc6ad8d8` + local edit, restored after each run | temporary edit then the smoke, run with `python3 -B` | 9/9 exit 1 with the offending value or file named | Local exercise, not a committed test; a same-size same-second edit needs `-B` to defeat stale bytecode |
| E11 | The registry could relax its own ratchet in one diff | `1dc6ad8d8` + local edit | fourteen registry mutations: lower one floor, lower all floors, lower a floor while dropping the owner it counts, raise every `inventory_ratchets` entry, raise one entry, raise a retirement budget | 7 escaped before the anchors, 0 escape after; each caught failure names the anchored value | Local exercise, not a committed test |
| E12 | 599 multi-value carriers were listed but never compared | `1dc6ad8d8` | collision rule applied to enums, closed sets, `Literal` aliases, and `as const` arrays | 4 same-name forks (10 definitions) and 19 twins already on the baseline, none budgeted; `SOURCE_SURFACES` alone has four divergent value sets | Name-keyed; a rename removes a name from the comparison |
| E14 | The smoke was not on the pull-request path | `1dc6ad8d8` + M0 | `loopx canary premerge --changed-file loopx/control_plane/turn_driver/loop_controller.py --changed-file loopx/control_plane/quota/turn_envelope.ts`; `.github/workflows/full-public-smokes.yml` triggers | 32 commands planned, smoke absent; fleet runs on push to `main` and schedule only | Selection by path token; CI wiring read from the workflow files |
| E15 | A tightened budget could drift back to its anchor | `1dc6ad8d8` + M0 | `ratchets[key] <= BUDGET_ANCHOR[key]` and `floor[key] >= anchored` in the smoke | any value between the tightened budget and the anchor passed | Code reading; the precedent uses the same comparison |
| E16 | Equality closes the stall and the wrapper reaches the sweep | `1dc6ad8d8` + M0 | lower one `inventory_ratchets` entry with the anchor untouched, then `pytest tests/architecture/test_semantic_vocabulary_drift.py` on the clean tree | the mutation fails naming both values; the wrapper passes in about three seconds | Local exercise plus committed test |
| E17 | Upstream merges stale the committed inventory | `upstream/main` `2f84af990`, last 20 first-parent merges | scanner facts of every changed `loopx/**/*.{py,ts}` compared between first parent and merge | 8 of 20 merges change at least one carrier; the branch's own upstream sync added 1 enum and 3 closed sets | Facts-level comparison, equivalent to a full regenerate |
| E18 | Declared scope exceeded the scan root | `503991dd2` + M0 | `literal_scan.roots` and inventory `root` read from the registry; `grep` for `effective_action` dispatch literals under `examples/`; count of `.ts`/`.tsx` under `apps/` | roots are `loopx` only; 12+ assertions in `examples/`; 90 files in `apps/` | Consumers and test doubles, not producers |
| E19 | `SOURCE_SURFACES` is four bounded contexts, not a fork | `503991dd2` | the four `multi_value_forks` definitions read from the inventory | each module lists the data sources of its own CLI command with disjoint values | Judgement from reading the values; the rule cannot make it |
| E20 | Retirement budgets over-count by substring | `503991dd2` | `'goal_boundary' in text` vs `\bgoal_boundary\b` over `loopx/**/*.py` | 35 vs 30 modules | Identifier count is the M3 gate's measure |
| E13 | The conflict budget mostly measured local naming | `1dc6ad8d8` | `MODULE_LOCAL_CONVENTION` applied to `conflicting_values` and `same_runtime_forks` names | 16 of 18 conflicts and 7 of 25 forks are module-local conventions; the semantic subsets are 2 and 18 | Classification is a name pattern, documented in the scanner and pinned by a fixture test |

## Appendix D: Rejected or superseded alternatives

See Section 6. A single-PR enum unification was rejected because the three
enums have distinct change reasons; the evidence that could reopen it is a
projection proven to be a bijection after M2.

## Appendix E: Incident and review lessons

- Hand-synchronized parallel constant lists across runtimes pass review until
  the day one side changes; a parity check must exist before the second copy is
  accepted.
- A private extraction of a shared constant looks harmless in a large module
  and is the most common way a schema version forks. Test fixtures are the
  second most common: `HANDOFF_MODES` was copied into an e2e fixture.
- A literal scan that only accepts `[a-z_]` silently skipped a `_v2` spelling
  during the M0 mutation exercise. Capture every quoted string and validate the
  shape separately, so a malformed value is reported instead of ignored.
- A scan pattern written from Python examples matched no TypeScript at all,
  and a guard that is green on a baseline containing violations proves only
  that the guard is blind. Mutation-test every runtime the registry claims to
  cover before declaring an invariant.
- When the registry is both the specification and the validator's input, a
  data edit can weaken the validator. Keep the recognised forms in code, floor
  the coverage counts, and reject owners that are not `module::Symbol`.
- A ratchet on names alone lets an already-conflicting name gain a third
  spelling. Budget definitions as well as names.
- A smoke the fleet discovers is not a commit-time check. Ask on which
  required PR job it is collected, and plan a diff that touches only the
  guarded code to see whether selection finds it. If the answer is "after
  merge", the invariant is a report, not a gate.
- An anchor compared with `<=` pins only the value it held when written. Every
  tightening below it is unprotected until someone remembers to move the
  anchor. Compare with equality so the two values cannot separate.
- One field name can carry several vocabularies inside one envelope; a scan
  that sees the field cannot see the slot. Record the slots as a relation so
  the ambiguity is a registered fact, not an accident the registry blesses.
- A committed snapshot of the whole tree makes the guard's input depend on
  other people's merges. Measure how often the tree changes under it before
  committing it, and write down who regenerates when `main` goes red.
- A name-keyed collision rule needs a way to say "these are different things
  that share a name". Without it the honest fix and the dishonest fix (a
  rename) lower the same number, and reviewers cannot tell them apart.
- When a document widens its scope faster than the code, the two must be
  reconciled in whichever direction is cheaper, but they must match. A scope
  claim the scanner does not implement is a false invariant.
- Budgets that only go down describe a direction. Write the target table
  before the second milestone, or nobody can say when the work is done.
- A decision that waits on "a check" the RFC never defines is a dangling
  reference dressed as prudence. Name the invariant and the milestone that
  delivers the check, or the decision has no input and never closes.
- Using a role word (producer, consumer) nineteen times is not defining it.
  Until the roles are a table with a check per role, "who writes this value"
  is a question every reviewer answers differently.
