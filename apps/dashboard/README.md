# Goal Harness Dashboard

This is the first product dashboard shell for Goal Harness. It renders the
status data contract with a React/Vite control-plane UI.

## Run

```bash
npm install
npm run build
npm run dev
```

The default screen uses the sanitized repository example at
`examples/status.example.json`, including the attention queue and compact run
history drill-down. The dashboard consumes agent-facing `goal-harness status`
JSON, but the first screen is a human operator view: `User Review Map` translates
registry/run/reward/controller signals into review states, while `Goal
Directory` remains the multi-project switcher with public-safe domain,
attention state, latest run, and run counts.
`User Actions` is the first content region because the dashboard is for the
human operator, not for raw status inspection. It lifts the selected-detail
operator logic into the first screen:
reward gates, controller opt-ins, evidence watches, Codex handoffs, and health
blocks are grouped as operator cards before the user opens a goal detail. Each
card also exposes the matching safe local path and reward-draft hint, so the
first screen stays user-facing while still pointing agents toward the CLI
contract. A compact action-kind filter lets the operator focus the first
screen on reward, controller, Codex, evidence, or health work without changing
the underlying status export. The filter is backed by the `actionKind` URL
search parameter, so focused review links survive refresh and can be shared
with another local operator or agent. The selected goal is also URL-backed via
`goalId`, which lets a shared link preserve both the review lane and the
selected goal detail. The adjacent first-screen `Selected action share`
control copies the current `actionKind`, selected `goalId`, source
`statusUrl`, and queue filters as browser UI state only. It intentionally has
one canonical copy affordance: `Copy Review Packet`. The packet follows the
selected action card, so an operator can click a different card to switch the
target instead of choosing among several copy formats. The packet combines the
review link, Chinese agree/disagree/reason/next-step template, project-agent
instructions, safe local path, reward/default hint, and local dry-run preview.
It is still a handoff artifact; it is not approval, reward append, controller
opt-in, or write-control.
The selected-goal detail starts with `Operator Decision`, which turns the
selected goal's queue item, lifecycle phase, and readiness gates into one of
the user-level stances: review or authorize, let Codex continue, wait for
evidence, or fix health first.
That same panel now includes a `Safe CLI Path`: a local dry-run, history, or
status command that matches the current stance. It is a bridge from
user-facing review to agent-facing CLI execution, not a browser write path.

When a selected goal has a compact run record, the run-history panel also shows
a `Reward CLI Draft`. It is intentionally local-only and defaults to
`--dry-run`; browser writes to private runtime indexes are not part of this
surface yet. Draft defaults are derived from the selected `Operator Decision`
and missing gates, so an evidence watch, controller opt-in, mapped handoff, and
already-rewarded run start with different decision/reward/reason/follow-up
values. The operator can still edit or reset the draft before validation.

When the dashboard is loaded from the loopback `Live` source, the same panel can
send that draft to `POST /reward/dry-run` for local validation. The endpoint
returns a compact validation result, the Chinese active-state summary Codex can
write after a real reward append, and the project-agent history command. It
never appends to the run index.
Durable reward should be recorded as a run-bound `human_reward` overlay through
`goal-harness reward`; active state may summarize the reward afterward, but it
should not be the only source of truth for multi-agent reward signals.
When a real CLI append should also update the active goal state, use
`goal-harness reward --write-active-state-summary`; the dashboard endpoint
remains dry-run only.

## Load Live Status

Start a local status server from the project you want to inspect:

```bash
goal-harness serve-status --port 8765
```

Then run the dashboard and use the `Live` source button, or load this URL from
the source control:

```text
http://127.0.0.1:8765/status.json
```

The status server binds to `127.0.0.1` by default and sends no-store JSON with
local CORS headers for the Vite dashboard.

It also serves `POST /reward/dry-run` for validating the selected goal/run and
public-safe reward text. This is a dry-run endpoint only; recording feedback
still goes through `goal-harness reward`.

## Load Static Status

Use a local static export:

```bash
python3 -m goal_harness.cli --format json status > apps/dashboard/public/status.local.json
cd apps/dashboard
npm run dev
```

Then load `/status.local.json` from the dashboard source control.

You can also import a JSON file directly in the browser, or load a local API
URL that returns the same `goal-harness --format json status` shape.

## Browser Smokes

Dashboard browser smokes are explicit because they start a temporary Vite
server and require the local Playwright CLI wrapper:

```bash
node examples/dashboard-throttled-browser-smoke.mjs
node examples/dashboard-operator-gate-browser-smoke.mjs
```

The throttled smoke protects the "quiet scheduling state" first screen. The
operator-gate smoke protects planned high-complexity goals: they should appear
as controller/user actions, not Codex-ready work.
