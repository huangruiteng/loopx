# Goal Harness Dashboard

This is the first product dashboard shell for Goal Harness. It renders the
status data contract with a React/Vite control-plane UI.

## Current Status

The dashboard is an experimental operator preview, not the primary Goal Harness
workflow. The CLI, status JSON, run history, and active goal files remain the
source of truth for day-to-day work. Use the dashboard for public-safe demos,
local inspection, and focused UI experiments until it receives a dedicated
product iteration pass.

## Fresh Clone Public Preview

No private Goal Harness state is required for the first dashboard preview. The
app bundles `examples/status.example.json` as its public-safe example source,
so a fresh checkout can validate and open the UI before starting any local
status server:

```bash
cd apps/dashboard
npm ci
npm run smoke:demo-readiness -- --skip-browser
npm run dev
```

Then open `http://127.0.0.1:5173/`. Use the bundled example source for a public
demo, or switch to a loopback status URL only after you have started
`goal-harness serve-status` locally. Do not commit `status.local.json` or live
status exports; they can contain local registry/runtime paths and private
project summaries.

The first read-only channel frontstage lives at `/frontstage`. It renders a
public-safe `goal_channel_projection_v0` fixture as a dense channel board with
decision, quota, user todo, agent todo, active-claim, timeline, and truth
contract lanes. Treat it as the product-path replacement for expanding the
no-dependency static HTML renderer; the Python renderer remains the fallback
demo/diagnostic surface.

The frontstage first screen is meant to teach the control-plane model before a
developer reads raw status JSON. The top operations strip answers whether the
human gate is explicit, whether agent work is active, how many lanes are
claimed, and whether recent evidence exists. The `Role Map` then separates the
owner, agent lane, and claim-owner responsibilities so a new contributor can
tell which part of the system is waiting, running, or coordinating side work.
The `Efficiency Evidence` panel pulls the public-safe self-iteration case from
the showcase catalog so the hosted frontstage can show commit-backed baseline,
actual-window, compression, and evidence-boundary signals without exposing raw
sessions. The `Showcase Motion` and `Showcase Cases` panels render the same
catalog as animated narrative lanes and compact case cards, linking back to
public GitHub case pages for deeper reading. Operations lanes are derived from
the read-only projection; showcase panels are derived only from public-safe
showcase metadata. Neither surface is browser write authority.

For live local control-plane inspection, open
`/frontstage?statusUrl=http://127.0.0.1:8766/status.json`. The route reads
`attention_queue.items[].goal_channel_projection` and stays read-only; if the
feed is missing or has no projection, the bundled demo fixture remains visible.

To create a public-safe static bundle for demos, Lark shares, or future GitHub
Pages hosting, export the frontstage with the sanitized fixture:

```bash
cd apps/dashboard
npm run export:frontstage-share
```

The default output is `/tmp/goal-harness-frontstage-share-bundle`. It includes a
compiled dashboard, `status.frontstage-share.json`, a direct `/frontstage/`
static route, a manifest, and a README with the local serve URL. The exporter
rejects local paths, private registry state, internal document hosts, raw-key
leaks, token assignments, and private key material before reporting success.
For repository Pages hosting later, rerun the same exporter with
`-- --base /goal-harness/ --out-dir <artifact-dir>` and publish only that
generated site artifact.

## Run

```bash
npm ci
npm run build
npm run dev
```

The default screen is the Chinese-first control-plane home. It is meant to
answer the operator's first questions before raw status drill-down: which
project line is active, which user todo is truly blocking, which agent todo is
high priority, which quota/guard state applies, and what evidence has already
been written back. It loads the shared global status source by default when the
loopback global server is available, so multi-project state is visible without
passing `view=share` or opening a debugging table.
Because this screen is the operator-facing home, it translates raw machine
status into Chinese decision copy. Exact tokens such as `single_surface`,
`focus_wait`, or `quota_slot_spent` may remain useful in `?view=ops` and packet
drill-downs, but the home should foreground user todos, agent priorities,
quota guard judgments, and evidence writeback in human-readable terms.

`?view=ops` remains as the explicit detailed workbench. That view keeps the
legacy operator tools: `Todo Focus`, `User Actions`, `Goal Directory`,
attention lanes, selected-goal run history, reward dry-run/append controls,
and raw queue filters. Use it when debugging status contracts, reward overlays,
or individual queue items; do not treat it as the product's main screen.

The old `view=share` URL value is tolerated as a compatibility alias for the
main control-plane home, but the dashboard normalizes non-`ops` views out of
the URL. Browser search parameters such as `actionKind`, `goalId`, `lane`,
`severity`, `statusUrl`, and `view` are UI state only. They are not approval,
reward append, controller opt-in, write-control, or durable goal truth.

The detailed ops workbench consumes the same agent-facing
`goal-harness status` JSON. Its first-screen action cards can group reward
gates, controller opt-ins, evidence watches, Codex handoffs, and health blocks;
each card may expose a safe local path and reward-draft hint. The copied
handoff remains a short `【GH Packet】` artifact with user todo, gate, safety
boundary, safe path, command, and project-agent stop rule. It is still a
handoff artifact; it is not approval, reward append, controller opt-in, or
write-control.

The selected-goal detail in `?view=ops` starts with `Operator Decision`, which
turns the selected goal's queue item, lifecycle phase, and readiness gates into
one of the user-level stances: review or authorize, let Codex continue, wait
for evidence, or fix health first. That same panel includes a `Safe CLI Path`:
a local dry-run, history, or status command that matches the current stance. It
is a bridge from user-facing review to agent-facing CLI execution, not a
browser write path.

When a selected goal has a compact run record, the run-history panel also shows
a `Reward CLI Draft`. It is intentionally local-only and defaults to
`--dry-run`; browser writes to private runtime indexes remain disabled unless
the local status server explicitly enables the reward write API. Draft defaults
are derived from the selected `Operator Decision`
and missing gates, so an evidence watch, controller opt-in, mapped handoff, and
already-rewarded run start with different decision/reward/reason/follow-up
values. The operator can still edit or reset the draft before validation.

When the dashboard is loaded from the loopback `Live` source, the same panel can
send that draft to `POST /reward/dry-run` for local validation. The endpoint
returns a compact validation result, the Chinese active-state summary Codex can
write after a real reward append, and the project-agent history command. It
also returns a `preview_id` that locks the selected goal, run, reward payload,
and current raw index count.
If the live server was started with `--enable-reward-write-api`, the dashboard
can then call `POST /reward/append` for that exact preview. The append writes
one run-bound `human_reward` overlay, refreshes status, and leaves the compact
overlay as the source of truth future agents read through `status` or
`history`.
Durable reward should be recorded as a run-bound `human_reward` overlay through
`goal-harness reward`; active state may summarize the reward afterward, but it
should not be the only source of truth for multi-agent reward signals.
When a real CLI append should also update the active goal state, use
`goal-harness reward --write-active-state-summary`; the dashboard append path
sets the same summary-write intent after the operator confirms the preview.

## Load Live Status

For the canonical multi-project home, start a global status server. This is the
normal operator view for all projects connected into the shared registry:

```bash
goal-harness serve-status --global-registry --port 8766 --limit 80
```

On macOS, keep both the status feed and the built dashboard static app running
after login with the user-level LaunchAgent helper:

```bash
../../scripts/macos-dashboard-launchagent.sh install
```

The helper starts:

```text
http://127.0.0.1:8766/status.json
http://127.0.0.1:5174/
```

Use `../../scripts/macos-dashboard-launchagent.sh restart|stop|uninstall|status`
for local service operations. `status` also probes
`http://127.0.0.1:8766/status.json` and prints the
`status_contract.schema_version`; if it is missing or below the expected
dashboard version, run `restart` before a demo so the live feed is not served by
an older daemon. Logs live under `~/Library/Logs/goal-harness/`.
The status output path is covered without touching real macOS services by
`python3 examples/macos-dashboard-launchagent-status-smoke.py`.

Then open the dashboard root:

```text
http://127.0.0.1:5174/
```

For project-local debugging or a disposable `goal-harness demo`, start a local
status server from the project you want to inspect:

```bash
goal-harness serve-status --port 8765
```

`--global-registry` is intentionally explicit: it keeps the multi-project home
on the shared registry even when you launch it from inside a project checkout,
while plain `serve-status` remains useful for project-local debugging.

Keep the dashboard app running and use `?view=ops`, the `Live` source button,
or load this project-local URL from the source control:

```text
http://127.0.0.1:8765/status.json
```

The status server binds to `127.0.0.1` by default and sends no-store JSON with
local CORS headers for the Vite dashboard.

It also serves `POST /reward/dry-run` for validating the selected goal/run and
public-safe reward text. To allow direct local dashboard submission, start the
server with the explicit write flag:

```bash
goal-harness serve-status --port 8765 --enable-reward-write-api
```

The write flag is loopback-only. Without it, the dashboard can validate a
reward draft but cannot append feedback.

## Load Static Status

Use a local static export:

```bash
python3 -m goal_harness.cli --format json status > apps/dashboard/public/status.local.json
cd apps/dashboard
npm run dev
```

Then load `/status.local.json` from the dashboard source control.

`status.local.json` is intentionally git-ignored because live status exports can
contain local registry/runtime paths and private project summaries. Keep it as a
local inspection file only. For public demos, use the sanitized
`examples/status.example.json` fixture instead of committing a live export.

You can also import a JSON file directly in the browser, or load a local API
URL that returns the same `goal-harness --format json status` shape.

## Browser Smokes

Dashboard browser smokes are explicit because they start a temporary Vite
server. For demo readiness, run the grouped public-safe smoke:

```bash
npm run smoke:demo-readiness
```

That command runs the LaunchAgent status-output smoke, the structured
`promotion-gate` fresh/warning contract smoke, the source-contract smokes, and
the three browser smokes below. In CI environments without Playwright/Chrome,
use:

```bash
python3 ../../examples/dashboard-demo-readiness-smoke.py --skip-browser
```

The individual browser smokes are still available when you want to debug one
surface:

```bash
npm run smoke:home-browser
npm run smoke:frontstage-share-bundle
npm run smoke:ops-decision-freshness
npm run smoke:promotion-readiness
node examples/dashboard-throttled-browser-smoke.mjs
node examples/dashboard-operator-gate-browser-smoke.mjs
```

The home browser smoke protects the canonical control-plane home. It uses a
public-safe four-project fixture, opens the root route without `view=share`,
checks the Chinese operator copy for user todos, agent priorities, showcase
activity, quota guard state, per-project top-4 todo status, and state
writeback, and rejects raw machine tokens such as `single_surface`,
`focus_wait`, or raw internal slot constraints on the first screen. It also captures desktop
and mobile first-screen / decision-frame screenshots under
`output/playwright/dashboard-home-visual-acceptance/` and fails on horizontal
overflow so density regressions are visible before calling the frontend broadly
usable. It uses an installed Playwright package or the Codex bundled runtime
when available, and starts Vite through the local `vite` package rather than
depending on `npm` / `npx` being on `PATH`.

The ops decision-freshness smoke protects the detailed `?view=ops` panel with
two public fixtures: a live-like zero-item summary and a stale/rebase-required
decision example. It verifies the rendered Chinese/English operator copy,
counts, top affected goal, and exact-replay wording instead of relying only on
source-string checks.

The promotion-readiness smoke protects the detailed `?view=ops` panel with
fresh, stale, and missing readiness fixtures. It verifies the status badges,
readiness/rerun decision, artifact window, age, reason, and source-of-truth copy
for canary promotion readiness. The canonical fixture/browser script is
`examples/dashboard-promotion-readiness-browser-smoke.mjs`; use the npm script
above instead of calling ad hoc duplicate filenames.
The grouped demo-readiness path also runs `examples/promotion-gate-smoke.py`
before browser checks, so the structured `gate_state`, `can_promote`, and
`should_warn` contract is covered even when browser smokes are skipped.

The throttled smoke protects the "quiet scheduling state" first screen. The
operator-gate smoke protects planned high-complexity goals: they should appear
as controller/user actions, not Codex-ready work. Those older browser smokes
still use the local Playwright CLI wrapper.
