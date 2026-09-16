#!/usr/bin/env python3
"""Check the immutable v1 archive without launching a benchmark or model."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess


ARCHIVE = Path(__file__).resolve().with_name("deepswe-gptxhigh-v1")
EXPECTED_TREE = "1bc5d2b3b74761a97d34ba3f3612e977fd610340"


def check_archive(archive: Path) -> dict:
    tree = bytearray()
    python_count = shell_count = embedded_count = 0
    for path in sorted(archive.iterdir(), key=lambda entry: entry.name.encode()):
        # Match the repository's bytecode ignores without hiding extra source
        # files or symlinks inside a directory named __pycache__.
        if path.name == "__pycache__" and path.is_dir() and not path.is_symlink():
            if any(
                entry.is_symlink() or not entry.is_file() or entry.suffix != ".pyc"
                for entry in path.iterdir()
            ):
                raise ValueError("unexpected non-bytecode entry in __pycache__")
            continue
        if path.suffix == ".pyc" and path.is_file() and not path.is_symlink():
            continue
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"unexpected archive entry: {path.name}")
        raw = path.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).digest()
        mode = b"100755" if path.stat().st_mode & 0o111 else b"100644"
        tree.extend(mode + b" " + path.name.encode() + b"\0" + blob)
        if path.suffix == ".py":
            compile(raw, path.name, "exec")
            python_count += 1
            for node in ast.parse(raw).body:
                if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                    continue
                names = {target.id for target in node.targets if isinstance(target, ast.Name)}
                if names & {"_RUNNER", "_BOOTSTRAP"} and isinstance(node.value.value, str):
                    source = node.value.value
                    if "_RUNNER" in names:
                        source = source.format(remote_dir="/tmp/loopx-goal")
                    compile(source, f"{path.name}:embedded", "exec")
                    embedded_count += 1
        elif path.suffix == ".sh":
            subprocess.run(["bash", "-n", str(path)], check=True, capture_output=True, timeout=10)
            shell_count += 1
    actual_tree = hashlib.sha1(b"tree " + str(len(tree)).encode() + b"\0" + tree).hexdigest()
    if actual_tree != EXPECTED_TREE:
        raise ValueError("archive contents or executable modes differ from the original v1 snapshot")
    return {
        "archive_tree": actual_tree,
        "original_snapshot_preserved": True,
        "python_syntax_checks": python_count,
        "embedded_python_checks": embedded_count,
        "shell_syntax_checks": shell_count,
        "benchmark_executed": False,
        "standalone_runnable": False,
        "runtime_validation": "not_performed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    args = parser.parse_args()
    try:
        report = check_archive(args.archive)
    except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps({"ok": True, **report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
