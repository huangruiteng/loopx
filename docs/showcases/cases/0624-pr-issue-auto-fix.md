# 0624: PR Issue Automatic Fix Loop

## Summary

This case captures the issue-to-fix loop: review feedback, issue text, or a PR
comment should become an executable repair plan with a repro or focused smoke,
not an informal note in chat. LoopX turns that signal into a bounded workflow
that can classify the problem, prepare a branch, implement a fix, validate it,
and report the result back to the review surface.

The original showcase included private visual evidence. This public case keeps
only the reusable product pattern and the repository surfaces that support it.

## Pattern

Automatic issue fixing needs more than "read the issue and edit files." A safe
workflow needs to:

- classify whether the issue body or review comment is enough to act on;
- create or identify a focused reproduction path;
- keep private or gated issue bodies out of public fixtures;
- make the implementation branch explicit;
- run a small validation command before reporting success;
- record any unresolved reviewer decision as a concrete todo.

## LoopX Behavior

LoopX supports the loop with issue-fix planning and command-pack style
contracts:

- the initial signal becomes ordered todos rather than prose;
- gated reads remain explicit when a body or comment is not safe to consume;
- implementation and validation steps stay separate;
- review feedback can create a successor todo instead of being lost after a PR
  comment;
- the final packet records what was fixed, what was validated, and what still
  needs a reviewer.

## User-Facing Value

The operator can point LoopX at a review issue and expect a controlled repair
loop: understand the request, create a repro, implement the fix, validate it,
and surface remaining review decisions. The user does not have to translate
every PR comment into a manual agent prompt.

## Evidence Boundary

This case excludes private screenshots, raw issue bodies from gated sources,
internal review notes, local paths, raw logs, credentials, and unpublished
repository artifacts. Public evidence should be the sanitized workflow plan,
focused smoke, branch diff, and public PR review outcome.

## Website Story Beats

1. A PR issue or review comment appears.
2. LoopX classifies the issue and creates ordered repair todos.
3. The agent builds or finds a focused repro.
4. The fix lands as a reviewable branch diff with validation.
5. Remaining reviewer decisions are written back as concrete todos.
