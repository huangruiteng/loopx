# LoopX Update Notes

LoopX publishes a public-safe update note every two weeks. The notes summarize
what changed in the public repository, what shipped as product surface, and
which control-plane or documentation contracts became more stable.

The update-note source of truth is public repository history: merged PRs,
commit subjects, shipped docs, public smokes, and public CLI behavior. Private
chat, internal documents, raw benchmark traces, local paths, credentials, and
operator-only state are intentionally excluded.

## Latest

- [2026-06-14 to 2026-06-27](2026-06-14-to-2026-06-27.md)

## Archive

| Window | Note | Focus |
| --- | --- | --- |
| 2026-06-14 to 2026-06-27 | [Read note](2026-06-14-to-2026-06-27.md) | LoopX rename, benchmark workflow hardening, host commands, issue-fix workflow, evented state, task graph, and scheduler reliability. |
| 2026-05-31 to 2026-06-13 | [Read note](2026-05-31-to-2026-06-13.md) | Public scaffold, local control plane, dashboard surface, quota/heartbeat loop, review packets, and project-agent todo contracts. |

## Publication Rules

- Keep each note compact and public-safe.
- Prefer stable product themes over raw commit lists.
- Link public docs or PRs when the reference is useful, but do not require a
  reader to inspect private state.
- Treat the note as a summary surface. The source of truth remains public git
  history, LoopX CLI behavior, and shipped docs.
- Publish on a two-week cadence anchored at the initial public scaffold on
  2026-05-31.
- Next expected window: 2026-06-28 to 2026-07-11.

## Automation

See [Biweekly update-note automation](automation.md) for the recommended
publication path. The short version: `.github/workflows/update-notes.yml` runs
a separate release-note job that opens a reviewable PR, not custom logic inside
the active LoopX heartbeat.
