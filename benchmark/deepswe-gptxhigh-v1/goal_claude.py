"""Claude Code arms for the DeepSWE sweep: plain, and driven by LoopX.

The Claude Code counterpart of `goal_codex.py`, and structured the same way for
the same reason: Pier's `ClaudeCode.run()` is one long method whose setup (auth
resolution, CLAUDE_CONFIG_DIR, skills/memory/MCP registration, session capture,
trajectory conversion) would have to be duplicated and kept in step with
upstream.  Intercepting the single command that matters leaves all of that
untouched, and if Pier ever changes how it invokes Claude Code the marker below
stops matching and the run fails loudly instead of quietly degrading to plain
Claude Code — which would look like a successful LoopX run with no loop in it.

There is no `GoalClaudeCode` here.  Codex has a native Goal API (app-server
`thread/goal/set`) that can own a continuation loop; Claude Code's equivalent
is its native `/loop`, which is an interactive slash command with no headless
(`--print`) entry point, so it cannot be exercised inside Pier's one-shot
container invocation.  On this harness the Claude Code contrast is therefore
plain vs LoopX-driven, not native-Goal vs LoopX.

Usage:

    MR_AGENT=claude-code MR_CLAUDE_ARM=plain ./run.sh --all -i <task>
    MR_AGENT=claude-code MR_CLAUDE_ARM=loopx ./run.sh --all -i <task>

Environment:

    MR_LOOPX_ROOT          path to the LoopX checkout on the host
    MR_LOOPX_QUOTA         max governed Turns per task (default 4)
    MR_LOOPX_TURN_TIMEOUT  per-Turn ceiling in seconds (default 1200)
"""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

from pier.agents.installed.claude_code import ClaudeCode
from pier.models.trial.paths import EnvironmentPaths

# Pier builds exactly one command containing this; see
# pier/agents/installed/claude_code.py, ClaudeCode.run().
_CLAUDE_EXEC_MARKER = "--output-format=stream-json"

_REMOTE_DIR = "/tmp/loopx-goal"
_LOOPX_MOUNT = "/opt/loopx"
_DEFAULT_LOOPX_ROOT = str(
    Path(__file__).resolve().parents[1] / "loopx-official-latest"
)

# Carried over verbatim from goal_codex.py.  DeepSWE grades a committed patch,
# so committing belongs in the objective — a run that solves the task and never
# commits scores zero — and both arms must be prompted with the same words or
# "the effect of that wording" folds into the measured difference.
_OBJECTIVE = (
    "Complete the software engineering task described in the task file. "
    "Work in the repository, keep existing behaviour intact, verify the change "
    "against the repository's own tests, and commit the finished work to a new "
    "branch off main. The goal is complete only once the change is committed."
)

_OBJECTIVE_STAGED = (
    "Complete the software engineering task described in the task file, in "
    "stages, and do not consider the goal complete until every stage is done.\n"
    "Stage 1: make the target behaviour work and commit it.\n"
    "Stage 2: re-read the task description and check your implementation "
    "against every requirement it states, including ones you did not address "
    "in stage 1. Fix what is missing and commit.\n"
    "Stage 3: look for behaviour you may have broken elsewhere in the "
    "repository, run the wider test suite, and fix any regression you find.\n"
    "Stage 4: consider edge cases the tests may not cover — empty inputs, "
    "concurrent use, error paths — and handle the ones the task implies.\n"
    "The goal is complete only after stage 4."
)


def _objective() -> str:
    return _OBJECTIVE_STAGED if os.environ.get("MR_GOAL_OBJECTIVE") == "staged" else _OBJECTIVE


class PlainClaudeCode(ClaudeCode):
    """The control arm: stock Claude Code, plus the objective text.

    The objective is appended for the same reason `PlainCodex` appends it: the
    LoopX arm necessarily carries that wording in its staged Todo, so
    withholding it here would make the comparison partly about the prompt
    instead of about the loop.

    What remains different is intrinsic and is the treatment: `claude --print`
    runs until the model stops and then exits, while LoopX runs a Turn, requires
    an independent validator to prove the postcondition, and only then asks for
    the next one.
    """

    async def run(self, instruction, environment, context):  # type: ignore[override]
        return await super().run(
            f"{instruction}\n\n{_objective()}", environment, context
        )


class LoopxClaudeCode(ClaudeCode):
    """Claude Code driven by LoopX's governed Turn loop.

    The plain arm stops when the model says it is finished.  LoopX is the arm
    where something other than the model decides: it runs one Turn, requires an
    independent validator to prove HEAD moved and the tree is clean, and only
    then commits the Todo and spends quota.  Turn two happens because the
    controller asks for it, not because the model volunteered.

    Everything else is held to the plain arm — same model, same
    `bypassPermissions`, same container, same task set, same objective wording.

    The validator is deliberately structural (HEAD moved, tree clean) and never
    the hidden tests: the benchmark runs its verifier after the trial and
    outside the controller, so a loop that could read the grade could steer on
    it.  What the validator proves is that the agent really committed work
    rather than declaring success over an unchanged tree.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loopx_instruction: str | None = None
        self._loopx_swapped = False

    async def run(self, instruction, environment, context):  # type: ignore[override]
        self._loopx_instruction = instruction
        self._loopx_swapped = False
        try:
            return await super().run(instruction, environment, context)
        finally:
            if not self._loopx_swapped:
                raise RuntimeError(
                    "LoopxClaudeCode never intercepted a `claude --print` command "
                    "— this run would have been plain Claude Code with no LoopX loop."
                )

    async def exec_as_agent(self, environment, command: str = "", env=None, **kwargs):  # type: ignore[override]
        if _CLAUDE_EXEC_MARKER not in command:
            return await super().exec_as_agent(
                environment, command=command, env=env, **kwargs
            )

        self._loopx_swapped = True

        loopx_root = Path(os.environ.get("MR_LOOPX_ROOT", _DEFAULT_LOOPX_ROOT))
        if not (loopx_root / "loopx" / "__init__.py").is_file():
            raise FileNotFoundError(f"LoopX package not found under {loopx_root}")
        here = Path(__file__).resolve().parent

        await super().exec_as_agent(
            environment, command=f"mkdir -p {shlex.quote(_REMOTE_DIR)}", env=env
        )

        # LoopX arrives as one tarball rather than a bind mount: the container is
        # created by Pier from its own compose file, so an agent cannot add a
        # mount to it, and uploading 710 files one at a time is not a serious
        # option.
        with tempfile.TemporaryDirectory() as tmp:
            tarball = Path(tmp) / "loopx.tar.gz"
            subprocess.run(
                ["tar", "czf", str(tarball), "-C", str(loopx_root), "loopx"],
                check=True,
            )
            task_path = Path(tmp) / "task.txt"
            task_path.write_text(self._loopx_instruction or "", encoding="utf-8")
            for local, remote in (
                (tarball, f"{_REMOTE_DIR}/loopx.tar.gz"),
                (task_path, f"{_REMOTE_DIR}/task.txt"),
                (here / "loopx_turn_runner.py", f"{_REMOTE_DIR}/loopx_turn_runner.py"),
                (here / "loopx_claude_adapter.py", f"{_REMOTE_DIR}/loopx_claude_adapter.py"),
            ):
                await environment.upload_file(str(local), remote)

        if environment.default_user is not None:
            await self.exec_as_root(
                environment,
                command=f"chown -R {environment.default_user} {shlex.quote(_REMOTE_DIR)}",
            )
        await super().exec_as_agent(
            environment,
            command=(
                f"mkdir -p {shlex.quote(_LOOPX_MOUNT)} && "
                f"tar xzf {shlex.quote(_REMOTE_DIR)}/loopx.tar.gz "
                f"-C {shlex.quote(_LOOPX_MOUNT)} && "
                f"python3 -c 'import sys; sys.path.insert(0, \"{_LOOPX_MOUNT}\"); "
                "import loopx.cli_commands.turn'"
            ),
            env=env,
        )

        args = [
            "python3",
            f"{_REMOTE_DIR}/loopx_turn_runner.py",
            "--project", "__PWD__",
            "--task-file", f"{_REMOTE_DIR}/task.txt",
            "--runtime-root", f"{_REMOTE_DIR}/runtime",
            "--adapter", "loopx_claude_adapter.py",
            # --model is required by the runner but the adapter resolves the
            # real one from ANTHROPIC_MODEL, which Pier has already set in this
            # container from the sweep's --model.  Passing it twice would let
            # the two drift.
            "--model", (self.model_name or ""),
            "--quota", os.environ.get("MR_LOOPX_QUOTA", "4"),
        ]
        rendered = shlex.join(args).replace("'__PWD__'", '"$(pwd)"').replace(
            "__PWD__", '"$(pwd)"'
        )
        output = (EnvironmentPaths.agent_dir / "loopx-turns.json").as_posix()
        return await super().exec_as_agent(
            environment,
            command=(
                'export PATH="$HOME/.local/bin:$PATH"; '
                f"PYTHONPATH={shlex.quote(_LOOPX_MOUNT)} {rendered} "
                f"2>&1 </dev/null | tee {shlex.quote(output)}"
            ),
            env=env,
        )
