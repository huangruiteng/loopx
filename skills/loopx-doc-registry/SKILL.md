---
name: loopx-doc-registry
description: Use when a connected LoopX project is asked to read, remember, record, index, register, or use a durable project material such as a Lark/wiki/design doc, research note, SOP, owner packet, migration report, benchmark paper, or external material source. Use even when the user does not mention LoopX or doc registry.
---

# LoopX Doc Registry

Use this skill for durable project materials. The goal is to make future agents
find the material from the project authority surface, not only from chat or
personal memory.

## Default Route

1. Resolve the target project and stable `goal_id` from the current repo or the
   user's named project. Prefer `.loopx/registry.json` and
   `.codex/goals/<goal-id>/ACTIVE_GOAL_STATE.md`.
2. If the material belongs to that project, register it in that project's own
   authority surface. Do not register it into `loopx-meta` just because
   the current worker discovered it.
3. If the project has a tracked `docs/meta/DOC_REGISTRY.yaml` or equivalent,
   update that first. If it does not, use `.loopx/registry.json` as the
   project-local doc registry through `authority_registry.topic_authority` and
   `authority_registry.project_materials`.
4. Run `loopx register-authority-source` with a redacted source contract.
   Raw URLs, doc ids, local private paths, comments, and source bodies must not
   be stored in public files.
5. Refresh status or state so review packets, read-only maps, dashboards, and
   heartbeat workers can find the material.

Memory extensions are allowed only as secondary personal reminders. They are
not a substitute for project-local authority registration when the project is
connected to LoopX.

## Command Shape

From the target project:

```bash
loopx --registry .loopx/registry.json register-authority-source \
  --goal-id <goal-id> \
  --source-id <stable-source-id> \
  --source-ref "<raw-url-or-private-path-to-hash>" \
  --source-kind <doc|lark_doc|wiki|paper|owner_packet|migration_report> \
  --role <public-safe-role> \
  --freshness <current|historical|unknown> \
  --owner-status <public-safe-owner-status> \
  --gate-status <readable|needs_access|owner_review_pending> \
  --boundary private_redacted \
  --revision "<public-safe-revision-label>" \
  --conflict-rule "<public-safe-conflict-rule>" \
  --topic <topic-key>
```

Use `--dry-run` first when the source classification or target project is not
obvious.

## Stop Conditions

Stop and write a project-local todo or blocker instead of registering when:

- the target project or goal is ambiguous;
- the material cannot be represented as public-safe metadata;
- registering would require reading private content that was not requested or
  permitted;
- the source conflicts with a newer owner-approved material and the conflict
  rule is unclear.
