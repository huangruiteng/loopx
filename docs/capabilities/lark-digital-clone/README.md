# Lark Digital Clone

The Lark digital clone capability turns one day of Lark message context into a
small owner-reviewed work packet:

- reply drafts for messages that look actionable;
- weekly-report material candidates;
- candidate LoopX todos for follow-up work;
- a review queue that keeps external writes gated.

## Why This Exists

Knowledge workers already use Lark as the place where requests, reminders,
status fragments, and loose commitments arrive. A long-running agent is only
useful when it can turn that stream into a compact surface the owner can review
quickly.

The digital clone feature gives the owner three concrete benefits:

- fewer missed asks, because `@me` messages become a daily review queue;
- faster replies, because the agent drafts short responses with source message
  ids attached;
- better weekly reporting, because the same scan preserves delivery signals as
  weekly material candidates.

The clone is scoped as a draft producer and control-plane projection. It does
not impersonate the owner, send messages by default, mutate LoopX state by
default, or store raw private payloads in public repository files.

## Current Shipped Path

The first PR ships the local scan path:

```bash
loopx lark-digital-clone scan --at-me --since 24h
```

By default the command produces dry-run previews. Real Lark reads require an
explicit flag:

```bash
loopx lark-digital-clone scan --at-me --since 24h --execute-read
```

For tests and demos, fixture mode avoids Lark access:

```bash
loopx lark-digital-clone scan \
  --fixture-json examples/messages.json \
  --out-dir /tmp/lark-digital-clone \
  --skip-auth-check
```

The command writes local artifacts under `.local/lark-digital-clone/latest` by
default:

- `summary.json`
- `today_todo.md`
- `reply_drafts.md`
- `weekly_material.md`
- `send_review.md`
- `review_queue.json`
- `loopx_todo_packet.json`

## Write Boundary

Every external write remains gated:

- send commands in `send_review.md` include `--dry-run`;
- `review_queue.json` items start as `needs_user_approval`;
- `loopx_todo_packet.json` is a candidate packet only;
- raw Lark payloads stay under the local artifact directory.

This boundary lets the owner inspect the clone's work before deciding whether
to send a reply, import a todo, or discard the suggestion.

## Owner Digest Extension

The next product step is an owner digest: after a daily scan, LoopX can send one
Lark markdown message to the current agent's owner.

Planned command shape:

```bash
loopx lark-digital-clone scan --at-me --since 24h --execute-read \
  --notify-owner \
  --owner-user-id ou_xxx \
  --notify-dry-run
```

The digest should include:

- scan date and agent id;
- message, draft, and weekly-material counts;
- the top pending reply drafts with message ids;
- local artifact paths or a review URL when one exists;
- a clear note that sending individual replies still requires approval.

The send path should use `lark-cli im +messages-send` with an idempotency key
derived from `(agent_id, owner_user_id, scan_date)`, so repeated runs do not
spam the owner.

Owner resolution should use this priority order:

1. explicit `--owner-user-id`;
2. a unique `--owner-query` contact search result;
3. LoopX agent profile metadata such as `owner_lark_user_id`;
4. the current authenticated Lark user for local single-owner runs.

Real owner notification should require an explicit execution flag and the
minimum send scope required by Lark. Dry-run mode should remain the default.

## Review Checklist

Before widening this capability, verify:

- fixture smoke covers the artifact contract without private data;
- external reads require `--execute-read`;
- external sends require a separate explicit flag;
- generated digests truncate source excerpts and keep message ids as evidence;
- public docs and smokes contain only synthetic Lark ids and public-safe text.
