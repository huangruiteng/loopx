# Creator-Ops Feedback And Boundary Contract

This contract describes how a public-safe creator-operator showcase should turn
non-technical user feedback into visible LoopX state.

It is a product contract for demos and future frontends. It is not a social
platform crawler, publishing tool, private memory store, or claim about real
creator performance.

## Purpose

A creator-operator should be able to answer four questions without reading
prompts, traces, or logs:

- what changed since the last run;
- what is waiting for human judgment;
- what can safely continue while the gated route waits;
- how my feedback changes the next agent move.

LoopX should make that feedback visible as structured state instead of
letting it disappear into chat history.

## Feedback Classes

| Feedback class | Example user phrase | Control-plane effect |
| --- | --- | --- |
| `gate_decision` | "Publish after I review tone." | Updates a user gate with the decision, stop condition, and owner judgment. |
| `preference_hint` | "This is too salesy." | Records a planning preference for future ranking, drafting, or revision. |
| `todo_update` | "Revise this angle first." | Creates or reprioritizes an agent todo. |
| `boundary_correction` | "Do not use this source." | Marks a source or material item as disallowed and creates cleanup work. |
| `reward_signal` | "This direction is useful." | Records a compact positive signal tied to the run and rationale. |
| `product_improvement_note` | "I cannot tell what is blocked." | Creates a product/docs/UI improvement todo, not project truth. |

The classes are intentionally separate. A preference is not a permission gate.
A positive reward is not approval to publish. A boundary correction overrides
the affected route until the state is repaired.

## Source Status

Every topic, insight, draft, and material-library item should carry a source
status:

| Source status | Meaning | Public showcase rule |
| --- | --- | --- |
| `synthetic_demo` | Fake data created for the demo. | Safe for public docs when labeled. |
| `public_source_summary` | A summary rewritten from public material. | Safe only when attribution and terms are respected. |
| `private_user_material` | User notes, drafts, or preferences. | Never render in public examples. |
| `unpublished_draft` | Draft work that has not been approved. | Keep behind a publish gate. |
| `needs_review` | Source status is uncertain. | Treat as blocked for public or publishing use. |
| `forbidden_public_surface` | User or policy rejected public use. | Remove from public demo and future render paths. |

For the public repository, the default should be `synthetic_demo`.

## No-Autopublish Gate

Publishing is a hard user gate:

- default state is no publish;
- source policy and tone approval must be explicit;
- private or uncertain material cannot be used to publish;
- safe side work may continue only when it is independent of the gate.

Good side work includes organizing synthetic material, preparing questions,
splitting todos, improving source-status labels, and making the next decision
easier for the user.

## Write Mapping

| Input | Allowed write | Forbidden write |
| --- | --- | --- |
| Gate decision | user gate state, run history summary | hidden publish approval |
| Preference hint | preference note, todo ranking rationale | hard safety decision |
| Todo update | new or reordered agent todo | silent plan mutation |
| Boundary correction | source status update, cleanup todo, blocker note | continued use of rejected material |
| Reward signal | compact run-bound signal with reason | unbounded personal profile |
| Product improvement note | contributor/product todo | fabricated project evidence |

Every write should preserve the source of the feedback in compact form: user
answer, synthetic fixture, public summary, or product observation.

## Replan Rules

After feedback, the next plan should show:

- the changed todo or gate;
- the blocked route, if any;
- the safe side path, if any;
- the validation expected before the next writeback.

If the feedback is ambiguous, ask a concrete question or create a user gate.
Do not turn ambiguity into hidden memory.

## Frontend Expectations

A non-technical operator surface should render feedback as choices with visible
effects. For example:

| Button | Visible effect |
| --- | --- |
| This angle is useful | Adds a reward signal and preference hint. |
| Too salesy | Adds a revision todo and style preference. |
| Do not use this source | Adds a boundary correction and cleanup todo. |
| Publish after tone review | Keeps publishing gated until tone review is done. |

The UI should show the resulting state change before the next automatic run
spends compute.

## Acceptance Criteria

A creator-ops demo satisfies this contract when:

- all public data is synthetic or clearly public-safe;
- no feedback is stored only as invisible chat context;
- publishing remains explicitly gated;
- boundary corrections stop affected work until repaired;
- safe side work is separate from publish-gated work;
- the catalog can link this contract beside the case page and storyboard.
