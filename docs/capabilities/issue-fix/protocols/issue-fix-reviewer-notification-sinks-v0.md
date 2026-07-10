# issue_fix_reviewer_notification_sinks_v0

`issue_fix_reviewer_notification_sinks_v0` extends the canonical GitHub
reviewer request with bounded secondary delivery. The first adapter sends an
idempotent Lark/Feishu group message that mentions the same repository-grounded
reviewer and then reads the message back. The sink does not select a different
reviewer and never replaces GitHub review state as the source of truth.
The result contract and adapter injection point are provider-neutral; the
public CLI currently exposes only the bounded `lark_chat` adapter.

## Position In The Flow

The order is fixed:

1. `reviewer-plan` ranks candidates from repository-native evidence;
2. `reviewer-request` verifies author exclusion and establishes canonical
   GitHub coverage through a formal request or its permission-only comment
   fallback;
3. configured secondary sinks notify the same verified reviewer;
4. `pr-lifecycle` continues to derive review state from GitHub.

In no-write preview mode, a sink may validate its local configuration against
the selected reviewer. In execute mode, a secondary send is skipped unless the
canonical GitHub notification is already verified. A secondary failure is
reported separately and does not erase a successful GitHub request.

## Local-Private Input

`--notification-sinks-json` consumes
`issue_fix_reviewer_notification_sinks_input_v0`. The file is deliberately a
local capability packet rather than public issue-fix state:

```json
{
  "schema_version": "issue_fix_reviewer_notification_sinks_input_v0",
  "receipts": [],
  "sinks": [
    {
      "sink_kind": "lark_chat",
      "sink_instance_key": "project-review-lane",
      "identity_scope": "project_dedicated",
      "bot_profile": "project-review-bot-profile",
      "bot_display_name": "Project Review Bot",
      "destination_id": "<private-chat-id>",
      "reviewer_identities": {
        "@service-owner": {
          "member_id": "<private-member-id>",
          "display_name": "Service Owner"
        }
      }
    }
  ]
}
```

`bot_profile`, `destination_id`, and `member_id` are execution inputs. They are
never copied into the result, domain state, todo, Kanban, PR, or public log.
The first contract requires a named, project-dedicated bot profile and expected
`bot_display_name`, verifies the live bot identity before every send, and
rejects shared/default or mismatched identities. This prevents a long-running
project employee from silently speaking as an unrelated application.

Identity mapping is advisory until both sides are verified: the GitHub handle
must come from the live author-excluding reviewer packet, and the messaging
member must be resolved in the approved destination. Missing or ambiguous
mapping produces `reviewer_notification_identity_unresolved` without sending.

## Authority, Idempotency, And Verification

The same standing reviewer-notification authority that permits the canonical
request may permit an explicitly configured secondary sink. `--execute` is the
write assertion; preview never calls the provider.

Each logical `(repository, PR, sink instance, reviewer set)` produces a stable
`sha256:` idempotency key. The Lark adapter derives a provider-bounded key from
that digest and embeds a compact marker in the message. The full verified key
is returned as a receipt. Callers store only that compact receipt in existing issue-fix state
and pass it back on retry; a matching receipt returns `already_notified`
without a provider call.

A zero exit status is insufficient. The adapter requires a message id from the
send response, fetches that message with the same dedicated bot profile, and
verifies both the id and marker. Results distinguish `preview_ready`,
`sent_verified`, `already_notified`, `sent_unverified`, and `gate_required`.
Permission or group-membership errors become the concrete
`lark_bot_group_access_required` gate.

## Dedicated Bot Setup

For a Lark sink, provision one app/bot identity for the project lane, grant only
the scopes required for sending and group/member resolution, publish the app,
and have the target group's owner or administrator install it. A local named
CLI profile selects those credentials explicitly. The contract never falls
back to the machine's default bot profile.

The setup gate should tell the owner exactly which missing invariant to repair:

- dedicated app/bot exists and has the intended visible name;
- bot capability is enabled and the version is published;
- send and approved chat/member-read scopes are granted;
- the bot is a member of the approved destination;
- each GitHub reviewer maps to one verified destination member.

## Public-Safety Boundary

Every public result keeps these fields false:

- `private_destination_captured`
- `private_member_ids_captured`
- `private_bot_profile_captured`
- `raw_provider_payload_captured`

Only the public PR URL, reviewer handles, sink kind, status, compact blocker,
and hashed receipts may leave the adapter. Credentials, raw member rosters,
chat identifiers, message identifiers, provider errors, and local config paths
remain private.

## Validation

Run:

```bash
python3 examples/issue-fix-reviewer-notification-sink-smoke.py
python3 examples/issue-fix-reviewer-request-smoke.py
```

The provider-neutral fixture covers preview, dedicated-identity enforcement,
author exclusion, identity-resolution gates, one send plus readback, stable
receipt retry, permission classification, unverified writes, and public-safety
redaction. The reviewer-request smoke proves the sink is a real post-canonical
call site rather than a disconnected adapter.
