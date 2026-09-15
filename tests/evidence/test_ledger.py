import hashlib
import json
import uuid
from datetime import UTC, datetime

from pekua.evidence.ledger import verify_chain
from pekua.storage.models import EvidenceEvent


def event(sequence: int, previous_hash: str | None) -> EvidenceEvent:
    occurred = datetime(2026, 1, sequence, tzinfo=UTC)
    stream_id = uuid.UUID(int=1)
    content = {
        "stream_id": str(stream_id),
        "sequence": sequence,
        "event_type": "claim.proposed",
        "actor_type": "agent",
        "actor_id": "extractor",
        "payload": {"claim": sequence},
        "previous_hash": previous_hash,
        "occurred_at": occurred.isoformat(),
    }
    digest = hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return EvidenceEvent(
        stream_id=stream_id,
        tenant_id=None,
        sequence=sequence,
        event_type="claim.proposed",
        actor_type="agent",
        actor_id="extractor",
        payload={"claim": sequence},
        previous_hash=previous_hash,
        event_hash=digest,
        occurred_at=occurred,
    )


def test_verifies_valid_chain_and_rejects_tampering() -> None:
    first = event(1, None)
    second = event(2, first.event_hash)
    assert verify_chain([first, second])
    second.payload = {"claim": "changed"}
    assert not verify_chain([first, second])
