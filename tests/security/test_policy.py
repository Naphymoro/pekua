import pytest

from pekua.auth.policy import AccessDenied, Action, AuthContext, LicenseGate, Role, authorize


class Audit:
    def __init__(self) -> None:
        self.events = []

    def append_security_event(self, **event) -> None:
        self.events.append(event)


def test_permits_granted_action_in_same_tenant() -> None:
    audit = Audit()
    context = AuthContext(user_id="u1", tenant_id="t1", roles={Role.RESEARCHER})
    authorize(
        context=context,
        action=Action.DOCUMENT_INGEST,
        resource_tenant_id="t1",
        trace_id="trace",
        audit=audit,
    )
    assert audit.events[-1]["outcome"] == "allowed"


def test_denies_cross_tenant_access_and_audits() -> None:
    audit = Audit()
    context = AuthContext(user_id="u1", tenant_id="t1", roles={Role.TENANT_ADMIN})
    with pytest.raises(AccessDenied):
        authorize(
            context=context,
            action=Action.DOCUMENT_READ,
            resource_tenant_id="t2",
            trace_id="trace",
            audit=audit,
        )
    assert audit.events[-1]["reason"] == "cross_tenant_access"


def test_license_gate_fails_closed() -> None:
    gate = LicenseGate(allows_download=True)
    gate.require("download")
    with pytest.raises(AccessDenied):
        gate.require("extraction")
    with pytest.raises(AccessDenied):
        gate.require("unknown")
