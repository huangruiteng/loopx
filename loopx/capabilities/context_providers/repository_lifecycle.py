from __future__ import annotations

from dataclasses import dataclass

from .base import ContextProviderSync, opaque_provider_ref


REPOSITORY_CONTEXT_REVISION_PLAN_SCHEMA_VERSION = "repository_context_revision_plan_v0"
REPOSITORY_CONTEXT_ACTIVATION_SCHEMA_VERSION = "repository_context_activation_v0"


@dataclass(frozen=True)
class RepositoryContextRevisionPlan:
    """Provider-neutral plan for one checkout's repository context.

    Provider resource identifiers remain internal. Public projections expose
    only opaque references, revisions, and the activation decision.
    """

    provider: str
    namespace: str
    revision_policy: str
    repository_revision: str
    current_scope_ref: str
    active_repository_revision: str | None = None
    active_scope_ref: str | None = None

    @property
    def revision_changed(self) -> bool:
        return bool(
            self.active_repository_revision
            and self.active_repository_revision != self.repository_revision
        )

    @property
    def sync_required(self) -> bool:
        return self.revision_policy == "checkout_head" and (
            self.active_repository_revision != self.repository_revision
            or self.active_scope_ref != self.current_scope_ref
        )

    @property
    def retrieval_scope_ref(self) -> str | None:
        if self.revision_policy == "pinned" or not self.sync_required:
            return self.current_scope_ref
        return None

    def public_packet(self) -> dict[str, object]:
        return {
            "schema_version": REPOSITORY_CONTEXT_REVISION_PLAN_SCHEMA_VERSION,
            "ok": True,
            "provider": self.provider,
            "namespace": self.namespace,
            "visibility": "public",
            "revision_policy": self.revision_policy,
            "repository_revision": self.repository_revision,
            "active_repository_revision": self.active_repository_revision,
            "revision_changed": self.revision_changed,
            "sync_required": self.sync_required,
            "retrieval_allowed": self.retrieval_scope_ref is not None,
            "current_scope_ref": opaque_provider_ref(
                provider=self.provider,
                namespace=self.namespace,
                resource_ref=self.current_scope_ref,
            ),
            "active_scope_ref": (
                opaque_provider_ref(
                    provider=self.provider,
                    namespace=self.namespace,
                    resource_ref=self.active_scope_ref,
                )
                if self.active_scope_ref
                else None
            ),
            "stale_revision_policy": "preserve_for_audit_exclude_from_retrieval",
            "raw_provider_refs_captured": False,
        }


@dataclass(frozen=True)
class RepositoryContextActivation:
    provider: str
    namespace: str
    repository_revision: str
    status: str
    active_repository_revision: str | None
    active_scope_ref: str | None
    previous_repository_revision: str | None
    previous_scope_ref: str | None
    reason_code: str | None = None

    @property
    def retrieval_scope_ref(self) -> str | None:
        if (
            self.status == "activated"
            and self.active_repository_revision == self.repository_revision
        ):
            return self.active_scope_ref
        return None

    def public_packet(self) -> dict[str, object]:
        return {
            "schema_version": REPOSITORY_CONTEXT_ACTIVATION_SCHEMA_VERSION,
            "ok": self.status in {"activated", "planned"},
            "provider": self.provider,
            "namespace": self.namespace,
            "visibility": "public",
            "status": self.status,
            "reason_code": self.reason_code,
            "repository_revision": self.repository_revision,
            "active_repository_revision": self.active_repository_revision,
            "previous_repository_revision": self.previous_repository_revision,
            "retrieval_allowed": self.retrieval_scope_ref is not None,
            "active_scope_ref": (
                opaque_provider_ref(
                    provider=self.provider,
                    namespace=self.namespace,
                    resource_ref=self.active_scope_ref,
                )
                if self.active_scope_ref
                else None
            ),
            "previous_scope_ref": (
                opaque_provider_ref(
                    provider=self.provider,
                    namespace=self.namespace,
                    resource_ref=self.previous_scope_ref,
                )
                if self.previous_scope_ref
                else None
            ),
            "stale_revision_policy": "preserve_for_audit_exclude_from_retrieval",
            "raw_provider_refs_captured": False,
        }


def activate_repository_context_revision(
    plan: RepositoryContextRevisionPlan,
    sync: ContextProviderSync,
) -> RepositoryContextActivation:
    """Activate only a fully verified current-revision sync.

    A committed-but-pending provider mutation is not yet safe for retrieval.
    The previous revision remains auditable but is never returned as a patch
    guidance fallback for the new checkout.
    """

    if sync.provider != plan.provider or sync.namespace != plan.namespace:
        raise ValueError("repository context sync does not match the revision plan")
    if (
        sync.status == "completed"
        and sync.requested_count > 0
        and sync.completed_count == sync.requested_count
    ):
        status = "activated"
        reason_code = None
        active_revision = plan.repository_revision
        active_scope = plan.current_scope_ref
    elif sync.status == "planned":
        status = "planned"
        reason_code = "execute_required_for_revision_activation"
        active_revision = None
        active_scope = None
    elif sync.status == "committed_pending":
        status = "activation_pending"
        reason_code = "current_revision_index_pending"
        active_revision = None
        active_scope = None
    else:
        status = "activation_blocked"
        reason_code = sync.reason_code or "current_revision_sync_incomplete"
        active_revision = None
        active_scope = None
    return RepositoryContextActivation(
        provider=plan.provider,
        namespace=plan.namespace,
        repository_revision=plan.repository_revision,
        status=status,
        active_repository_revision=active_revision,
        active_scope_ref=active_scope,
        previous_repository_revision=plan.active_repository_revision,
        previous_scope_ref=plan.active_scope_ref,
        reason_code=reason_code,
    )
