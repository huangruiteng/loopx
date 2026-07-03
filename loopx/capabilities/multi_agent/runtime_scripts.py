from __future__ import annotations


SCOPED_LOOPX_WRAPPER_PY = r"""
import os
from pathlib import Path

project = Path(os.environ["LOOPX_PROJECT"])
real = os.environ["LOOPX_REAL_CLI"]
registry = os.environ["LOOPX_REGISTRY"]
runtime = os.environ["LOOPX_RUNTIME_ROOT"]
bin_dir = project / ".local" / "bin"
bin_dir.mkdir(parents=True, exist_ok=True)

json_target = bin_dir / "loopx-json"
json_target.write_text(
    "#!/usr/bin/env python3\n"
    "import os, stat, sys\n"
    f"real = {real!r}\n"
    f"registry = {registry!r}\n"
    f"runtime = {runtime!r}\n"
    "explicit = os.environ.get('LOOPX_MACHINE_JSON') == '1' or os.environ.get('LOOPX_ALLOW_TTY_JSON') == '1' or os.environ.get('LOOPX_ALLOW_VISIBLE_JSON') == '1'\n"
    "stdout_mode = os.fstat(sys.stdout.fileno()).st_mode\n"
    "stdout_is_file = stat.S_ISREG(stdout_mode)\n"
    "if not explicit and not stdout_is_file:\n"
    "    print('\\n[LoopX machine JSON hidden]\\nraw JSON is not printed in visible panes.\\n')\n"
    "    print('Use $LOOPX_PANE_LOOPX for human-readable output, or redirect machine JSON:')\n"
    "    print('  mkdir -p \"$LOOPX_PANE_ARTIFACT_DIR\"')\n"
    "    print('  $LOOPX_PANE_LOOPX_JSON <command> > \"$LOOPX_PANE_ARTIFACT_DIR/<name>.public.json\"')\n"
    "    print('$LOOPX_PANE_LOOPX_JSON is a command path, not an output file.')\n"
    "    print('It injects --format json unless you pass an explicit --format.')\n"
    "    print('Internal launcher pipes must set LOOPX_MACHINE_JSON=1 explicitly.')\n"
    "    raise SystemExit(2)\n"
    "args = sys.argv[1:]\n"
    "has_format = any(arg == '--format' or arg.startswith('--format=') for arg in args)\n"
    "if not has_format:\n"
    "    args = ['--format', 'json'] + args\n"
    "os.execv(real, [real, '--registry', registry, '--runtime-root', runtime] + args)\n",
    encoding="utf-8",
)
json_target.chmod(0o700)

human_target = bin_dir / "loopx"
human_target.write_text(
    "#!/usr/bin/env python3\n"
    "import os, sys\n"
    f"real = {real!r}\n"
    f"registry = {registry!r}\n"
    f"runtime = {runtime!r}\n"
    "args = sys.argv[1:]\n"
    "force = os.environ.get('LOOPX_VISIBLE_FORCE_MARKDOWN', '1') != '0'\n"
    "machine_json = os.environ.get('LOOPX_MACHINE_JSON') == '1'\n"
    "changed = False\n"
    "if force and not machine_json:\n"
    "    rewritten = []\n"
    "    index = 0\n"
    "    while index < len(args):\n"
    "        arg = args[index]\n"
    "        if arg == '--format' and index + 1 < len(args):\n"
    "            rewritten.append(arg)\n"
    "            value = args[index + 1]\n"
    "            if value == 'json':\n"
    "                value = 'markdown'\n"
    "                changed = True\n"
    "            rewritten.append(value)\n"
    "            index += 2\n"
    "            continue\n"
    "        if arg == '--format=json':\n"
    "            arg = '--format=markdown'\n"
    "            changed = True\n"
    "        rewritten.append(arg)\n"
    "        index += 1\n"
    "    args = rewritten\n"
    "if changed:\n"
    "    print('\\n[LoopX human view]\\nformat=markdown; machine_json_command=$LOOPX_PANE_LOOPX_JSON artifact_dir=$LOOPX_PANE_ARTIFACT_DIR\\n', flush=True)\n"
    "os.execv(real, [real, '--registry', registry, '--runtime-root', runtime] + args)\n",
    encoding="utf-8",
)
human_target.chmod(0o700)

tick_target = bin_dir / "loopx-pane-a2a-tick"
tick_target.write_text(
    "#!/usr/bin/env python3\n"
    "import json, os, shlex, subprocess\n"
    "from pathlib import Path\n"
    "loopx = os.environ.get('LOOPX_PANE_LOOPX') or str(Path(os.environ.get('LOOPX_PROJECT', '.')) / '.local' / 'bin' / 'loopx')\n"
    "goal = os.environ.get('LOOPX_GOAL_ID', '').strip()\n"
    "agent = os.environ.get('LOOPX_AGENT_ID', '').strip()\n"
    "role = os.environ.get('LOOPX_ROLE_ID', '').strip() or os.environ.get('LOOPX_LANE_ID', '').strip() or agent\n"
    "artifact_dir = Path(os.environ.get('LOOPX_PANE_ARTIFACT_DIR') or Path(os.environ.get('LOOPX_PROJECT', '.')) / '.local' / 'pane-artifacts' / (role or agent or 'lane'))\n"
    "artifact_dir.mkdir(parents=True, exist_ok=True)\n"
    "rounds_artifact = artifact_dir / 'pane-a2a-rounds.public.json'\n"
    "round_records = []\n"
    "def write_rounds_summary(*, ok, status, rounds_requested, worker_label=None, worker_configured=False):\n"
    "    completed = 0\n"
    "    for item in round_records:\n"
    "        if item.get('quota_status') == 0 and item.get('worker_status') in (0, None):\n"
    "            completed += 1\n"
    "    payload = {\n"
    "        'ok': bool(ok),\n"
    "        'schema_version': 'pane_local_a2a_tick_rounds_v0',\n"
    "        'source': 'pane_local_a2a_tick',\n"
    "        'goal_id': goal,\n"
    "        'agent_id': agent,\n"
    "        'role_id': role,\n"
    "        'coordination_model': 'decentralized_state_a2a',\n"
    "        'workflow_driver': False,\n"
    "        'status': status,\n"
    "        'rounds_requested': int(rounds_requested),\n"
    "        'rounds_completed': completed,\n"
    "        'worker_label': worker_label,\n"
    "        'worker_configured': bool(worker_configured),\n"
    "        'rounds': round_records,\n"
    "        'public_boundary': {\n"
    "            'raw_logs_recorded': False,\n"
    "            'private_artifacts_recorded': False,\n"
    "            'absolute_paths_recorded': False,\n"
    "            'credentials_recorded': False,\n"
    "            'local_workspace_path_redacted': True,\n"
    "        },\n"
    "    }\n"
    "    rounds_artifact.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n"
    "if not goal or not agent:\n"
    "    print('\\n[LoopX pane A2A]\\nmissing LOOPX_GOAL_ID or LOOPX_AGENT_ID; cannot read role-local frontier.\\n', flush=True)\n"
    "    write_rounds_summary(ok=False, status='missing_goal_or_agent', rounds_requested=0)\n"
    "    raise SystemExit(2)\n"
    "def _positive_int(value, *, default):\n"
    "    try:\n"
    "        parsed = int(str(value).strip())\n"
    "    except Exception:\n"
    "        return default\n"
    "    return parsed if parsed > 0 else default\n"
    "def run(args):\n"
    "    print('\\n[LoopX pane A2A] ' + ' '.join(shlex.quote(str(arg)) for arg in args), flush=True)\n"
    "    return subprocess.call([str(arg) for arg in args])\n"
    "print(f'\\n[LoopX pane A2A] role={role} agent={agent}\\n', flush=True)\n"
    "turn = os.environ.get('LOOPX_PANE_WORKER_TURN', '').strip()\n"
    "loop = os.environ.get('LOOPX_PANE_WORKER_LOOP', '').strip()\n"
    "command = turn or loop\n"
    "if not command:\n"
    "    status = run([loopx, '--format', 'markdown', 'quota', 'should-run', '--goal-id', goal, '--agent-id', agent])\n"
    "    round_records.append({'round_index': 1, 'quota_status': status, 'worker_configured': False, 'worker_executed': False, 'worker_status': None})\n"
    "    write_rounds_summary(ok=status == 0, status='no_worker_command_configured' if status == 0 else 'quota_failed', rounds_requested=1)\n"
    "    if status != 0:\n"
    "        raise SystemExit(status)\n"
    "    print('\\n[LoopX pane A2A]\\nNo role worker-turn command is configured; continue manually with $LOOPX_PANE_LOOPX.\\n', flush=True)\n"
    "    raise SystemExit(0)\n"
    "label = 'worker-turn' if turn else 'worker-loop'\n"
    "rounds = _positive_int(os.environ.get('LOOPX_PANE_TICK_ROUNDS', '1'), default=1)\n"
    "sleep_seconds = _positive_int(os.environ.get('LOOPX_PANE_TICK_SLEEP_SECONDS', '3'), default=3)\n"
    "for round_index in range(1, rounds + 1):\n"
    "    print(f'\\n[LoopX pane A2A round {round_index}/{rounds}]\\n', flush=True)\n"
    "    status = run([loopx, '--format', 'markdown', 'quota', 'should-run', '--goal-id', goal, '--agent-id', agent])\n"
    "    round_record = {'round_index': round_index, 'quota_status': status, 'worker_label': label, 'worker_configured': True, 'worker_executed': False, 'worker_status': None}\n"
    "    round_records.append(round_record)\n"
    "    if status != 0:\n"
    "        write_rounds_summary(ok=False, status='quota_failed', rounds_requested=rounds, worker_label=label, worker_configured=True)\n"
    "        raise SystemExit(status)\n"
    "    print(f'\\n[LoopX pane A2A {label}]\\n{command}\\n', flush=True)\n"
    "    result = subprocess.call(command, shell=True, executable=os.environ.get('SHELL') or '/bin/bash')\n"
    "    round_record['worker_executed'] = True\n"
    "    round_record['worker_status'] = result\n"
    "    write_rounds_summary(ok=result == 0, status='running' if result == 0 else 'worker_failed', rounds_requested=rounds, worker_label=label, worker_configured=True)\n"
    "    if result != 0:\n"
    "        raise SystemExit(result)\n"
    "    if round_index < rounds:\n"
    "        print(f'\\n[LoopX pane A2A] waiting {sleep_seconds}s for other lanes before the next local tick\\n', flush=True)\n"
    "        subprocess.call(['sleep', str(sleep_seconds)])\n"
    "write_rounds_summary(ok=True, status='completed', rounds_requested=rounds, worker_label=label, worker_configured=True)\n"
    "raise SystemExit(0)\n",
    encoding="utf-8",
)
tick_target.chmod(0o700)
"""


CODEX_TUI_EXEC_PY = r"""
import json
import os
import subprocess

codex = os.environ["LOOPX_CODEX_BIN"]
project = os.environ["LOOPX_PROJECT"]
reasoning_effort = os.environ["LOOPX_CODEX_REASONING_EFFORT"]

args = [codex]
if os.environ.get("LOOPX_CODEX_TRUST_WORKSPACE") == "1":
    candidates = [project, os.path.realpath(project)]
    git_root = subprocess.run(
        ["git", "-C", project, "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if git_root:
        candidates.extend([git_root, os.path.realpath(git_root)])
    seen = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        args.extend(["-c", f"projects.{json.dumps(path)}.trust_level=\"trusted\""])

args.extend(["-c", f"model_reasoning_effort={reasoning_effort}", "-C", project])
os.execvp(codex, args)
"""
