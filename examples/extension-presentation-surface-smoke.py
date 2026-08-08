#!/usr/bin/env python3
"""Prove extension-gated presentation projection lifecycle behavior."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from loopx.extensions.presentation import (
    collect_active_extension_presentation_surfaces,
    default_extension_projection_root,
    publish_extension_projection,
)
from loopx.extensions.runtime import (
    disable_extension,
    doctor_installed_extension,
    enable_extension,
    install_extension,
)


EXTENSION_ID = "synthetic-research-extension"
SURFACE_ID = "investment-research"
VIEW_SCHEMA = "synthetic_dashboard_v0"


def _view() -> dict[str, object]:
    # Core keeps views opaque unless an extension registers a validator for the
    # declared view_schema. This lifecycle smoke uses a synthetic, structure-only
    # view so it proves generic Core behavior without depending on any one
    # domain's schema (finance owns and tests its own view separately).
    return {
        "headline": "Synthetic lifecycle view",
        "sections": [
            {
                "id": "summary",
                "title": "Summary",
                "body": "Opaque passthrough content for the lifecycle proof.",
            }
        ],
    }


def _provider_result() -> dict[str, object]:
    return {
        "schema_version": "synthetic_research_packet_v0",
        "presentation_projection": {
            "schema_version": "extension_presentation_projection_v0",
            "surface_id": SURFACE_ID,
            "goal_id": "synthetic-research-goal",
            "generated_at": "2026-01-15T12:00:00+00:00",
            "review_due_at": "2027-01-15T12:00:00+00:00",
            "lineage": {
                "source_id": "synthetic-research-2026-01-15",
                "version": 1,
                "row_lifecycle": "active",
                "supersedes": [],
                "superseded_by": None,
            },
            "view_schema": VIEW_SCHEMA,
            "view": _view(),
        },
    }


def _write_provider(path: Path, response_path: Path) -> None:
    path.write_text(
        f"""#!{sys.executable}
import json
from pathlib import Path
import sys

if "--doctor" in sys.argv:
    raise SystemExit(0)

json.load(sys.stdin)
json.dump(json.loads(Path({str(response_path)!r}).read_text(encoding="utf-8")), sys.stdout)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_manifest(
    path: Path,
    *,
    provider: Path,
    version: str,
) -> None:
    path.write_text(
        f"""\
schema_version = "loopx_extension_manifest_v0"
id = "{EXTENSION_ID}"
version = "{version}"
requires_loopx_api = ">=1,<2"
permissions = []

[runtime]
protocol = "synthetic_research_provider_v0"
entrypoint = {json.dumps(str(provider))}
doctor_args = ["--doctor"]
required_permissions = []
timeout_seconds = 5

[[presentation_surfaces]]
id = "{SURFACE_ID}"
kind = "synthetic_dashboard"
title = "Investment Research"
view_schema = "synthetic_dashboard_v0"
view_validator = "loopx.extensions.presentation:validate_opaque_presentation_view"
visibility = "public-safe"
empty_state_title = "No validated research yet"
empty_state_detail = "Publish a validated projection."
""",
        encoding="utf-8",
    )


def _canonical_hash(envelope: dict[str, object]) -> str:
    payload = {
        key: value
        for key, value in envelope.items()
        if key != "payload_sha256"
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _only_item(
    collection: dict[str, object],
    *,
    expected_state: str,
) -> dict[str, object]:
    assert collection["count"] == 1, collection
    items = collection["items"]
    assert isinstance(items, list)
    item = items[0]
    assert isinstance(item, dict)
    assert item["state"] == expected_state, item
    return item


def main() -> int:
    with tempfile.TemporaryDirectory(
        prefix="loopx-extension-presentation-surface-"
    ) as raw_temp:
        temp = Path(raw_temp)
        state_file = temp / "runtime" / "extensions" / "state.json"
        provider = temp / "provider"
        response_path = temp / "response.json"
        manifest_a = temp / "extension-a.toml"
        manifest_b = temp / "extension-b.toml"
        response_path.write_text(
            json.dumps(_provider_result(), ensure_ascii=False),
            encoding="utf-8",
        )
        _write_provider(provider, response_path)
        _write_manifest(manifest_a, provider=provider, version="1.0.0")
        _write_manifest(manifest_b, provider=provider, version="2.0.0")

        missing = collect_active_extension_presentation_surfaces(
            state_file=state_file
        )
        assert missing["count"] == 0, missing

        installed_a = install_extension(
            manifest_a,
            state_file=state_file,
            execute=True,
        )
        revision_a = installed_a["revision"]

        disable_extension(EXTENSION_ID, state_file=state_file, execute=True)
        disabled = collect_active_extension_presentation_surfaces(
            state_file=state_file
        )
        assert disabled["count"] == 0, disabled

        enable_extension(EXTENSION_ID, state_file=state_file, execute=True)
        provider.write_text(
            provider.read_text(encoding="utf-8") + "# runtime identity changed\n",
            encoding="utf-8",
        )
        stale = collect_active_extension_presentation_surfaces(
            state_file=state_file
        )
        assert stale["count"] == 0, stale

        doctor = doctor_installed_extension(
            EXTENSION_ID,
            state_file=state_file,
            execute=True,
        )
        assert doctor["verified"] is True, doctor
        empty = collect_active_extension_presentation_surfaces(
            state_file=state_file
        )
        _only_item(empty, expected_state="empty")

        request = {"schema_version": "synthetic_research_request_v0"}
        preview = publish_extension_projection(
            EXTENSION_ID,
            SURFACE_ID,
            state_file=state_file,
            request=request,
        )
        assert preview["dry_run"] is True, preview
        assert preview["executed"] is False, preview

        published = publish_extension_projection(
            EXTENSION_ID,
            SURFACE_ID,
            state_file=state_file,
            request=request,
            execute=True,
        )
        assert published["status"] == "published", published
        assert published["readback_verified"] is True, published

        projection_path = (
            default_extension_projection_root(state_file)
            / EXTENSION_ID
            / f"{SURFACE_ID}.json"
        )
        envelope_a = json.loads(projection_path.read_text(encoding="utf-8"))
        assert envelope_a["extension_revision"] == revision_a
        assert envelope_a["payload_sha256"] == published["payload_sha256"]
        assert envelope_a["payload_sha256"] == _canonical_hash(envelope_a)

        ready = collect_active_extension_presentation_surfaces(
            state_file=state_file,
            now=datetime(2026, 1, 16, tzinfo=timezone.utc),
        )
        ready_item = _only_item(ready, expected_state="ready")
        # Status is a compact index: it references the published projection by
        # content-addressed pointer rather than inlining the full view.
        assert "view" not in ready_item, ready_item
        assert ready_item["detail_ref"] == {
            "extension_id": EXTENSION_ID,
            "surface_id": SURFACE_ID,
            "extension_revision": revision_a,
            "payload_sha256": envelope_a["payload_sha256"],
        }, ready_item

        disable_extension(EXTENSION_ID, state_file=state_file, execute=True)
        hidden = collect_active_extension_presentation_surfaces(
            state_file=state_file
        )
        assert hidden["count"] == 0, hidden

        enable_extension(EXTENSION_ID, state_file=state_file, execute=True)
        doctor_installed_extension(
            EXTENSION_ID,
            state_file=state_file,
            execute=True,
        )
        restored = collect_active_extension_presentation_surfaces(
            state_file=state_file,
            now=datetime(2026, 1, 16, tzinfo=timezone.utc),
        )
        _only_item(restored, expected_state="ready")

        installed_b = install_extension(
            manifest_b,
            state_file=state_file,
            operation="upgrade",
            execute=True,
        )
        revision_b = installed_b["revision"]
        assert revision_b != revision_a
        assert projection_path.exists()
        assert json.loads(projection_path.read_text(encoding="utf-8"))[
            "extension_revision"
        ] == revision_a
        upgraded = collect_active_extension_presentation_surfaces(
            state_file=state_file
        )
        _only_item(upgraded, expected_state="empty")

        corrupted_b = dict(envelope_a)
        corrupted_b["extension_revision"] = revision_b
        projection_path.write_text(
            json.dumps(corrupted_b, ensure_ascii=False),
            encoding="utf-8",
        )
        invalid = collect_active_extension_presentation_surfaces(
            state_file=state_file
        )
        invalid_item = _only_item(invalid, expected_state="invalid")
        assert invalid_item["diagnostic"] == "projection_hash_invalid"
        assert "view" not in invalid_item

    print("extension-presentation-surface-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
