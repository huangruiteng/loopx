#!/usr/bin/env python3
"""A `codex` stand-in that drops LoopX's sandbox flags before running the real one.

LoopX's codex-cli host is the path that works: driven through it, a Turn loop
ran four times on one task, committed a 22 KB patch and scored f2p 31/35.  Its
one problem is the sandbox — it always passes `--sandbox <mode>` (or
`-c sandbox_mode=...` when resuming), only permits read-only and
workspace-write, and both need bubblewrap, which needs unprivileged user
namespaces these containers do not have:

    bwrap: No permissions to create a new namespace

Switching to `--host generic-cli` avoided that but bought a worse problem: the
generic host carries its own scheduler contract, and eleven of sixteen turns
died at "LoopX Turn route is not host executable" before any model work, with
no route recorded to explain why.

So keep the working host and fix the flag instead.  This sits earlier on PATH
than the real codex, strips the sandbox arguments, and substitutes the same
`--dangerously-bypass-approvals-and-sandbox` the other two arms already use —
which is also what keeps the three arms identical in permissions.  LoopX's
contracts are untouched: it still believes it is driving codex-cli, because it
is.

Set MR_REAL_CODEX to the real binary; defaults to /usr/local/bin/codex.
MR_LOOPX_CODEX_LOG names the log file; defaults to /tmp/loopx-goal/codex-wrapper.log.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Resolve the real binary rather than assuming /usr/local/bin/codex.  Codex is
# installed into the image through nvm, so it lives under the Node version's
# bin directory and the hardcoded path does not exist — which made the wrapper
# die before it ever reached Codex, and LoopX report the indistinguishable
# `codex_cli_exit_nonzero`.  The wrapper is invoked by absolute path through
# --codex-bin and is not itself on PATH, so a PATH lookup finds the real one.
REAL = (
    os.environ.get("MR_REAL_CODEX")
    or shutil.which("codex")
    or "/usr/local/bin/codex"
)
BYPASS = "--dangerously-bypass-approvals-and-sandbox"
REASONING_EFFORT = os.environ.get("MR_CODEX_REASONING_EFFORT", "").strip()
LOG = Path(
    os.environ.get("MR_LOOPX_CODEX_LOG", "/tmp/loopx-goal/codex-wrapper.log")
)


def rewrite(argv: list[str]) -> list[str]:
    out: list[str] = []
    skip_next = False
    for i, arg in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        # `--sandbox <mode>` — new-session form.
        if arg == "--sandbox":
            skip_next = True
            continue
        if arg.startswith("--sandbox="):
            continue
        # `-c sandbox_mode="..."` — resume form.  The value is a separate argv
        # item after -c, so both have to go, and only when it is that key: -c
        # carries every other config override too.
        if arg == "-c" and i + 1 < len(argv) and argv[i + 1].startswith("sandbox_mode="):
            skip_next = True
            continue
        out.append(arg)

    # Insert the bypass right after the subcommand so it lands before `--`,
    # which codex treats as the end of flags.
    if out and out[0] == "exec":
        out.insert(1, BYPASS)
        if REASONING_EFFORT and not any(
            value.startswith("model_reasoning_effort=") for value in out
        ):
            out[2:2] = ["-c", f"model_reasoning_effort={REASONING_EFFORT}"]
    else:
        out.insert(0, BYPASS)
    return out


def _log(text: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(text.rstrip("\n") + "\n")
    except OSError:
        pass


def main() -> int:
    argv = rewrite(sys.argv[1:])
    # Run the real codex as a child rather than execv'ing it, so its stderr can
    # be recorded.  LoopX reports a failed Turn as `codex_cli_exit_nonzero` and
    # keeps neither the exit code's cause nor any output, and the container is
    # gone by the time anyone looks — so an execv here means the only evidence
    # of why Codex refused is destroyed at the moment it is produced.
    #
    # stdout stays inherited and untouched: LoopX parses Codex's `--json`
    # stream off it, so anything written there would corrupt the Turn.
    _log(f"--- argv in : {sys.argv[1:]}")
    _log(f"--- argv out: {argv}")
    _log(f"--- real    : {REAL} (exists={os.path.exists(REAL)})")
    try:
        completed = subprocess.run(  # noqa: S603
            [REAL, *argv], stderr=subprocess.PIPE, check=False
        )
    except OSError as exc:
        # Without this the wrapper's own failure to start Codex is reported by
        # LoopX as `codex_cli_exit_nonzero`, which reads as "the model refused"
        # rather than "the binary is not there".
        _log(f"--- launch failed: {type(exc).__name__}: {exc}")
        sys.stderr.write(f"codex wrapper could not launch {REAL}: {exc}\n")
        return 127
    stderr = completed.stderr.decode("utf-8", "replace") if completed.stderr else ""
    _log(f"--- exit {completed.returncode}")
    if stderr:
        _log(stderr)
        sys.stderr.write(stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
