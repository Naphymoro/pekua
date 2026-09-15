"""Tenant-scoped RBAC and document licence gates."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    VIEWER = "viewer"
    RESEARCHER = "researcher"
    VALIDATOR = "validator"
    CONNECTOR_ADMIN = "connector_admin"
    TENANT_ADMIN = "tenant_admin"


class Action(StrEnum):
    EVIDENCE_READ = "evidence:read"
    EVIDENCE_WRITE = "evidence:write"
    EVIDENCE_VALIDATE = "evidence:validate"
    DOCUMENT_READ = "document:read"
    DOCUMENT_INGEST = "document:ingest"
    CONNECTOR_READ = "connector:read"
    CONNECTOR_CONFIGURE = "connector:configure"
    SECRET_ROTATE = "secret:rotate"  # noqa: S105 - permission name, not a credential
    TENANT_ADMIN = "tenant:admin"


_GRANTS: dict[Role, frozenset[Action]] = {
    Role.VIEWER: frozenset({Action.EVIDENCE_READ, Action.CONNECTOR_READ}),
    Role.RESEARCHER: frozenset(
        {
            Action.EVIDENCE_READ,
            Action.EVIDENCE_WRITE,
            Action.DOCUMENT_READ,
            Action.DOCUMENT_INGEST,
            Action.CONNECTOR_READ,
        }
    ),
    Role.VALIDATOR: frozenset(
        {
            Action.EVIDENCE_READ,
            Action.EVIDENCE_VALIDATE,
            Action.DOCUMENT_READ,
            Action.CONNECTOR_READ,
        }
    ),
    Role.CONNECTOR_ADMIN: frozenset(
        {Action.CONNECTOR_READ, Action.CONNECTOR_CONFIGURE, Action.SECRET_ROTATE}
    ),
    Role.TENANT_ADMIN: frozenset(Action),
}


class AuthContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    user_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    roles: frozenset[Role]


class AuditWriter(Protocol):
    def append_security_event(
        self,
        *,
        action: str,
        outcome: str,
        actor_id: str,
        tenant_id: str,
        reason: str | None,
        trace_id: str,
    ) -> None: ...


class AccessDenied(PermissionError):
    """Intentionally contains no sensitive resource details."""


def authorize(
    *,
    context: AuthContext,
    action: Action,
    resource_tenant_id: str,
    trace_id: str,
    audit: AuditWriter,
) -> None:
    same_tenant = context.tenant_id == resource_tenant_id
    permitted = same_tenant and any(action in _GRANTS[role] for role in context.roles)
    reason = (
        None if permitted else ("cross_tenant_access" if not same_tenant else "insufficient_role")
    )
    audit.append_security_event(
        action=action,
        outcome="allowed" if permitted else "denied",
        actor_id=context.user_id,
        tenant_id=context.tenant_id,
        reason=reason,
        trace_id=trace_id,
    )
    if not permitted:
        raise AccessDenied("Access denied")


class LicenseGate(BaseModel):
    model_config = ConfigDict(frozen=True)
    allows_download: bool = False
    allows_storage: bool = False
    allows_extraction: bool = False
    allows_cross_tenant_derivatives: bool = False
    agreement_id: str | None = None

    def require(self, operation: str) -> None:
        allowed = {
            "download": self.allows_download,
            "storage": self.allows_storage,
            "extraction": self.allows_extraction,
            "cross_tenant_derivatives": self.allows_cross_tenant_derivatives,
        }.get(operation, False)
        if not allowed:
            raise AccessDenied(f"Licence does not permit {operation}")
