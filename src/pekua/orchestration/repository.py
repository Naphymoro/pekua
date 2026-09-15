from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .contracts import EventKind, JobSpec, JobState
from .models import CircuitBreaker, DeadLetter, Job, JobAttempt, JobCheckpoint, JobEvent, utcnow


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit(self, spec: JobSpec) -> tuple[Job, bool]:
        existing = await self.session.scalar(
            select(Job).where(
                Job.tenant_id == spec.tenant_id, Job.idempotency_key == spec.idempotency_key
            )
        )
        if existing:
            return existing, False
        job = Job(
            tenant_id=spec.tenant_id,
            task_type=spec.task_type,
            connector=spec.connector,
            payload=spec.payload,
            priority=spec.priority,
            idempotency_key=spec.idempotency_key,
            trace_id=spec.trace_id or uuid4().hex,
            parent_job_id=spec.parent_job_id,
            max_attempts=spec.max_attempts,
            scheduled_at=spec.scheduled_at,
        )
        self.session.add(job)
        await self.session.flush()
        self.event(job, EventKind.SUBMITTED, {"task_type": job.task_type})
        await self.session.commit()
        return job, True

    async def claim(self, worker_id: str, *, lease_seconds: int = 60) -> Job | None:
        now = utcnow()
        job = await self.session.scalar(
            select(Job)
            .where(
                and_(
                    Job.state.in_([JobState.QUEUED, JobState.RUNNING]),
                    Job.scheduled_at <= now,
                    Job.cancellation_requested.is_(False),
                    or_(Job.lease_expires_at.is_(None), Job.lease_expires_at < now),
                )
            )
            .order_by(Job.priority, Job.scheduled_at, Job.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return None
        job.state, job.lease_owner = JobState.RUNNING, worker_id
        job.lease_expires_at, job.attempts = (
            now + timedelta(seconds=lease_seconds),
            job.attempts + 1,
        )
        self.session.add(
            JobAttempt(job_id=job.id, attempt_number=job.attempts, worker_id=worker_id)
        )
        self.event(job, EventKind.LEASED, {"worker_id": worker_id, "attempt": job.attempts})
        await self.session.commit()
        return job

    async def heartbeat(self, job_id: str, worker_id: str, lease_seconds: int = 60) -> bool:
        result = await self.session.execute(
            update(Job)
            .where(Job.id == job_id, Job.lease_owner == worker_id, Job.state == JobState.RUNNING)
            .values(
                lease_expires_at=utcnow() + timedelta(seconds=lease_seconds), updated_at=utcnow()
            )
        )
        await self.session.commit()
        return (getattr(result, "rowcount", 0) or 0) > 0

    async def checkpoint(self, job: Job, data: dict[str, object]) -> JobCheckpoint:
        latest = await self.session.scalar(
            select(JobCheckpoint.sequence)
            .where(JobCheckpoint.job_id == job.id)
            .order_by(JobCheckpoint.sequence.desc())
            .limit(1)
        )
        checkpoint = JobCheckpoint(job_id=job.id, sequence=(latest or 0) + 1, data=data)
        self.session.add(checkpoint)
        self.event(job, EventKind.CHECKPOINTED, {"sequence": checkpoint.sequence})
        await self.session.commit()
        return checkpoint

    async def latest_checkpoint(self, job_id: str) -> dict[str, object] | None:
        item = await self.session.scalar(
            select(JobCheckpoint)
            .where(JobCheckpoint.job_id == job_id)
            .order_by(JobCheckpoint.sequence.desc())
            .limit(1)
        )
        return item.data if item else None

    async def succeed(self, job: Job, output: dict[str, object]) -> None:
        now = utcnow()
        job.state, job.output, job.completed_at = JobState.SUCCEEDED, output, now
        job.lease_owner = job.lease_expires_at = None
        attempt = await self._attempt(job)
        if attempt:
            attempt.state, attempt.finished_at = JobState.SUCCEEDED, now
        self.event(job, EventKind.SUCCEEDED, {})
        await self.session.commit()

    async def fail(self, job: Job, code: str, message: str, retry_at: datetime | None) -> None:
        now = utcnow()
        job.last_error_code, job.last_error_message = code, message[:4000]
        job.lease_owner = job.lease_expires_at = None
        attempt = await self._attempt(job)
        if attempt:
            attempt.state, attempt.finished_at = JobState.FAILED, now
            attempt.error_code, attempt.error_message = code, message[:4000]
        if retry_at and job.attempts < job.max_attempts:
            job.state, job.scheduled_at = JobState.QUEUED, retry_at
            self.event(job, EventKind.RETRY_SCHEDULED, {"scheduled_at": retry_at.isoformat()})
        else:
            job.state, job.completed_at = JobState.DEAD_LETTERED, now
            self.session.add(
                DeadLetter(job_id=job.id, reason=message[:4000], payload_snapshot=job.payload)
            )
            self.event(job, EventKind.DEAD_LETTERED, {"code": code})
        await self.session.commit()

    async def request_cancel(self, job: Job) -> None:
        job.cancellation_requested = True
        if job.state == JobState.QUEUED:
            job.state, job.completed_at = JobState.CANCELLED, utcnow()
            self.event(job, EventKind.CANCELLED, {})
        else:
            self.event(job, EventKind.CANCEL_REQUESTED, {})
        await self.session.commit()

    async def replay(self, dead: DeadLetter) -> Job:
        job = await self.session.get(Job, dead.job_id)
        if not job:
            raise LookupError(dead.job_id)
        job.state, job.attempts, job.scheduled_at = JobState.QUEUED, 0, utcnow()
        job.completed_at, job.cancellation_requested, dead.replayed_at = None, False, utcnow()
        self.event(job, EventKind.RETRY_SCHEDULED, {"source": "dead_letter_replay"})
        await self.session.commit()
        return job

    def event(self, job: Job, kind: EventKind, data: dict[str, object]) -> None:
        self.session.add(JobEvent(job_id=job.id, trace_id=job.trace_id, kind=kind, data=data))

    async def _attempt(self, job: Job) -> JobAttempt | None:
        return cast(
            JobAttempt | None,
            await self.session.scalar(
                select(JobAttempt).where(
                    JobAttempt.job_id == job.id, JobAttempt.attempt_number == job.attempts
                )
            ),
        )


class CircuitBreakerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def allow(self, connector: str) -> bool:
        circuit = await self.session.get(CircuitBreaker, connector)
        if not circuit or circuit.state == "closed":
            return True
        if circuit.state == "open" and circuit.retry_after and circuit.retry_after <= utcnow():
            circuit.state, circuit.half_open_claimed = "half_open", True
            await self.session.commit()
            return True
        return False

    async def success(self, connector: str) -> None:
        circuit = await self.session.get(CircuitBreaker, connector)
        if circuit:
            circuit.state, circuit.consecutive_failures = "closed", 0
            circuit.opened_at = circuit.retry_after = None
            circuit.half_open_claimed = False
            await self.session.commit()

    async def failure(self, connector: str, cooldown_seconds: int = 60) -> None:
        circuit = await self.session.get(CircuitBreaker, connector)
        if not circuit:
            circuit = CircuitBreaker(connector=connector)
            self.session.add(circuit)
        circuit.consecutive_failures += 1
        if (
            circuit.state == "half_open"
            or circuit.consecutive_failures >= circuit.failure_threshold
        ):
            circuit.state, circuit.opened_at = "open", utcnow()
            circuit.retry_after, circuit.half_open_claimed = (
                utcnow() + timedelta(seconds=cooldown_seconds),
                False,
            )
        await self.session.commit()
