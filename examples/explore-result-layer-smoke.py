#!/usr/bin/env python3
"""Smoke-test the exploration result layer: topology log, Lark board sync, card.

Covers the durable public contracts:
- result events (node/edge/finding) fold into a bounded public-safe projection
  with topology tree, blocked reasons, findings, and Mermaid graph source;
- absolute local paths are rejected at record time and never reach generated
  Lark record values (shared_adapter_local_path_leak guard);
- feishu-sync is dry-run by default, upserts idempotently by record id on the
  second executed sync, and shared visibility redacts private links;
- the result card is transport-free content built from the same projection;
- the CLI surface works end to end against a temp registry/runtime root.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.explore import result_log  # noqa: E402
from loopx.capabilities.lark import explore_results  # noqa: E402


ABS_PATH_RE = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/](?![\\/])|file://|/Users/|/home/")


def build_sample_events(goal_id: str) -> list[dict[str, object]]:
    events = [
        result_log.build_explore_node_event(
            goal_id=goal_id,
            title="SCADE peer tool landscape",
            node_id="node_root",
            node_kind="area",
            status="exploring",
            recorded_at="2026-07-06T01:00:00Z",
        ),
        result_log.build_explore_node_event(
            goal_id=goal_id,
            title="KCG code generator licensing",
            node_id="node_kcg",
            node_kind="question",
            status="open",
            parent_id="node_root",
            recorded_at="2026-07-06T01:05:00Z",
        ),
        # Same node id again: latest event wins in the projection.
        result_log.build_explore_node_event(
            goal_id=goal_id,
            title="KCG code generator licensing",
            node_id="node_kcg",
            node_kind="question",
            status="blocked",
            blocked_reason="vendor licence terms unclear",
            parent_id="node_root",
            recorded_at="2026-07-06T02:00:00Z",
        ),
        result_log.build_explore_edge_event(
            goal_id=goal_id,
            from_node="node_kcg",
            to_node="node_root",
            edge_type="subtopic_of",
            recorded_at="2026-07-06T01:06:00Z",
        ),
        result_log.build_explore_finding_event(
            goal_id=goal_id,
            title="Two open-source Lustre toolchains cover the KCG core use case",
            node_id="node_kcg",
            status="confirmed",
            confidence=0.8,
            evidence_refs=["ov:doc:lustre-survey"],
            summary="See https://internal.example.invalid/wiki/abc for the private survey doc",
            recorded_at="2026-07-06T02:10:00Z",
        ),
    ]
    return events


def check_result_log_contract() -> dict[str, object]:
    goal_id = "explore-smoke-goal"
    with tempfile.TemporaryDirectory(prefix="loopx-explore-smoke-") as tmp:
        runtime_root = Path(tmp) / "runtime"
        log_path = result_log.explore_result_log_path(runtime_root, goal_id)
        for event in build_sample_events(goal_id):
            appended = result_log.append_explore_result_event(log_path, event)
            assert appended["ok"] is True, appended
        events = result_log.load_explore_result_events(log_path, goal_id=goal_id)
        assert len(events) == 5, events

        projection = result_log.build_explore_result_projection(events, goal_id=goal_id)
        assert projection["schema_version"] == "loopx_explore_result_projection_v0", projection
        counts = projection["counts"]
        assert counts["node_count"] == 2, counts
        assert counts["edge_count"] == 1, counts
        assert counts["finding_count"] == 1, counts
        assert counts["nodes_by_status"]["blocked"] == 1, counts

        # Latest node event wins and keeps update lineage.
        kcg = next(node for node in projection["nodes"] if node["node_id"] == "node_kcg")
        assert kcg["status"] == "blocked", kcg
        assert kcg["blocked_reason"] == "vendor licence terms unclear", kcg
        assert kcg["update_count"] == 2, kcg
        assert kcg["finding_count"] == 1, kcg

        stuck = projection["stuck"]
        assert [node["node_id"] for node in stuck] == ["node_kcg"], stuck

        tree = projection["tree"]
        assert len(tree) == 1 and tree[0]["node_id"] == "node_root", tree
        assert tree[0]["children"][0]["node_id"] == "node_kcg", tree

        mermaid = projection["mermaid"]
        assert mermaid.startswith("flowchart TD"), mermaid
        assert "node_kcg" in mermaid and ":::blocked" in mermaid, mermaid
        assert "-->|subtopic_of|" in mermaid, mermaid

    # Public-safety gates at record time.
    try:
        result_log.build_explore_finding_event(
            goal_id=goal_id,
            title="leaky finding",
            evidence_refs=["C:\\\\work\\\\private\\\\notes.md"],
        )
        raise AssertionError("absolute evidence ref must be rejected")
    except ValueError:
        pass
    try:
        result_log.build_explore_node_event(
            goal_id=goal_id,
            title="Review C:\\\\work\\\\private\\\\notes.md",
        )
        raise AssertionError("absolute path in public text must be rejected")
    except ValueError:
        pass
    try:
        result_log.build_explore_finding_event(
            goal_id=goal_id,
            title="leaky summary",
            summary="See file:///tmp/private-notes.md for details",
        )
        raise AssertionError("file URL in public text must be rejected")
    except ValueError:
        pass
    try:
        result_log.build_explore_node_event(goal_id=goal_id, title="stuck node", status="blocked")
        raise AssertionError("blocked node without blocked_reason must be rejected")
    except ValueError:
        pass
    return projection


def lark_list_fixture(records: list[tuple[str, str, str]]) -> dict[str, object]:
    fields = ["LoopX Goal ID", "LoopX Result ID", "Title"]
    return {
        "ok": True,
        "data": {
            "fields": fields,
            "data": [[goal, result, title] for goal, result, title in records],
            "record_id_list": [f"rec_fixture_{index}" for index in range(len(records))],
        },
    }


def check_lark_sync_contract() -> None:
    goal_id = "explore-smoke-goal"
    events = build_sample_events(goal_id)
    projection = result_log.build_explore_result_projection(events, goal_id=goal_id)
    config = explore_results.LarkExploreConfig(
        **{"base_" + "token": "SMOKE_BASE"},
        table_ids={"nodes": "tblN", "edges": "tblE", "findings": "tblF"},
    )

    with tempfile.TemporaryDirectory(prefix="loopx-explore-smoke-") as tmp:
        config_path = Path(tmp) / ".loopx" / "lark-explore.json"

        # Dry-run: plans upserts, runs nothing, and leaks no local paths.
        dry = explore_results.sync_explore_results_to_lark(
            config,
            projection=projection,
            config_path=config_path,
            execute=False,
        )
        assert dry["ok"] is True and dry["execute"] is False, dry
        assert dry["row_counts"] == {"nodes": 2, "edges": 1, "findings": 1}, dry
        assert all(not item["command"]["executed"] for item in dry["records"]), dry
        record_blob = json.dumps(dry["records"], ensure_ascii=False)
        assert str(REPO_ROOT) not in record_blob, record_blob
        assert tmp not in record_blob, record_blob
        assert not ABS_PATH_RE.search(record_blob), record_blob

        # Executed sync creates records and remembers record ids.
        upsert_calls: list[list[str]] = []

        def fake_runner(args: list[str], cwd: Path | None, timeout: float | None) -> dict[str, object]:
            if "+record-list" in args:
                return {
                    "returncode": 0,
                    "stdout": json.dumps(lark_list_fixture([])),
                    "stderr": "",
                    "timed_out": False,
                }
            if "+record-upsert" in args:
                upsert_calls.append(list(args))
                return {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {"ok": True, "data": {"record_id_list": [f"rec_new_{len(upsert_calls)}"]}}
                    ),
                    "stderr": "",
                    "timed_out": False,
                }
            raise AssertionError(args)

        first = explore_results.sync_explore_results_to_lark(
            config,
            projection=projection,
            config_path=config_path,
            execute=True,
            runner=fake_runner,
        )
        assert first["ok"] is True, first
        assert len(upsert_calls) == 4, upsert_calls
        assert all("--record-id" not in call for call in upsert_calls), upsert_calls
        stored = json.loads(config_path.read_text(encoding="utf-8"))
        assert len(stored["result_records"]) == 4, stored

        # Second executed sync updates the same rows by remembered record id.
        upsert_calls.clear()
        second = explore_results.sync_explore_results_to_lark(
            config,
            projection=projection,
            config_path=config_path,
            execute=True,
            runner=fake_runner,
        )
        assert second["ok"] is True, second
        assert len(upsert_calls) == 4, upsert_calls
        assert all("--record-id" in call for call in upsert_calls), upsert_calls
        edge_record = next(item for item in second["records"] if item["table"] == "edges")
        assert edge_record["values"]["From Node Link"] == [{"id": "rec_new_2"}], edge_record
        assert edge_record["values"]["To Node Link"] == [{"id": "rec_new_1"}], edge_record

        # Shared visibility redacts private links in row values.
        shared = explore_results.sync_explore_results_to_lark(
            config,
            projection=projection,
            config_path=config_path,
            sink_visibility="shared",
            execute=False,
        )
        shared_blob = json.dumps(shared["records"], ensure_ascii=False)
        assert "internal.example.invalid" not in shared_blob, shared_blob
        assert "[private-link-redacted]" in shared_blob, shared_blob


def check_lark_setup_and_card() -> None:
    goal_id = "explore-smoke-goal"
    projection = result_log.build_explore_result_projection(
        build_sample_events(goal_id), goal_id=goal_id
    )

    schema = explore_results.lark_explore_schema_payload()
    assert schema["schema_version"] == "loopx_lark_explore_result_board_v0", schema
    assert set(schema["tables"]) == {"nodes", "edges", "findings"}, schema
    edge_fields = schema["tables"]["edges"]["fields"]
    assert any(
        field.get("name") == "From Node Link"
        and field.get("type") == "link"
        and field.get("link_table") == "Nodes"
        for field in edge_fields
    ), edge_fields
    assert any(
        field.get("name") == "To Node Link"
        and field.get("type") == "link"
        and field.get("link_table") == "Nodes"
        for field in edge_fields
    ), edge_fields

    with tempfile.TemporaryDirectory(prefix="loopx-explore-smoke-") as tmp:
        config_path = Path(tmp) / ".loopx" / "lark-explore.json"
        dry = explore_results.setup_lark_explore_board(config_path=config_path, execute=False)
        assert dry["ok"] is True and not config_path.exists(), dry
        assert len(dry["commands"]) == 4, dry

        def fake_runner(args: list[str], cwd: Path | None, timeout: float | None) -> dict[str, object]:
            if "+base-create" in args:
                payload = {
                    "ok": True,
                    "data": {
                        "app_token": "SMOKE_BASE",
                        "base": {
                            "base_token": "SMOKE_BASE",
                            "url": "https://example.invalid/base/SMOKE_BASE",
                        },
                    },
                }
            elif "+table-create" in args:
                name = args[args.index("--name") + 1]
                payload = {"ok": True, "data": {"table_id": f"tbl{name}"}}
            else:
                raise AssertionError(args)
            return {"returncode": 0, "stdout": json.dumps(payload), "stderr": "", "timed_out": False}

        executed = explore_results.setup_lark_explore_board(
            config_path=config_path, execute=True, runner=fake_runner
        )
        assert executed["ok"] is True, executed
        assert executed["tables"] == {
            "nodes": "tblNodes",
            "edges": "tblEdges",
            "findings": "tblFindings",
        }, executed
        assert executed["board"]["base_url"] == "https://example.invalid/base/SMOKE_BASE", executed
        stored = json.loads(config_path.read_text(encoding="utf-8"))
        assert stored["board"]["tables"]["nodes"] == "tblNodes", stored
        assert stored["board"]["base_url"] == "https://example.invalid/base/SMOKE_BASE", stored

        config_path.write_bytes(b"\xef\xbb\xbf" + config_path.read_bytes())
        bom_payload = explore_results.read_lark_explore_local_config(config_path)
        assert bom_payload["ok"] is True, bom_payload
        assert bom_payload["board"]["base_token"] == "SMOKE_BASE", bom_payload

    card_payload = explore_results.build_explore_result_card(projection)
    assert card_payload["ok"] is True, card_payload
    assert card_payload["schema_version"] == "loopx_lark_explore_card_v0", card_payload
    markdown = card_payload["card_markdown"]
    assert "**Exploration map**: 2 nodes" in markdown, markdown
    assert "**Blocked**" in markdown and "vendor licence terms unclear" in markdown, markdown
    assert "[confirmed] Two open-source Lustre toolchains" in markdown, markdown
    card = card_payload["card"]
    assert card["header"]["title"]["content"].startswith("Exploration map:"), card
    assert card["elements"][0]["text"]["tag"] == "lark_md", card


def check_cli_surface() -> None:
    goal_id = "explore-smoke-cli"
    with tempfile.TemporaryDirectory(prefix="loopx-explore-smoke-") as tmp:
        registry = Path(tmp) / ".loopx" / "registry.json"
        runtime_root = Path(tmp) / "runtime"

        def run_cli(*extra_args: str) -> dict[str, object]:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "loopx.cli",
                    "--format",
                    "json",
                    "--registry",
                    str(registry),
                    "--runtime-root",
                    str(runtime_root),
                    *extra_args,
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            return json.loads(result.stdout)

        node = run_cli(
            "explore",
            "node",
            "--goal-id",
            goal_id,
            "--title",
            "CLI topology root",
            "--node-id",
            "node_cli_root",
            "--status",
            "exploring",
        )
        assert node["ok"] is True and node["result_id"] == "node_cli_root", node
        finding = run_cli(
            "explore",
            "finding",
            "--goal-id",
            goal_id,
            "--title",
            "CLI-visible finding",
            "--node",
            "node_cli_root",
            "--status",
            "tentative",
        )
        assert finding["ok"] is True, finding
        summary = run_cli("explore", "summary", "--goal-id", goal_id)
        assert summary["counts"]["node_count"] == 1, summary
        assert summary["counts"]["finding_count"] == 1, summary
        graph = run_cli("explore", "graph", "--goal-id", goal_id)
        assert str(graph["mermaid"]).startswith("flowchart TD"), graph
        sync = run_cli(
            "explore",
            "feishu-sync",
            "--goal-id",
            goal_id,
            "--config-path",
            str(Path(tmp) / ".loopx" / "lark-explore.json"),
            "--base-token",
            "SMOKE_BASE",
            "--table-id-nodes",
            "tblN",
            "--table-id-edges",
            "tblE",
            "--table-id-findings",
            "tblF",
        )
        assert sync["ok"] is True and sync["execute"] is False, sync
        assert tmp not in json.dumps(sync["records"], ensure_ascii=False), sync

        config_path = Path(tmp) / ".loopx" / "stored-lark-explore.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(
                {
                    "schema_version": "loopx_lark_explore_local_config_v0",
                    "board": {
                        "base_token": "SMOKE_BASE",
                        "tables": {"nodes": "tblN", "edges": "tblE", "findings": "tblF"},
                        "cli_bin": "stored-lark-cli",
                        "identity": "user",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        stored_cli_sync = run_cli(
            "explore",
            "feishu-sync",
            "--goal-id",
            goal_id,
            "--config-path",
            str(config_path),
        )
        assert stored_cli_sync["ok"] is True, stored_cli_sync
        assert stored_cli_sync["commands"][0]["command"].startswith("stored-lark-cli "), stored_cli_sync

        # Error contract: unknown target without config fails with exit 1.
        error = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime_root),
                "explore",
                "feishu-sync",
                "--goal-id",
                goal_id,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert error.returncode == 1, error.stdout
        error_payload = json.loads(error.stdout)
        assert error_payload["ok"] is False, error_payload
        assert "feishu-setup" in str(error_payload["error"]), error_payload


def main() -> int:
    check_result_log_contract()
    check_lark_sync_contract()
    check_lark_setup_and_card()
    check_cli_surface()
    print("explore result layer smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
