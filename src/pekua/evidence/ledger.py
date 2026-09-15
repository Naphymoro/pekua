import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pekua.storage.models import EvidenceEvent, EvidenceStream


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


@dataclass(frozen=True)
class AppendEvent:
    stream_id: uuid.UUID
    event_type: str
    actor_type: str
    actor_id: str
    payload: dict[str, Any]
    tenant_id: uuid.UUID | None = None
    occurred_at: datetime | None = None


class EvidenceLedger:
    """Append-only, tenant-bound, hash-chained evidence history."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(self, request: AppendEvent) -> EvidenceEvent:
        stream = await self.session.scalar(
            select(EvidenceStream)
            .where(
                EvidenceStream.id == request.stream_id,
                EvidenceStream.tenant_id.is_(None)
                if request.tenant_id is None
                else EvidenceStream.tenant_id == request.tenant_id,
            )
            .with_for_update()
        )
        if stream is None:
            raise LookupError("Evidence stream not found for tenant")
        occurred_at = request.occurred_at or datetime.now(UTC)
        sequence = stream.head_sequence + 1
        digest_input = {
            "stream_id": str(request.stream_id),
            "sequence": sequence,
            "event_type": request.event_type,
            "actor_type": request.actor_type,
            "actor_id": request.actor_id,
            "payload": request.payload,
            "previous_hash": stream.head_hash,
            "occurred_at": occurred_at.isoformat(),
        }
        event_hash = hashlib.sha256(_canonical(digest_input)).hexdigest()
        event = EvidenceEvent(
            stream_id=request.stream_id,
            tenant_id=request.tenant_id,
            sequence=sequence,
            event_type=request.event_type,
            actor_type=request.actor_type,
            actor_id=request.actor_id,
            payload=request.payload,
            previous_hash=stream.head_hash,
            event_hash=event_hash,
            occurred_at=occurred_at,
        )
        self.session.add(event)
        stream.head_sequence = sequence
        stream.head_hash = event_hash
        await self.session.flush()
        return event


def verify_chain(events: list[EvidenceEvent]) -> bool:
    previous_hash: str | None = None
    for expected_sequence, event in enumerate(events, 1):
        if event.sequence != expected_sequence or event.previous_hash != previous_hash:
            return False
        digest_input = {
            "stream_id": str(event.stream_id),
            "sequence": event.sequence,
            "event_type": event.event_type,
            "actor_type": event.actor_type,
            "actor_id": event.actor_id,
            "payload": event.payload,
            "previous_hash": event.previous_hash,
            "occurred_at": event.occurred_at.isoformat(),
        }
        if hashlib.sha256(_canonical(digest_input)).hexdigest() != event.event_hash:
            return False
        previous_hash = event.event_hash
    return True
