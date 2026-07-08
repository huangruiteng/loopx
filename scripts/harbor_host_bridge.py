"""Host command bridge template for Harbor-based Codex agents."""

from __future__ import annotations

BRIDGE_SCRIPT_TEMPLATE = """#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
import time
import uuid

REQUEST_DIR = pathlib.Path("__LOOPX_REQUEST_DIR__")

parser = argparse.ArgumentParser(description="Forward a command into Harbor environment.exec")
parser.add_argument("--cwd", default="")
parser.add_argument("--timeout-sec", type=float, default=600)
parser.add_argument("command", nargs=argparse.REMAINDER)
args = parser.parse_args()

if not args.command:
    print("missing command", file=sys.stderr)
    raise SystemExit(2)

if args.command[0] == "--":
    args.command = args.command[1:]

command = " ".join(args.command) if len(args.command) > 1 else args.command[0]
request_id = uuid.uuid4().hex
request = REQUEST_DIR / f"{request_id}.request.json"
response = REQUEST_DIR / f"{request_id}.response.json"
tmp = REQUEST_DIR / f"{request_id}.tmp"
tmp.write_text(json.dumps({
    "command": command,
    "cwd": args.cwd,
    "timeout_sec": args.timeout_sec,
}, ensure_ascii=False))
tmp.rename(request)
deadline = time.time() + args.timeout_sec + 30
while time.time() < deadline:
    if response.exists():
        payload = json.loads(response.read_text())
        stdout = payload.get("stdout") or ""
        stderr = payload.get("stderr") or ""
        if stdout:
            sys.stdout.write(stdout)
        if stderr:
            sys.stderr.write(stderr)
        raise SystemExit(int(payload.get("return_code") or 0))
    time.sleep(0.5)

print("harbor-env-exec timed out waiting for response", file=sys.stderr)
raise SystemExit(124)
"""

__all__ = ["BRIDGE_SCRIPT_TEMPLATE"]
