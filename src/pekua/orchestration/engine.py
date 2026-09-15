from __future__ import annotations

from collections.abc import Awaitable
from datetime import timedelta
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .contracts import (
    CircuitOpenError,
    JobSpec,
    PermanentTaskError,
    RetryPolicy,
    TaskContext,
    TaskResult,
)
from .models import Job, utcnow
from .repository import CircuitBreakerRepository, JobRepository
from .retry import retry_delay


class TaskHandler(Protocol):
    def __call__(
        self, payload: dict[str, object], context: TaskContext
    ) -> Awaitable[TaskResult]: ...


class Orchestrator:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def submit(self, spec: JobSpec) -> tuple[Job, bool]:
        async with self.sessions() as session:
            return await JobRepository(session).submit(spec)


class Worker:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        worker_id: str,
        handlers: dict[str, TaskHandler],
        retry_policy: RetryPolicy | None = None,
        lease_seconds: int = 60,
    ) -> None:
        self.sessions, self.worker_id, self.handlers = sessions, worker_id, handlers
        self.retry_policy, self.lease_seconds = retry_policy or RetryPolicy(), lease_seconds

    async def run_once(self) -> bool:
        async with self.sessions() as session:
            jobs, circuits = JobRepository(session), CircuitBreakerRepository(session)
            job = await jobs.claim(self.worker_id, lease_seconds=self.lease_seconds)
            if not job:
                return False
            if job.connector and not await circuits.allow(job.connector):
                await self._fail(jobs, job, CircuitOpenError(job.connector), True)
                return True
            handler = self.handlers.get(job.task_type)
            if not handler:
                await self._fail(
                    jobs, job, PermanentTaskError(f"unknown task: {job.task_type}"), False
                )
                return True
            context = TaskContext(
                job.id,
                job.attempts,
                job.tenant_id,
                job.trace_id,
                await jobs.latest_checkpoint(job.id),
                job.cancellation_requested,
            )
            try:
                result = await handler(job.payload, context)
                await jobs.succeed(job, result.output)
                if job.connector:
                    await circuits.success(job.connector)
            except PermanentTaskError as exc:
                await self._fail(jobs, job, exc, False)
            except Exception as exc:
                await self._fail(jobs, job, exc, True)
                if job.connector:
                    await circuits.failure(job.connector)
            return True

    async def heartbeat(self, job_id: str) -> bool:
        async with self.sessions() as session:
            return await JobRepository(session).heartbeat(
                job_id, self.worker_id, self.lease_seconds
            )

    async def checkpoint(self, job_id: str, data: dict[str, object]) -> None:
        async with self.sessions() as session:
            job = await session.get(Job, job_id)
            if not job:
                raise LookupError(job_id)
            await JobRepository(session).checkpoint(job, data)

    async def _fail(self, jobs: JobRepository, job: Job, exc: Exception, retryable: bool) -> None:
        retry_at = None
        if retryable and job.attempts < job.max_attempts:
            retry_at = utcnow() + timedelta(seconds=retry_delay(self.retry_policy, job.attempts))
        await jobs.fail(job, type(exc).__name__, str(exc), retry_at)
