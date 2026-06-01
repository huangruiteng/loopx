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
history drill-down. The first-screen `Goal Directory` is the multi-project
switcher: it lists every known goal, its public-safe domain, attention state,
latest run, and run counts before the operator drills into queue or history
detail.

When a selected goal has a compact run record, the run-history panel also shows
a `Reward CLI Draft`. It is intentionally local-only and defaults to
`--dry-run`; browser writes to private runtime indexes are not part of this
surface yet.

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
