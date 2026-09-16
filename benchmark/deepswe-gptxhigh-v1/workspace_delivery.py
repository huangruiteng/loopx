#!/usr/bin/env python3
"""Normalize an agent's work into the canonical DeepSWE checkout.

DeepSWE grades ``git diff <base> HEAD`` from ``/app``.  LoopX may legitimately
place an agent in a linked worktree, so a commit can exist while the collector
still sees an empty patch.  This module makes that delivery boundary explicit:
it finds the one changed worktree, commits any remaining agent changes, copies
the resulting patch into the canonical checkout, and proves that the patch
applies to the task base before the verifier is allowed to run.

LoopX control state is runner-owned and is never included in the submission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONTROL_PATHS = (".loopx", ".codex", ".worktrees")


class DeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class Candidate:
    path: Path
    head: str
    patch: bytes

    @property
    def patch_sha256(self) -> str:
        return hashlib.sha256(self.patch).hexdigest()


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    input_bytes: bytes | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        argv,
        cwd=cwd,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        detail = result.stderr.decode("utf-8", "replace")[-600:]
        raise DeliveryError(f"command failed ({result.returncode}): {argv!r}: {detail}")
    return result


def head_sha(project: Path) -> str:
    return _run(["git", "-C", str(project), "rev-parse", "HEAD"]).stdout.decode().strip()


def _exclude_control_state(project: Path) -> None:
    git_dir = _run(
        ["git", "-C", str(project), "rev-parse", "--git-common-dir"]
    ).stdout.decode().strip()
    common = Path(git_dir)
    if not common.is_absolute():
        common = (project / common).resolve()
    exclude = common / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    additions = [f"/{name}/" for name in CONTROL_PATHS if f"/{name}/" not in existing]
    if additions:
        with exclude.open("a", encoding="utf-8") as handle:
            handle.write("\n# DeepSWE runner control state\n")
            handle.write("\n".join(additions) + "\n")


def worktrees(project: Path) -> list[Path]:
    output = _run(
        ["git", "-C", str(project), "worktree", "list", "--porcelain"]
    ).stdout.decode("utf-8", "replace")
    paths = []
    for line in output.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line.removeprefix("worktree ")).resolve())
    canonical = project.resolve()
    return sorted(set(paths), key=lambda path: (path != canonical, str(path)))


def _commit_pending(path: Path) -> None:
    _exclude_control_state(path)
    # The runner state is ignored through the repository's shared exclude file.
    # Passing ignored paths as explicit negative pathspecs makes Git reject the
    # entire add operation in some task repositories.
    _run(["git", "-C", str(path), "add", "-A", "--", "."])
    staged = _run(
        ["git", "-C", str(path), "diff", "--cached", "--quiet"], check=False
    )
    if staged.returncode not in (0, 1):
        raise DeliveryError(f"could not inspect staged changes in {path}")
    if staged.returncode == 1:
        env = os.environ.copy()
        env.setdefault("GIT_AUTHOR_NAME", "DeepSWE delivery runner")
        env.setdefault("GIT_AUTHOR_EMAIL", "runner@deepswe.invalid")
        env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
        env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])
        result = subprocess.run(
            ["git", "-C", str(path), "commit", "-m", "chore: deliver agent work"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode:
            raise DeliveryError(
                "could not commit pending agent changes: "
                + result.stderr.decode("utf-8", "replace")[-600:]
            )


def _candidate(path: Path, base_sha: str) -> Candidate | None:
    _commit_pending(path)
    head = head_sha(path)
    patch = _run(
        [
            "git",
            "-C",
            str(path),
            "diff",
            "--binary",
            base_sha,
            "HEAD",
            "--",
            ".",
            *(f":(exclude){name}" for name in CONTROL_PATHS),
        ]
    ).stdout
    return Candidate(path=path, head=head, patch=patch) if patch.strip() else None


def _prove_applies(project: Path, base_sha: str, patch: bytes) -> None:
    with tempfile.TemporaryDirectory(prefix="deepswe-delivery-check-") as tmp:
        checkout = Path(tmp) / "base"
        _run(["git", "clone", "--shared", "--no-checkout", str(project), str(checkout)])
        _run(["git", "-C", str(checkout), "checkout", "--detach", base_sha])
        _run(["git", "-C", str(checkout), "apply", "--check", "--binary", "-"], input_bytes=patch)


def _install_patch(project: Path, base_sha: str, patch: bytes) -> str:
    _run(["git", "-C", str(project), "reset", "--hard", base_sha])
    _run(["git", "-C", str(project), "apply", "--index", "--binary", "-"], input_bytes=patch)
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "DeepSWE delivery runner")
    env.setdefault("GIT_AUTHOR_EMAIL", "runner@deepswe.invalid")
    env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
    env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])
    result = subprocess.run(
        ["git", "-C", str(project), "commit", "-m", "chore: recover agent worktree delivery"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise DeliveryError(
            "could not install recovered patch: "
            + result.stderr.decode("utf-8", "replace")[-600:]
        )
    return head_sha(project)


def normalize_delivery(project: Path, base_sha: str) -> dict[str, Any]:
    project = project.resolve()
    receipt: dict[str, Any] = {
        "schema_version": "deepswe_delivery_receipt_v1",
        "project": str(project),
        "base_sha": base_sha,
        "status": "error",
        "treatment_valid": False,
    }
    try:
        candidates = [
            item
            for path in worktrees(project)
            if (item := _candidate(path, base_sha)) is not None
        ]
        by_patch: dict[str, list[Candidate]] = {}
        for item in candidates:
            by_patch.setdefault(item.patch_sha256, []).append(item)
        receipt["changed_worktree_count"] = len(candidates)
        receipt["distinct_patch_count"] = len(by_patch)
        receipt["changed_worktrees"] = [str(item.path) for item in candidates]
        if not candidates:
            receipt["status"] = "empty"
            receipt["reason"] = "no_agent_delta_from_task_base"
            return receipt
        if len(by_patch) != 1:
            receipt["status"] = "ambiguous"
            receipt["reason"] = "multiple_distinct_agent_patches"
            return receipt

        selected = next(iter(by_patch.values()))[0]
        _prove_applies(project, base_sha, selected.patch)
        canonical = project.resolve()
        recovered = selected.path.resolve() != canonical
        if recovered:
            final_head = _install_patch(project, base_sha, selected.patch)
        else:
            final_head = selected.head
        final_patch = _run(
            [
                "git",
                "-C",
                str(project),
                "diff",
                "--binary",
                base_sha,
                "HEAD",
                "--",
                ".",
                *(f":(exclude){name}" for name in CONTROL_PATHS),
            ]
        ).stdout
        if not final_patch.strip():
            raise DeliveryError("canonical patch became empty after normalization")
        if hashlib.sha256(final_patch).hexdigest() != selected.patch_sha256:
            raise DeliveryError("canonical patch digest differs after normalization")
        _prove_applies(project, base_sha, final_patch)

        receipt.update(
            {
                "status": "valid",
                "reason": "canonical_patch_verified",
                "treatment_valid": True,
                "source_worktree": str(selected.path),
                "recovered_from_linked_worktree": recovered,
                "final_head": final_head,
                "patch_bytes": len(final_patch),
                "patch_sha256": selected.patch_sha256,
                "patch_applies": True,
            }
        )
    except Exception as exc:
        receipt["status"] = "error"
        receipt["reason"] = f"{type(exc).__name__}: {exc}"
    return receipt


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--require-valid", action="store_true")
    args = parser.parse_args()

    receipt = normalize_delivery(args.project, args.base_sha)
    if args.receipt:
        write_receipt(args.receipt, receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["treatment_valid"] or not args.require_valid else 12


if __name__ == "__main__":
    raise SystemExit(main())
