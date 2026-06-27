# 0623: Agent-To-Agent PR Comment And Fix Loop

## Summary

This case captures a public-safe version of a multi-agent review loop: one
agent lane can notice or respond to PR review feedback, while another lane
keeps the implementation and fix evidence reviewable. The important behavior is
not the chat transcript. It is the control-plane loop around a PR: comment,
handoff, fix, validation, and review packet.

The original evidence included operator-side screenshots and review context, so
this repository keeps only the reusable pattern. Public PR surfaces can be used
as evidence, but raw screenshots and private coordination details stay out of
the repo.

## Pattern

A review comment is a good boundary object for long-running agents:

- it is concrete enough to turn into a todo;
- it belongs to a public or reviewable PR surface;
- it can be routed to the agent that owns the implementation lane;
- it can be closed only after a fix and validation are visible.

LoopX keeps that flow explicit instead of relying on a human to remember which
agent saw the comment.

## LoopX Behavior

LoopX contributes the following control-plane pieces:

- a claimed todo names the PR feedback or comment thread;
- a handoff gate keeps the blocked agent from guessing outside its lane;
- the implementation agent records the fix and validation evidence;
- the review packet points the reviewer back to the public PR surface;
- follow-up work becomes a successor todo rather than a loose chat note.

## User-Facing Value

The operator does not need to manually shepherd every PR comment across agent
threads. LoopX turns review feedback into a bounded work item with owner,
evidence, and handoff state. That makes agent-to-agent collaboration useful
without hiding the final review responsibility.

## Evidence Boundary

This case excludes private screenshots, raw chats, internal review notes, local
state, credentials, and unpublished artifacts. The public-safe evidence shape
is the PR comment/fix lifecycle itself: a visible PR surface, a claimed todo,
the fix diff, validation output, and the resulting review packet.

## Website Story Beats

1. A PR receives feedback that should become executable work.
2. LoopX turns the feedback into an owned todo instead of a chat reminder.
3. Another agent lane implements or verifies the fix.
4. The review packet links the comment, fix, and validation evidence.
5. Follow-up work remains explicit as successor todos.
