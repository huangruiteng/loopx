from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_opencode_goal_bridge_runtime_contract() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the OpenCode bridge runtime contract")
    test_file = Path(__file__).with_name("opencode_goal_bridge_runtime.test.mjs")
    subprocess.run([node, "--test", str(test_file)], check=True)
