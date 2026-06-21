# PoC Feedback And Case Report Loop

LoopX is still early. The fastest useful feedback is not a long review; it is a
small, public-safe case report that shows where a long-running agent loop became
hard to govern.

This note defines the default PoC feedback loop for seed users and contributors.
It turns onboarding friction, real usage stories, and showcase ideas into
repeatable evidence without publishing private work.

## Intake

Use GitHub Issues or Discussions as the primary public entry. Chat groups are
useful for quick questions, but public proof should eventually reduce to an
issue, PR, or showcase patch that future users can inspect.

Good seed-user feedback usually fits one of these shapes:

| Feedback shape | Best public entry | What to include |
| --- | --- | --- |
| Onboarding friction | Issue | Install path, agent surface, confusing step, expected next action. |
| Real case candidate | Issue or Discussion | Domain label, loop length, where the agent got stuck, what stayed private. |
| Showcase improvement | PR or Issue | Case card, better wording, missing evidence, or public-safe screenshot. |
| Product gap | Issue | The decision, gate, todo, or evidence signal that was hard to see. |

Do not paste private chats, credentials, internal URLs, raw traces, customer
names, local paths, or unpublished artifacts. Describe the pattern instead.

## Case Report Shape

A useful case report is short:

```text
Title:
Domain:
Agent surface:
Loop length:
What became hard:
What LoopX made visible:
Human decision:
Safe side work:
Evidence pointer:
Private boundary:
Suggested public claim:
```

The report should be understandable without reading logs. If a field cannot be
shared publicly, write the boundary instead of the raw detail.

## Evidence Checklist

A case is ready to influence the PoC when it has:

- a reusable control-plane pattern, not just "an agent did work";
- a public-safe evidence pointer such as a PR, issue, commit, smoke, synthetic
  fixture, or approved screenshot;
- an explicit private boundary;
- a plain-language user value statement;
- one next action that would make the case more reproducible or clearer.

For the first 3-5 PoC users, prefer modest evidence over broad claims. A case
can be valuable even when it ends in a blocker, as long as the blocker is
visible and the next safe action is concrete.

## Promotion Path

1. **Feedback**: a user files an issue, discussion, or small PR.
2. **Triage**: a maintainer labels the pattern and public/private boundary.
3. **Report**: the case is reduced into the report shape above.
4. **Catalog**: mature reports become `docs/showcases` case cards or appendix
   entries.
5. **Frontstage**: only catalog-backed, public-safe cases become public cards.

This keeps the hosted Frontstage honest: it shows public product proof, not
private local status or unreviewed anecdotes.

## Maintainer Triage Notes

When converting feedback into a contributor task, preserve these fields:

- source entry: issue, discussion, PR, or approved public artifact;
- pattern tags: gate, fallback, ownership, evidence, replan, feedback, or
  onboarding;
- claim level: synthetic demo, public evidence, redacted stub, or appendix;
- boundary: what must not appear in public docs or UI;
- next proof: smoke, screenshot, case page, frontend card, or user question.

If the report depends on private material, keep it out of the public catalog
until a sanitized summary or synthetic reproduction exists.
