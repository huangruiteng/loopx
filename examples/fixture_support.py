from __future__ import annotations

import atexit
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable


OPERATOR_LOCAL_RESULT_FIELDS = frozenset(
    {
        "index_path",
        "json_path",
        "markdown_path",
        "registry",
        "runtime_root",
    }
)


def _without_operator_local_result_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_operator_local_result_fields(item)
            for key, item in value.items()
            if key not in OPERATOR_LOCAL_RESULT_FIELDS
        }
    if isinstance(value, list):
        return [_without_operator_local_result_fields(item) for item in value]
    return value


def assert_public_result_projection(
    value: Any,
    *,
    forbidden_text: Iterable[str],
    max_chars: int,
) -> None:
    full_text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    projection = _without_operator_local_result_fields(value)
    projection_text = (
        json.dumps(projection, sort_keys=True)
        if not isinstance(projection, str)
        else projection
    )
    leaked = [marker for marker in forbidden_text if marker in projection_text]
    assert not leaked, leaked
    assert len(full_text) < max_chars, len(full_text)


def create_minimal_goal_registry(
    *,
    goal_id: str,
    objective: str,
) -> tuple[Path, Path]:
    root = Path(tempfile.mkdtemp(prefix="loopx-cli-registry-fixture-"))
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    project = root / "project"
    runtime_root = root / "runtime"
    state_file = project / ".codex" / "goals" / goal_id / "ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        f"# {goal_id}\n\n## Next Action\n\n- Run the fixture dry-run.\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "registry_role": "project-local",
                "common_runtime_root": str(runtime_root),
                "goals": [
                    {
                        "id": goal_id,
                        "objective": objective,
                        "domain": "smoke",
                        "repo": str(project),
                        "state_file": str(state_file.relative_to(project)),
                        "status": "connected-read-only",
                        "adapter": {
                            "kind": "read_only_project_map_v0",
                            "status": "connected-read-only",
                        },
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, runtime_root


def install_stub_executables_on_path(*names: str) -> tuple[Path, ...]:
    root = Path(tempfile.mkdtemp(prefix="loopx-executable-fixture-"))
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    executables = []
    for name in names:
        executable = root / name
        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        executable.chmod(0o755)
        executables.append(executable)
    os.environ["PATH"] = str(root) + os.pathsep + os.environ.get("PATH", "")
    return tuple(executables)


def install_minimal_goal_registry_environment(
    *,
    goal_id: str,
    objective: str,
) -> tuple[Path, Path]:
    registry_path, runtime_root = create_minimal_goal_registry(
        goal_id=goal_id,
        objective=objective,
    )
    os.environ["LOOPX_REGISTRY"] = str(registry_path)
    os.environ["LOOPX_RUNTIME_ROOT"] = str(runtime_root)
    return registry_path, runtime_root
