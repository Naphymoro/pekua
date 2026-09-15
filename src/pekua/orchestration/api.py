from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .contracts import JobSpec, JobState
from .models import DeadLetter, Job, JobEvent
from .repository import JobRepository

router = APIRouter(prefix="/api/v1/jobs", tags=["orchestration"])
_sessions: async_sessionmaker[AsyncSession] | None = None


def configure_session_factory(sessions: async_sessionmaker[AsyncSession]) -> None:
    global _sessions
    _sessions = sessions


async def get_session():  # type: ignore[no-untyped-def]
    if _sessions is None:
        raise RuntimeError("orchestration database is not configured")
    async with _sessions() as session:
        yield session


Db = Annotated[AsyncSession, Depends(get_session)]
Tenant = Annotated[str, Header(alias="X-Tenant-ID")]


class SubmitJobRequest(BaseModel):
    task_type: str = Field(min_length=1, max_length=160)
    payload: dict[str, Any] = Field(default_factory=dict)
    connector: str | None = Field(default=None, max_length=160)
    priority: int = Field(default=100, ge=0, le=1000)
    max_attempts: int = Field(default=4, ge=1, le=20)
    parent_job_id: str | None = None
    scheduled_at: datetime | None = None


class JobResponse(BaseModel):
    id: str
    task_type: str
    connector: str | None
    state: str
    priority: int
    attempts: int
    max_attempts: int
    trace_id: str
    scheduled_at: datetime
    created_at: datetime
    completed_at: datetime | None
    output: dict[str, Any] | None
    last_error_code: str | None
    last_error_message: str | None
    model_config = {"from_attributes": True}


async def tenant_job(session: AsyncSession, job_id: str, tenant: str) -> Job:
    job = await session.scalar(select(Job).where(Job.id == job_id, Job.tenant_id == tenant))
    if not job:
        raise HTTPException(404, "job not found")
    return job


@router.post("", response_model=JobResponse, status_code=202)
async def submit_job(
    request: SubmitJobRequest,
    session: Db,
    tenant: Tenant,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    trace_id: Annotated[str | None, Header(alias="X-Trace-ID")] = None,
) -> Job:
    values: dict[str, Any] = {}
    if request.scheduled_at:
        values["scheduled_at"] = request.scheduled_at
    spec = JobSpec(
        task_type=request.task_type,
        payload=request.payload,
        tenant_id=tenant,
        idempotency_key=idempotency_key,
        connector=request.connector,
        priority=request.priority,
        max_attempts=request.max_attempts,
        parent_job_id=request.parent_job_id,
        trace_id=trace_id,
        **values,
    )
    job, _ = await JobRepository(session).submit(spec)
    return job


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    session: Db, tenant: Tenant, state: JobState | None = None, limit: int = Query(50, ge=1, le=200)
) -> list[Job]:
    query = select(Job).where(Job.tenant_id == tenant).order_by(Job.created_at.desc()).limit(limit)
    if state:
        query = query.where(Job.state == state)
    return list((await session.scalars(query)).all())


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, session: Db, tenant: Tenant) -> Job:
    return await tenant_job(session, job_id, tenant)


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: str, session: Db, tenant: Tenant) -> Job:
    job = await tenant_job(session, job_id, tenant)
    if job.state in {JobState.SUCCEEDED, JobState.CANCELLED, JobState.DEAD_LETTERED}:
        raise HTTPException(409, f"cannot cancel {job.state} job")
    await JobRepository(session).request_cancel(job)
    return job


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: str, session: Db, tenant: Tenant) -> Job:
    job = await tenant_job(session, job_id, tenant)
    dead = await session.scalar(
        select(DeadLetter).where(DeadLetter.job_id == job.id, DeadLetter.replayed_at.is_(None))
    )
    if not dead:
        raise HTTPException(409, "no replayable dead letter")
    return await JobRepository(session).replay(dead)


@router.get("/{job_id}/events")
async def job_events(job_id: str, session: Db, tenant: Tenant) -> list[dict[str, Any]]:
    await tenant_job(session, job_id, tenant)
    rows = (
        await session.scalars(
            select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.created_at)
        )
    ).all()
    return [
        {
            "id": row.id,
            "kind": row.kind,
            "data": row.data,
            "trace_id": row.trace_id,
            "created_at": row.created_at,
        }
        for row in rows
    ]
