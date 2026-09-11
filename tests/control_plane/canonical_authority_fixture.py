"""Initialize an already canonical provider for its independent consumer tests.

This fixture runs the real FileAuthorityStore in a Node process. It deliberately
does not claim that a shadow qualification can promote canonical authority.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


def initialize_canonical_authority(runtime_root: Path, goal_id: str, projection: dict, *, state_path: Path, provider: str = "file") -> dict:
    repository = Path(__file__).resolve().parents[2]
    module = repository / "loopx/control_plane/coordination/file_authority_store.ts"
    fence_module = repository / "loopx/control_plane/coordination/legacy_writer_fence.ts"
    codec_module = repository / "loopx/control_plane/coordination/authority_store_codec.ts"
    script = (
        f"import {{FileAuthorityStore}} from {json.dumps(module.as_uri())};"
        f"import {{selectLocalSqliteAuthority,openLocalAuthorityStore}} from {json.dumps((module.parent / 'local_authority_provider.ts').as_uri())};"
        f"import {{engageLegacyCoordinationWriterFence}} from {json.dumps(fence_module.as_uri())};"
        f"import {{canonicalAuthoritySha256}} from {json.dumps(codec_module.as_uri())};"
        "import {join} from 'node:path';let input='';for await(const chunk of process.stdin)input+=chunk;"
        "const request=JSON.parse(input);"
        "if(request.provider==='sqlite')await selectLocalSqliteAuthority(request.root,request.goal,true);"
        "const store=await openLocalAuthorityStore(request.root,request.goal);"
        "const result=await store.commitAuthority({expected_provider_revision:null,operation_id:'canonical-fixture',"
        "events:[],next_projection:request.projection,receipts:[]});"
        "const fence=await engageLegacyCoordinationWriterFence({schema_version:'loopx_legacy_coordination_writer_fence_engage_request_v0',"
        "runtime_root:request.root,goal_id:request.goal,state_path:request.state_path,fence:{schema_version:'loopx_legacy_coordination_writer_fence_v0',"
        "state:'engaged',goal_id:request.goal,fence_id:'canonical-fixture',source_version:'canonical-fixture',"
        "source_projection_sha256:canonicalAuthoritySha256(request.projection),expected_shadow_provider_revision:result.provider_revision}});"
        "if(fence.status!=='applied')throw new Error(JSON.stringify(fence));process.stdout.write(JSON.stringify(result));"
    )
    process = subprocess.run(["node", "--no-warnings", "--experimental-strip-types", "--input-type=module", "-e", script],
        input=json.dumps({"root": str(runtime_root), "goal": goal_id, "projection": projection, "state_path": str(state_path), "provider": provider}),
        capture_output=True, text=True, check=False, timeout=45)
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert result["status"] == "applied", result
    return result


def isolate_sqlite_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("NODE_OPTIONS", os.environ.get("NODE_OPTIONS", "") + " --experimental-sqlite")
    # Do not reuse an Effect runtime started by the minimum-Node CI step.
    # Each CLI subprocess resolves its own tempfile root from this environment.
    for variable in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(variable, str(tmp_path))
