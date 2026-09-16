"""Qualify whether the installed runtime proves a selected update source is active.

``loopx update check`` cannot call a release active just because a newer tag or
branch exists: the installed archive has to carry source lineage that proves the
selected update source reached the runtime. This module owns that decision so the
question keeps one home instead of growing inside the self-update command surface.
"""

from __future__ import annotations

import re
from typing import Any


RUNTIME_ACTIVATION_QUALIFICATION_SCHEMA_VERSION = (
    "loopx_runtime_activation_qualification_v0"
)
_FULL_COMMIT_PATTERN = re.compile(r"[0-9a-fA-F]{40}")


def _immutable_source_commit(source: dict[str, Any]) -> str | None:
    """Return the selected source commit when the ref is an immutable full SHA.

    A full commit SHA is its own commit identity: ``scripts/install.sh`` installs
    it without a branch-resolution service, so the qualification can compare it
    against the installed manifest instead of reporting that the trusted target
    source lineage is unavailable.
    """

    ref = str(source.get("ref") or "")
    return ref.lower() if _FULL_COMMIT_PATTERN.fullmatch(ref) else None


def runtime_activation_qualification(
    *,
    install_freshness: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    """Return the typed activation qualification for an archive-snapshot install."""

    installed_commit = install_freshness.get("manifest_source_git_commit")
    target_commit = install_freshness.get("freshness_source_git_commit")
    revision_relation = install_freshness.get("manifest_source_freshness_relation")
    selected_commit = _immutable_source_commit(source)
    if selected_commit and not target_commit:
        # An immutable ref names its own commit, so the qualification resolves it
        # the same way the installer does instead of reporting that the
        # installed-versus-target lineage is unavailable.
        target_commit = selected_commit
        if (
            isinstance(installed_commit, str)
            and installed_commit.lower() == selected_commit
        ):
            revision_relation = "same"
    qualified_repo = install_freshness.get("manifest_source_repo")
    qualified_ref = install_freshness.get("manifest_source_ref")
    selected_repo = source.get("repo")
    selected_ref = source.get("ref")
    package_matches_runtime = install_freshness.get(
        "manifest_package_version_matches_runtime"
    )
    requires_upgrade = install_freshness.get("requires_upgrade")
    has_commit_pair = all(
        isinstance(commit, str) and bool(commit)
        for commit in (installed_commit, target_commit)
    )
    source_identity_matches = all(
        isinstance(value, str) and bool(value)
        for value in (qualified_repo, qualified_ref, selected_repo, selected_ref)
    ) and (
        str(qualified_repo).removesuffix(".git").lower()
        == str(selected_repo).removesuffix(".git").lower()
        and str(qualified_ref).removeprefix("refs/heads/")
        == str(selected_ref).removeprefix("refs/heads/")
    )

    if package_matches_runtime is False:
        decision = "release_or_install_successor_required"
        runtime_active: bool | None = False
        successor_kind = "release_or_install"
        reason = "release manifest package version does not match the active runtime"
    elif not source_identity_matches:
        decision = "activation_qualification_required"
        runtime_active = None
        successor_kind = "activation_qualification"
        reason = "trusted source lineage does not identify the selected update source"
    elif has_commit_pair and (
        installed_commit == target_commit or revision_relation == "installed_ahead"
    ):
        decision = "runtime_active"
        runtime_active = True
        successor_kind = None
        reason = "installed source contains the trusted target source commit"
    elif has_commit_pair and revision_relation in {"installed_behind", "diverged"}:
        decision = "release_or_install_successor_required"
        runtime_active = False
        successor_kind = "release_or_install"
        reason = "installed source does not contain the trusted target source commit"
    elif has_commit_pair and selected_commit:
        decision = "activation_qualification_required"
        runtime_active = None
        successor_kind = "activation_qualification"
        reason = (
            "installed source commit does not match the selected immutable source commit"
        )
    else:
        decision = "activation_qualification_required"
        runtime_active = None
        successor_kind = "activation_qualification"
        reason = "trusted installed-versus-target source lineage is unavailable"

    return {
        "schema_version": RUNTIME_ACTIVATION_QUALIFICATION_SCHEMA_VERSION,
        "decision": decision,
        "runtime_active": runtime_active,
        "installed_release_id": install_freshness.get("release_id"),
        "installed_version": install_freshness.get("current_version"),
        "installed_source_commit": installed_commit,
        "target_source_label": install_freshness.get("freshness_source_label"),
        "target_source_commit": target_commit,
        "revision_relation": revision_relation,
        "qualified_source": {
            "repo": qualified_repo,
            "ref": qualified_ref,
        },
        "source_identity_matches": source_identity_matches,
        "package_version_matches_runtime": package_matches_runtime,
        "requires_upgrade": requires_upgrade,
        "selected_source": {
            "repo": selected_repo,
            "ref": selected_ref,
        },
        "successor": {
            "required": runtime_active is not True,
            "kind": successor_kind,
        },
        "reason": reason,
    }
