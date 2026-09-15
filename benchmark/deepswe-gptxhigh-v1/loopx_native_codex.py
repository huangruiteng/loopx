#!/usr/bin/env python3
"""The LoopX arm, driven through LoopX's own product path.

The first LoopX arm measured the wrong thing.  It called `loopx turn run-once`
from an outer loop of my own, four times, against a goal document I hand-wrote
with four stages in it.  `benchmark/deepswe/README.md` rules that out in as
many words -- the treatment must not be "an outer polling loop labeled as Goal
mode" -- and it makes the distinction a formal gate: "a clean run can still be
uncountable when the treatment did not execute the preregistered LoopX path".
Under LoopX's own standard those 54 results are uncountable.  They describe my
wrapper, not this product.

The real path, all of it LoopX's:

    install_native_codex_profile      scripts/install-local.sh builds a release
                                      snapshot and installs the seven LoopX skills
                                      into a profile-owned CODEX_HOME
    loopx bootstrap                   LoopX writes .loopx/registry.json and
                                      .codex/goals/<id>/ACTIVE_GOAL_STATE.md,
                                      with its own execution profile
    loopx configure-goal              registers the peer identity
    render_native_codex_goal_prompt   the installed CLI renders the real Goal
                                      body -- the thing I used to hand-write
    run_native_goal_process_until_terminal
                                      codex app-server owns continuation while
                                      the Goal stays active; nothing here counts
                                      turns

`required_skill_ids` makes `skills/list` a precondition of thread creation, so a
run in which Codex never discovered the LoopX skills fails before model work
instead of quietly scoring as a LoopX result.

Everything Pier does to stand Codex up is inherited from GoalCodex, which also
already owns the app-server transaction (it copies LoopX's own
`native_codex_goal.py` into the container).  Only three things differ from the
Goal arm: where CODEX_HOME points, who wrote the objective, and whether the
skills gate is armed.  That is the intended contrast -- the same host, the same
transaction, LoopX present or absent.

The profile is built on the host and shipped, rather than installed in the
container: `install-local.sh` is offline (no pip, npm, curl, wget, git clone or
apt in 872 lines, so the sandbox is not the obstacle), but it verifies that its
source tree is a clean checkout, and the container receives a tarball of the
`loopx` package with no `.git` to verify.  Building it once on the host keeps
`source_clean` a real claim.  Both sides use the same absolute path so the
release snapshot's symlinks stay valid.

Usage:

    MR_AGENT=loopx_native_codex:LoopxNativeCodex MR_MODEL=openai/gpt-5.5 \
      ./run.sh --all -i <task>

Environment:

    MR_LOOPX_PREFLIGHT=1     prove skills discovery and Goal attachment, then
                             stop before any model turn -- costs nothing
    MR_LOOPX_PROFILE_ROOT    where the profile lives on host and in container
                             (default /tmp/loopx-profile; must match on both)
    MR_LOOPX_ROOT            LoopX checkout to install from
    MR_GOAL_TIMEOUT_SEC      ceiling for the continuation loop
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

from goal_codex import GoalCodex, _CODEX_EXEC_MARKER, _REMOTE_DIR

_PROFILE_ROOT = os.environ.get(
    "MR_LOOPX_PROFILE_ROOT", "/tmp/loopx-profile"
)
_LOOPX_ROOT = os.path.expanduser(
    os.environ.get(
        "MR_LOOPX_ROOT",
        str(Path(__file__).resolve().parents[1] / "wen" / "loopx"),
    )
)
_GOAL_ID = "deepswe-task"
_AGENT_ID = "deepswe-codex"
_PROJECT = "/app"
_RUNTIME_PROFILES = {
    "ssh-goal": "codex_app_ssh_goal",
    "codex-cli": "codex_cli",
    "heartbeat": "outer_controller",
}
# Deliberately not GoalCodex's objective.txt: that file is written after this
# runs, so sharing the name would let the Goal arm's hand-written objective
# overwrite the one LoopX rendered.
_OBJECTIVE_FILE = f"{_REMOTE_DIR}/loopx_objective.txt"
_GOAL_DOC_FILE = f"{_PROFILE_ROOT}/goal-doc.md"
_WEN_COMPAT = os.environ.get("MR_LOOPX_WEN_COMPAT", "1") not in ("", "0")
_SOURCE_DIR = Path(__file__).resolve().parent
_RUNNER_SOURCES = {
    "ssh-goal": _SOURCE_DIR / "loopx_wen_native_runner.py",
    "codex-cli": _SOURCE_DIR / "loopx_codex_cli_runner.py",
    "heartbeat": _SOURCE_DIR / "loopx_heartbeat_supervisor.py",
}
_SUPPORT_SOURCES = (
    _SOURCE_DIR / "workspace_delivery.py",
    _SOURCE_DIR / "codex_nosandbox_wrapper.py",
)


def build_host_profile(loopx_root: str = _LOOPX_ROOT,
                       profile_root: str = _PROFILE_ROOT) -> dict:
    """Install the formal release snapshot once, on the host.

    Reuses an existing profile: the installer refuses a non-empty target on
    purpose, because mixing installation revisions would invalidate the
    treatment, and re-installing per task would repeat that work 54 times.
    """
    sys.path.insert(0, loopx_root)
    from loopx.capabilities.benchmark_toolkit.native_codex_profile import (
        compact_native_codex_profile_receipt,
        inspect_native_codex_profile,
        install_native_codex_profile,
    )

    target = Path(profile_root)
    if target.exists() and any(target.iterdir()):
        profile = inspect_native_codex_profile(target, source_root=loopx_root)
    else:
        profile = install_native_codex_profile(loopx_root, target)
    return compact_native_codex_profile_receipt(profile)


class LoopxNativeCodex(GoalCodex):
    """Codex with LoopX installed, driven by LoopX's rendered Goal."""

    loopx_mode = "ssh-goal"

    async def exec_as_agent(self, environment, command, env=None, **kwargs):  # noqa: ANN001
        # Intercept the same marker GoalCodex does, not the command it builds.
        # GoalCodex reaches the launch through `super().exec_as_agent`, so an
        # override keyed on `run_goal.py` is never called: the first version of
        # this arm silently shipped no profile, armed no skills gate, and still
        # produced a receipt that looked like a LoopX run.  Everything below is
        # therefore handed over through the environment, which GoalCodex reads
        # while building its own command.
        if _CODEX_EXEC_MARKER not in str(command):
            return await super().exec_as_agent(environment, command, env=env, **kwargs)

        profile_receipt = build_host_profile()
        mode = self.loopx_mode
        runtime_profile = _RUNTIME_PROFILES[mode]
        # GoalCodex owns the common Pier setup and command interception, but the
        # three treatments must not share one execution surface. ssh-goal uses
        # native app-server Goal attachment, codex-cli uses LoopX's built-in
        # ``turn run-once`` Codex host, and heartbeat uses a recurring external
        # supervisor which launches one fresh host wake per cadence tick.
        self._goal_runner_source = _RUNNER_SOURCES[mode]
        self._goal_runner_env = {
            "LOOPX_CLI": f"{_PROFILE_ROOT}/bin/loopx",
            "LOOPX_REGISTRY": f"{_PROJECT}/.loopx/registry.json",
            "LOOPX_RUNTIME_ROOT": f"{_PROJECT}/.loopx/runtime",
            "LOOPX_GOAL_ID": _GOAL_ID,
            "LOOPX_AGENT_ID": _AGENT_ID,
            "LOOPX_RECOVER_BLOCKED": "1",
            "LOOPX_MODE": mode,
        }
        treatment_env = dict(env or {})
        treatment_env["LOOPX_WEN_COMPAT"] = "1" if _WEN_COMPAT else "0"
        parent = str(Path(_PROFILE_ROOT).parent)
        name = Path(_PROFILE_ROOT).name

        await super().exec_as_agent(
            environment, command=f"mkdir -p {shlex.quote(_REMOTE_DIR)}", env=treatment_env
        )

        # Ship the installed profile to the identical absolute path: the release
        # snapshot's `bin/loopx` is a symlink into releases/, so a different path
        # would leave a dangling CLI and no Goal body could be rendered at all.
        with tempfile.TemporaryDirectory() as tmp:
            tarball = Path(tmp) / "profile.tar.gz"
            subprocess.run(
                ["tar", "czf", str(tarball), "-C", parent, name], check=True
            )
            receipt_path = Path(tmp) / "profile_receipt.json"
            receipt_path.write_text(
                json.dumps(profile_receipt, indent=2), encoding="utf-8"
            )
            bootstrap_path = Path(tmp) / "loopx_product_bootstrap.py"
            bootstrap_path.write_text(_BOOTSTRAP, encoding="utf-8")
            for local, remote in (
                (tarball, f"{_REMOTE_DIR}/profile.tar.gz"),
                (receipt_path, f"{_REMOTE_DIR}/profile_receipt.json"),
                (bootstrap_path, f"{_REMOTE_DIR}/loopx_product_bootstrap.py"),
                (self._goal_runner_source, f"{_REMOTE_DIR}/{self._goal_runner_source.name}"),
                *(
                    (source, f"{_REMOTE_DIR}/{source.name}")
                    for source in _SUPPORT_SOURCES
                ),
            ):
                await environment.upload_file(str(local), remote)

        await super().exec_as_agent(
            environment,
            command=(
                f"mkdir -p {shlex.quote(parent)} && "
                f"tar xzf {shlex.quote(_REMOTE_DIR)}/profile.tar.gz "
                f"-C {shlex.quote(parent)} && "
                f"test -x {shlex.quote(_PROFILE_ROOT)}/bin/loopx && "
                f"chmod +x {shlex.quote(_REMOTE_DIR)}/codex_nosandbox_wrapper.py"
            ),
            env=treatment_env,
        )

        # Bootstrap renders the product-owned objective before GoalCodex reaches
        # its normal upload phase.  Seed the task file here so a fresh container
        # does not fail before the later upload (which also sends objective.txt
        # and the native module).
        with tempfile.TemporaryDirectory() as tmp:
            task_path = Path(tmp) / "task.txt"
            task_path.write_text(self._goal_instruction or "", encoding="utf-8")
            await environment.upload_file(str(task_path), f"{_REMOTE_DIR}/task.txt")

        # LoopX writes its own registry, goal state and Goal body.  Nothing in
        # this arm authors goal content: the hand-written four-stage document
        # the previous arm used is exactly what made its results describe a
        # prompt of mine rather than this product.
        await super().exec_as_agent(
            environment,
            command=(
                # The profile is installed on the host, so its launcher records
                # the host's Python path -- a uv-managed interpreter that does
                # not exist in the task image, which made every CLI call exit 2
                # with "configured Python executable not found".  LOOPX_PYTHON
                # redirects the launcher at the container's own interpreter
                # without reinstalling, so the release snapshot stays the one
                # whose cleanliness was proven on the host.
                f"cd {shlex.quote(_PROJECT)} && "
                "export LOOPX_PYTHON=\"$(command -v python3)\" && "
                "python3 -c 'import sys; assert sys.version_info >= (3, 11), sys.version' && "
                f"python3 {shlex.quote(_REMOTE_DIR)}/loopx_product_bootstrap.py "
                f"--profile-root {shlex.quote(_PROFILE_ROOT)} "
                f"--project {shlex.quote(_PROJECT)} "
                f"--goal-id {_GOAL_ID} --agent-id {_AGENT_ID} "
                f"--runtime-profile {runtime_profile} "
                f"--goal-doc-file {shlex.quote(_GOAL_DOC_FILE)} "
                f"--task-file {shlex.quote(f'{_REMOTE_DIR}/task.txt')} "
                f"--objective-out {shlex.quote(_OBJECTIVE_FILE)} "
                f"--receipt-out {shlex.quote(_REMOTE_DIR)}/loopx_product.json"
            ),
            env=treatment_env,
        )

        os.environ["MR_GOAL_OBJECTIVE_FILE"] = _OBJECTIVE_FILE
        os.environ["MR_GOAL_CODEX_HOME"] = f"{_PROFILE_ROOT}/codex-home"
        os.environ["MR_GOAL_REQUIRED_SKILL_IDS"] = ",".join(
            profile_receipt["required_skill_ids"]
        )
        # Arm GoalCodex's LOOPX_PYTHON export for the actual app-server process,
        # not just the earlier bootstrap script -- Codex's own mid-turn `loopx`
        # calls run inside app-server's environment and hit the same failure
        # bootstrap did until this is set here too.
        os.environ["MR_GOAL_ARM_LOOPX_PYTHON"] = "1"
        if os.environ.get("MR_LOOPX_PREFLIGHT", "") not in ("", "0"):
            os.environ["MR_GOAL_PREFLIGHT"] = "1"

        # Give the profile's CODEX_HOME the credentials and provider settings
        # Pier wrote into its own.  Pointing app-server at the formally
        # installed CODEX_HOME is what makes `skills/list` find LoopX, but that
        # directory ships only `skills/` -- no auth.json, no config.toml, so no
        # API key and no gateway base_url.  A run configured that way discovers
        # every skill, starts, and then waits for a model it has no address
        # for: one smoke hung for 85 minutes and the gateway's call count never
        # moved.  The preflight cannot catch it, because Goal attachment stops
        # before the first model turn and needs no credentials.
        #
        # Only top-level files are copied.  `cp -a` of the whole directory
        # would merge Pier's own skills over the formal install, and which
        # skills app-server discovers is the one thing this arm must not
        # improvise.
        profile_home = f"{_PROFILE_ROOT}/codex-home"
        await super().exec_as_agent(
            environment,
            command=(
                'for f in "$CODEX_HOME"/*; do '
                f'[ -f "$f" ] && cp -f "$f" {shlex.quote(profile_home)}/; '
                "done; "
                # GoalCodex disables web_search by appending to *its* CODEX_HOME
                # after this runs, so the copy above would leave the profile
                # without it and give this arm a hosted search tool the other
                # two do not have -- an advantage no network isolation would
                # reveal, since the provider runs the search.
                f'grep -q "^web_search" {shlex.quote(profile_home)}/config.toml '
                f'|| printf "\\nweb_search = \\"disabled\\"\\n" '
                f'>> {shlex.quote(profile_home)}/config.toml; '
                f'test -s {shlex.quote(profile_home)}/config.toml '
                '|| { echo "no config.toml reached the LoopX profile" >&2; exit 1; }'
            ),
            env=env,
        )

        # Capture LoopX's own trace before the container is torn down.  Pier's
        # own teardown copies `$CODEX_HOME/sessions` into the job directory,
        # but that is Pier's CODEX_HOME -- this arm points app-server at the
        # profile's instead, so codex writes its session transcript to
        # `{profile_home}/sessions` and Pier's copy finds nothing.  The first
        # smoke run's job directory logged "No Codex session directory found"
        # for exactly this reason: the transcript existed, just one directory
        # over from where anyone looked for it.
        #
        # This has to be a second, separate call rather than the launch command
        # rewritten to append a capture step.  `command` at this point still
        # reads "codex exec ..." -- GoalCodex.exec_as_agent below only checks
        # for that marker's presence and then throws the string away, building
        # its own `run_goal.py` invocation from internal state.  Appending shell
        # onto a string GoalCodex never looks at silently does nothing, which is
        # exactly the bug that made the CODEX_HOME swap above necessary: this
        # arm keeps stumbling on places where a value must go through GoalCodex
        # rather than through the string it happens to be holding.
        capture_dir = "/logs/agent/loopx_trace"
        try:
            return await super().exec_as_agent(
                environment, command=command, env=env, **kwargs
            )
        finally:
            await super().exec_as_agent(
                environment,
                command=(
                    f"mkdir -p {shlex.quote(capture_dir)}; "
                    f'if [ -d {shlex.quote(profile_home)}/sessions ]; then '
                    f'cp -R {shlex.quote(profile_home)}/sessions '
                    f'{shlex.quote(capture_dir)}/sessions; fi; '
                    f'find /app/.codex/goals -name ACTIVE_GOAL_STATE.md '
                    f'-exec cp {{}} {shlex.quote(capture_dir)}/ACTIVE_GOAL_STATE.md \\; '
                    f'2>/dev/null; '
                    # Same LOOPX_PYTHON fix as the app-server launch above: this
                    # CLI call is yet another separate shell, and without its own
                    # export it fails with the same "configured Python
                    # executable not found" that showed up twice in mid-turn
                    # calls before the launch-side fix existed.
                    'export LOOPX_PYTHON="$(command -v python3)"; '
                    f'{shlex.quote(_PROFILE_ROOT)}/bin/loopx '
                    f'--registry {shlex.quote(_PROJECT)}/.loopx/registry.json '
                    f'--runtime-root {shlex.quote(_PROJECT)}/.loopx/runtime '
                    f'--format json todo list --goal-id {_GOAL_ID} '
                    f'> {shlex.quote(capture_dir)}/todo_list.json 2>&1; '
                    "true"
                ),
                env=env,
            )


class LoopxCodexCliCodex(LoopxNativeCodex):
    """LoopX governed Turns executed by the real Codex CLI host."""

    loopx_mode = "codex-cli"


class LoopxHeartbeatCodex(LoopxNativeCodex):
    """LoopX generic CLI heartbeat executed by a recurring supervisor."""

    loopx_mode = "heartbeat"


# Runs inside the container: bootstrap, register the peer, render the Goal body.
_BOOTSTRAP = '''\
import argparse, json, os, subprocess, sys
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--profile-root", required=True)
p.add_argument("--project", required=True)
p.add_argument("--goal-id", required=True)
p.add_argument("--agent-id", required=True)
p.add_argument("--goal-doc-file", required=True)
p.add_argument("--task-file", required=True)
p.add_argument("--runtime-profile", required=True)
p.add_argument("--objective-out", required=True)
p.add_argument("--receipt-out", required=True)
a = p.parse_args()

cli = f"{a.profile_root}/bin/loopx"
registry = f"{a.project}/.loopx/registry.json"
runtime = f"{a.project}/.loopx/runtime"
base = [cli, "--registry", registry, "--runtime-root", runtime, "--format", "json"]
steps = {}


def run(name, args):
    out = subprocess.run(base + args, capture_output=True, text=True)
    try:
        payload = json.loads(out.stdout)
    except Exception:
        payload = {}
    # Keep returncode and both streams for every step.  Pier reports a failed
    # agent command as "Command failed" and discards its output, so a step that
    # dies here is otherwise invisible: the first run of this arm failed exactly
    # once and left nothing but that phrase in the log.
    steps[name] = {
        "returncode": out.returncode,
        "ok": payload.get("ok"),
        "error": payload.get("error"),
        "stdout_tail": out.stdout[-400:] if not payload else None,
        "stderr_tail": out.stderr[-400:],
    }
    if out.returncode or payload.get("ok") is not True:
        detail = payload.get("error") or out.stderr[-240:] or out.stdout[-240:]
        raise RuntimeError(f"{name}_failed:{detail}")
    return payload


goal_doc = Path(a.goal_doc_file)
goal_doc.write_text(
    Path(a.task_file).read_text(encoding="utf-8"),
    encoding="utf-8",
)
task_text = goal_doc.read_text(encoding="utf-8")
bootstrap_args = [
    "bootstrap", "--project", a.project, "--goal-id", a.goal_id,
    "--objective", "Complete the software engineering task described in the task file and commit the finished work.",
    "--goal-doc", str(goal_doc),
    "--adapter-kind", "read_only_project_map_v0",
    "--adapter-status", "connected-read-only",
]
if os.environ.get("LOOPX_WEN_COMPAT", "1") not in ("", "0"):
    bootstrap_args += [
        # Benchmark admission supplies one frozen task. Project-map onboarding
        # todos otherwise outrank it and measure repository housekeeping rather
        # than the requested software-engineering task.
        "--no-onboarding-scan",
        "--begin-autonomous-advance",
        "--codex-app-heartbeat",
        "yes" if a.runtime_profile == "codex_app_ssh_goal" else "no",
        "--write-scope", a.project,
    ]
else:
    bootstrap_args += ["--no-onboarding-scan", "--codex-app-heartbeat", "ask"]
run("bootstrap", bootstrap_args)
run("configure_goal", ["configure-goal", "--goal-id", a.goal_id,
                       "--registered-agent", a.agent_id, "--execute"])
# The gate selects work from the todo frontier.  Keeping the task only in the
# turn input lets the model spend the whole budget on onboarding todos while
# the target repository remains untouched; wen's native driver explicitly
# inserts this P0 advancement todo for the same reason.
run("add_task_todo", ["todo", "add", "--goal-id", a.goal_id,
                       "--role", "agent", "--todo-id", "deepswe-task",
                       "--text", "[P0] " + task_text, "--task-class", "advancement_task",
                       "--action-kind", "implement",
                       "--required-capability", "filesystem_write",
                       "--status", "open", "--execute"])
if os.environ.get("LOOPX_WEN_COMPAT", "1") not in ("", "0"):
    run("clear_waiting_on", ["configure-goal", "--goal-id", a.goal_id,
                              "--clear-waiting-on",
                              "--agent-work-mode", f"{a.agent_id}=active",
                              "--write-scope", a.project, "--execute"])
prompt = run("heartbeat_prompt",
             ["heartbeat-prompt", "--thin", "--goal-id", a.goal_id,
              "--agent-id", a.agent_id, "--available-capability", "shell",
              "--available-capability", "filesystem_write",
              "--runtime-profile", a.runtime_profile, "--cli-bin", cli])

body = prompt.get("task_body")
if body:
    Path(a.objective_out).write_text(body, encoding="utf-8")
    steps["goal_body_chars"] = len(body)
else:
    steps["fatal"] = "heartbeat-prompt returned no task_body"
Path(a.receipt_out).write_text(json.dumps(steps, indent=2), encoding="utf-8")
print(json.dumps(steps, indent=2))
raise SystemExit(0 if body else 1)
'''
