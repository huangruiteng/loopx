# 0623: Overnight Project Refactor As PR-Sized Slices

## Summary

This case captures a long unattended refactor that stayed reviewable because
LoopX kept splitting the work into bounded PR-sized slices. The reusable lesson
is that autonomous refactoring should not land as one huge diff. It should keep
todo follow-up, supersede decisions, validation, and review boundaries visible.

The source note described an overnight refactor wave. This repository records
the public-safe control-plane pattern rather than private screenshots or local
project state.

## Before

Large refactors are a bad fit for naive autonomous loops. Without a control
plane, an agent can keep editing after the original plan is stale, mix cleanup
with behavior changes, or produce a broad diff that is hard to review.

The desired behavior is:

1. keep the goal and current slice explicit;
2. finish one reviewable unit at a time;
3. create follow-up todos for remaining work;
4. supersede stale todos when the refactor discovers a better route;
5. validate each slice before merge or handoff.

## LoopX Behavior

LoopX makes that refactor loop durable:

- `todo follow-up` turns discoveries into the next concrete slice;
- `supersede` prevents stale tasks from staying runnable;
- quota and status keep the current slice separate from adjacent cleanup;
- review packets and focused smokes keep each PR independently checkable;
- public/private boundary scans prevent local planning material from leaking
  into public docs.

## User-Facing Value

The operator can let a refactor continue overnight while still waking up to
reviewable units. The project moves faster, but the review surface remains
human-sized.

## Evidence Boundary

This case excludes private screenshots, raw chats, internal planning notes,
local paths, credentials, raw logs, and unpublished project artifacts. Public
evidence should come from the resulting PR-sized diffs, validation commands,
and follow-up/supersede state, not from raw agent traces.

## Public Evidence Sequence

1. A broad refactor starts as a long-running goal.
2. LoopX keeps the current slice explicit.
3. Follow-up and supersede convert discoveries into reviewable next steps.
4. Each slice gets validation and a review packet.
5. The operator reviews bounded PRs instead of a giant autonomous diff.
