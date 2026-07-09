#!/usr/bin/env python3
"""Smoke-test the SkillsBench reverse-tunnel supervisor wrapper."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_core import materialize_public_benchmark_artifacts
from loopx.benchmark_core.remote_closeout import closeout_remote_benchmark_batch

SCRIPT = REPO_ROOT / "scripts" / "skillsbench_reverse_tunnel_supervisor.py"


def _fake_ssh(path: Path, log_path: Path) -> None:
    path.write_text(
        f"""#!/usr/bin/env python3
import os
import base64
import json
import signal
import sys
import time

log_path = {str(log_path)!r}
args = sys.argv[1:]
with open(log_path, "a", encoding="utf-8") as handle:
    handle.write(repr(args) + "\\n")

if "-R" in args:
    running = True
    def stop(_sig, _frame):
        global running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        time.sleep(0.05)
    sys.exit(0)

remote_command = args[-1] if args else ""
if "LOOPX_REVERSE_TUNNEL_PROBE" in remote_command:
    print("HTTP/1.1 200 Connection Established")
    sys.exit(0)

if "LOOPX_REMOTE_FAILURE_CLEANUP" in remote_command:
    print('{{"alive_after_count": 0, "docker_matched_count": 1, "docker_removed_count": 1, "docker_status": "ok", "kill_sent_count": 0, "matched_count": 2, "term_sent_count": 2}}')
    sys.exit(0)

if "benchmark_remote_public_artifact_collection_v0" in remote_command:
    compact = json.dumps({{
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "skillsbench@1.1",
        "task_id": "case-a",
        "run_id": "case-a-sync-smoke",
        "route": "codex-cli-goal-baseline",
        "status": "completed",
        "official_score": 0.0,
    }}, sort_keys=True).encode("utf-8")
    print(json.dumps({{
        "schema_version": "benchmark_remote_public_artifact_collection_v0",
        "matched_count": 1,
        "blocked_count": 0,
        "artifacts": [{{
            "relative_path": "job/case/benchmark_run.compact.json",
            "content_base64": base64.b64encode(compact).decode("ascii"),
        }}],
    }}, sort_keys=True))
    sys.exit(0)

if "cat >" in remote_command:
    sys.stdin.read()

if "fail-skillsbench" in remote_command:
    print("private failure detail")
    sys.exit(42)

print('{{"ok": true, "source": "fake_remote_command"}}')
sys.exit(0)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_supervisor_holds_tunnel_and_redacts_private_command() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-tunnel-supervisor-") as tmp:
        root = Path(tmp)
        fake_ssh = root / "ssh"
        ssh_log = root / "ssh.log"
        public_output = root / "public.json"
        private_log = root / "private.log"
        _fake_ssh(fake_ssh, ssh_log)

        opaque_destination = "opaque-benchmark-host.example"
        opaque_command = "cd /opaque/workdir && run-skillsbench --task bike-rebalance"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--ssh-bin",
                str(fake_ssh),
                "--ssh-destination",
                opaque_destination,
                "--remote-forward",
                "127.0.0.1:18180:127.0.0.1:18180",
                "--remote-command",
                opaque_command,
                "--public-output-path",
                str(public_output),
                "--private-log-path",
                str(private_log),
                "--tunnel-ready-timeout-sec",
                "5",
                "--probe-interval-sec",
                "0.1",
                "--run-timeout-sec",
                "5",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=10,
        )
        assert proc.returncode == 0, proc.stderr or proc.stdout
        payload = json.loads(proc.stdout)
        persisted = json.loads(public_output.read_text(encoding="utf-8"))
        assert payload == persisted
        assert payload["ok"] is True, payload
        assert payload["tunnel_started"] is True, payload
        assert payload["tunnel_ready"] is True, payload
        assert payload["probe_status"] == "http_connect_ready", payload
        assert payload["remote_command_exit_code"] == 0, payload
        assert payload["raw_ssh_destination_recorded"] is False, payload
        assert payload["raw_remote_command_recorded"] is False, payload
        assert payload["raw_remote_output_recorded"] is False, payload
        assert payload["private_log_written"] is True, payload
        assert payload["remote_forward"]["raw_forward_recorded"] is False, payload
        public_text = json.dumps(payload, sort_keys=True)
        assert opaque_destination not in public_text
        assert opaque_command not in public_text
        assert opaque_command in ssh_log.read_text(encoding="utf-8")
        assert private_log.exists()


def test_supervisor_syncs_only_compact_public_artifacts() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-tunnel-sync-") as tmp:
        root = Path(tmp)
        fake_ssh = root / "ssh"
        ssh_log = root / "ssh.log"
        public_output = root / "public.json"
        private_log = root / "private.log"
        synced_dir = root / "synced"
        ledger_path = root / "live-ledger.json"
        aggregate_path = root / "standard-aggregate.json"
        canonical_ids = root / "canonical-case-ids.txt"
        canonical_ids.write_text("case-a\n", encoding="utf-8")
        _fake_ssh(fake_ssh, ssh_log)

        opaque_destination = "opaque-benchmark-host.example"
        opaque_remote_root = "/opaque/private/jobs"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--ssh-bin",
                str(fake_ssh),
                "--ssh-destination",
                opaque_destination,
                "--remote-forward",
                "127.0.0.1:18180:127.0.0.1:18180",
                "--remote-command",
                "run-skillsbench --case case-a",
                "--remote-public-artifact-root",
                opaque_remote_root,
                "--remote-public-artifact-glob",
                "job/*/benchmark_run.compact.json",
                "--local-public-artifact-dir",
                str(synced_dir),
                "--local-run-ledger-path",
                str(ledger_path),
                "--local-run-group-id",
                "skillsbench-codex-cli-goal-xhigh-sync-smoke",
                "--local-current-aggregate-path",
                str(aggregate_path),
                "--local-canonical-case-ids-file",
                str(canonical_ids),
                "--local-target-lane-id",
                "codex-cli-goal-xhigh",
                "--local-target-run-group-contains",
                "skillsbench-codex-cli-goal-xhigh-",
                "--public-output-path",
                str(public_output),
                "--private-log-path",
                str(private_log),
                "--tunnel-ready-timeout-sec",
                "5",
                "--probe-interval-sec",
                "0.1",
                "--run-timeout-sec",
                "5",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=10,
        )
        assert proc.returncode == 0, proc.stderr or proc.stdout
        payload = json.loads(proc.stdout)
        sync = payload["public_artifact_sync"]
        assert sync["ok"] is True, sync
        assert sync["matched_count"] == 1, sync
        assert sync["written_count"] == 1, sync
        compact_path = synced_dir / "job" / "case" / "benchmark_run.compact.json"
        assert compact_path.exists(), sync
        assert ledger_path.exists(), sync
        assert aggregate_path.exists(), sync
        assert sync["local_ledger_update"]["upserted_count"] == 1, sync
        assert sync["local_aggregate_update"]["canonical_total"] == 1, sync
        public_text = public_output.read_text(encoding="utf-8")
        assert opaque_destination not in public_text
        assert opaque_remote_root not in public_text
        assert str(synced_dir) not in public_text
        assert sync["raw_paths_recorded"] is False
        assert sync["raw_logs_read"] is False
        assert sync["raw_trajectory_read"] is False


def test_public_artifact_materializer_rejects_private_children() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-artifact-boundary-") as tmp:
        content = base64.b64encode(b"{}\n").decode("ascii")
        result = materialize_public_benchmark_artifacts(
            [
                {
                    "relative_path": "private/leak.public.json",
                    "content_base64": content,
                },
                {
                    "relative_path": "case/benchmark_run.compact.json",
                    "content_base64": content,
                },
            ],
            output_dir=tmp,
            adapter_kind="skillsbench",
        )
        assert result["written_count"] == 1, result
        assert result["blocked_reasons"] == {"raw_private_surface": 1}, result
        assert not (Path(tmp) / "private" / "leak.public.json").exists()


def test_closeout_requires_compact_when_ledger_is_requested() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-closeout-compact-") as tmp:
        content = base64.b64encode(b"{}\n").decode("ascii")
        collection = json.dumps(
            {
                "artifacts": [
                    {
                        "relative_path": "job/runner_prerequisites.public.json",
                        "content_base64": content,
                    }
                ],
                "matched_count": 1,
                "blocked_count": 0,
            }
        )
        result = closeout_remote_benchmark_batch(
            run_remote_command=lambda _command, _timeout: subprocess.CompletedProcess(
                args=[], returncode=0, stdout=collection, stderr=""
            ),
            remote_root="/opaque/private/jobs",
            artifact_globs=["job/*.public.json"],
            local_public_artifact_dir=tmp,
            adapter_kind="skillsbench",
            max_bytes=1024,
            sync_timeout_sec=1,
            ledger_path=str(Path(tmp) / "ledger.json"),
        )
        assert result["ok"] is False, result
        assert (
            result["first_blocker"]
            == "benchmark_compact_missing_after_remote_closeout"
        ), result


def test_supervisor_cleans_remote_failure_without_public_pattern() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-tunnel-cleanup-") as tmp:
        root = Path(tmp)
        fake_ssh = root / "ssh"
        ssh_log = root / "ssh.log"
        public_output = root / "public.json"
        private_log = root / "private.log"
        _fake_ssh(fake_ssh, ssh_log)

        opaque_destination = "opaque-benchmark-host.example"
        opaque_cleanup_pattern = "redacted-cleanup-token-example"
        opaque_command = (
            "cd /opaque/workdir && fail-skillsbench --run-group "
            + opaque_cleanup_pattern
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--ssh-bin",
                str(fake_ssh),
                "--ssh-destination",
                opaque_destination,
                "--remote-forward",
                "127.0.0.1:18180:127.0.0.1:18180",
                "--remote-command",
                opaque_command,
                "--remote-failure-cleanup-pattern",
                opaque_cleanup_pattern,
                "--remote-failure-cleanup-include-docker",
                "--remote-failure-cleanup-timeout-sec",
                "5",
                "--public-output-path",
                str(public_output),
                "--private-log-path",
                str(private_log),
                "--tunnel-ready-timeout-sec",
                "5",
                "--probe-interval-sec",
                "0.1",
                "--run-timeout-sec",
                "5",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=10,
        )
        assert proc.returncode == 42, proc.stderr or proc.stdout
        payload = json.loads(proc.stdout)
        assert payload["ok"] is False, payload
        assert payload["first_blocker"] == "remote_command_exit_nonzero", payload
        assert payload["remote_command_exit_code"] == 42, payload
        cleanup = payload["remote_failure_cleanup"]
        assert cleanup["requested"] is True, cleanup
        assert cleanup["attempted"] is True, cleanup
        assert cleanup["trigger"] == "remote_command_exit_nonzero", cleanup
        assert cleanup["exit_code"] == 0, cleanup
        assert cleanup["matched_count"] == 2, cleanup
        assert cleanup["term_sent_count"] == 2, cleanup
        assert cleanup["alive_after_count"] == 0, cleanup
        assert cleanup["docker_status"] == "ok", cleanup
        assert cleanup["docker_matched_count"] == 1, cleanup
        assert cleanup["docker_removed_count"] == 1, cleanup
        assert cleanup["raw_pattern_recorded"] is False, cleanup
        assert cleanup["raw_output_recorded"] is False, cleanup
        public_text = json.dumps(payload, sort_keys=True)
        assert opaque_destination not in public_text
        assert opaque_command not in public_text
        assert opaque_cleanup_pattern not in public_text
        assert "LOOPX_REMOTE_FAILURE_CLEANUP" in ssh_log.read_text(encoding="utf-8")
        assert private_log.exists()


def test_supervisor_holds_json_bridge_and_materializes_remote_client() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-tunnel-json-") as tmp:
        root = Path(tmp)
        fake_ssh = root / "ssh"
        ssh_log = root / "ssh.log"
        public_output = root / "public.json"
        private_log = root / "private.log"
        local_socket = Path("/tmp") / f"{root.name}.sock"
        _fake_ssh(fake_ssh, ssh_log)

        opaque_destination = "opaque-benchmark-host.example"
        opaque_bridge_command = "opaque-private-json-bridge-command"
        opaque_remote_socket = "/tmp/opaque-private-json-bridge.sock"
        opaque_remote_client = "/tmp/opaque-private-json-client"
        opaque_command = (
            "run-skillsbench --bridge {json_bridge_client} "
            "--case bike-rebalance"
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--ssh-bin",
                str(fake_ssh),
                "--ssh-destination",
                opaque_destination,
                "--remote-forward",
                "127.0.0.1:18180:127.0.0.1:18180",
                "--remote-command",
                opaque_command,
                "--public-output-path",
                str(public_output),
                "--private-log-path",
                str(private_log),
                "--tunnel-ready-timeout-sec",
                "5",
                "--probe-interval-sec",
                "0.1",
                "--run-timeout-sec",
                "5",
                "--json-bridge",
                "--json-bridge-command",
                opaque_bridge_command,
                "--json-local-socket",
                str(local_socket),
                "--json-remote-socket",
                opaque_remote_socket,
                "--json-remote-client-path",
                opaque_remote_client,
                "--json-socket-ready-timeout-sec",
                "2",
                "--remote-setup-timeout-sec",
                "2",
                "--json-server-timeout-sec",
                "5",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=10,
        )
        assert proc.returncode == 0, proc.stderr or proc.stdout
        payload = json.loads(proc.stdout)
        assert payload["ok"] is True, payload
        assert payload["tunnel_ready"] is True, payload
        bridge = payload["json_bridge"]
        assert bridge["enabled"] is True, bridge
        assert bridge["server_started"] is True, bridge
        assert bridge["local_socket_ready"] is True, bridge
        assert bridge["remote_socket_ready"] is True, bridge
        assert bridge["remote_client_materialized"] is True, bridge
        assert bridge["sandbox_env_probe_deferred"] is True, bridge
        cleanup = bridge["remote_socket_cleanup"]
        assert cleanup["requested"] is True, cleanup
        assert cleanup["attempted"] is True, cleanup
        assert cleanup["ok"] is True, cleanup
        assert cleanup["exit_code"] == 0, cleanup
        assert bridge["raw_bridge_command_recorded"] is False, bridge
        assert bridge["raw_socket_paths_recorded"] is False, bridge
        assert bridge["raw_client_path_recorded"] is False, bridge

        public_text = json.dumps(payload, sort_keys=True)
        assert opaque_destination not in public_text
        assert opaque_bridge_command not in public_text
        assert str(local_socket) not in public_text
        assert opaque_remote_socket not in public_text
        assert opaque_remote_client not in public_text
        ssh_log_text = ssh_log.read_text(encoding="utf-8")
        assert "rm -f --" in ssh_log_text
        assert opaque_remote_socket in ssh_log_text
        assert opaque_remote_client in ssh_log_text
        assert private_log.exists()


if __name__ == "__main__":
    test_supervisor_holds_tunnel_and_redacts_private_command()
    test_supervisor_syncs_only_compact_public_artifacts()
    test_public_artifact_materializer_rejects_private_children()
    test_closeout_requires_compact_when_ledger_is_requested()
    test_supervisor_cleans_remote_failure_without_public_pattern()
    test_supervisor_holds_json_bridge_and_materializes_remote_client()
    print("skillsbench-reverse-tunnel-supervisor smoke ok")
