from __future__ import annotations

from typing import Any


PROJECT_SKILL_DELIVERY_CATALOG_ENTRY: dict[str, Any] = {
    "id": "project-skill-delivery",
    "origin": "builtin",
    "visibility": "public",
    "provider_id": "loopx-core",
    "documentation": {
        "source_root": "loopx/capabilities/project_skill_delivery",
        "site_root": "capabilities/project-skill-delivery",
        "canonical": "README.md",
        "aliases": [
            {
                "source": "README.md",
                "site": "reference/project-skill-delivery.md",
            },
        ],
    },
    "title": "Managed project skill delivery",
    "status": "active-preview",
    "real_world_anchor": (
        "one release-owned skill delivered into selected projects for "
        "Codex, Claude Code, or OpenCode"
    ),
    "user_value": (
        "Keep capability skills out of global agent configuration while "
        "installing, upgrading, and removing verified project-local copies "
        "through one host-neutral lifecycle."
    ),
    "entry_command": (
        "loopx project-skill status --project . --skill <skill-id> "
        "--surface codex --format json"
    ),
    "commands": [
        {
            "command": (
                "loopx project-skill status --project . --skill "
                "<skill-id> --surface <surface> --format json"
            ),
            "purpose": "Inspect source and managed-copy digests without writing the project.",
            "write_boundary": "read-only project and release inspection",
        },
        {
            "command": (
                "loopx project-skill install --project . --skill "
                "<skill-id> --surface <surface> --execute --format json"
            ),
            "purpose": "Transactionally install or upgrade one release-owned project skill for one or more agent hosts.",
            "write_boundary": "managed host-native project skill directories only; unmanaged or locally modified targets fail closed",
        },
        {
            "command": (
                "loopx project-skill uninstall --project . --skill "
                "<skill-id> --surface <surface> --execute --format json"
            ),
            "purpose": "Transactionally remove verified managed copies while preserving user-owned targets.",
            "write_boundary": "verified managed host-native project skill directories only",
        },
    ],
    "implemented_protocols": [
        {
            "schema_version": "loopx_project_skill_status_v0",
            "module": "loopx.capabilities.project_skill_delivery.core",
            "doc": "loopx/capabilities/project_skill_delivery/README.md",
        },
        {
            "schema_version": "loopx_managed_project_skill_v0",
            "module": "loopx.capabilities.project_skill_delivery.core",
            "doc": "loopx/capabilities/project_skill_delivery/README.md",
        },
    ],
    "smokes": ["python -m pytest tests/test_project_skill_cli.py -q"],
    "docs": ["loopx/capabilities/project_skill_delivery/README.md"],
    "boundaries": [
        "Only release skills explicitly marked global or project can be delivered; the marker declares default discovery, not authority.",
        "Project connection, preview-first mutation, digest readback, symlink containment, and rollback are mandatory.",
        "Skill discovery never creates a goal, todo, write scope, domain authority, credential, or external permission.",
        "Public delivery metadata contains no private project content, locators, provider payloads, or credentials.",
    ],
    "next_real_step": (
        "Dogfood a second project-scoped skill or host combination before "
        "considering higher-level automatic installation."
    ),
}
