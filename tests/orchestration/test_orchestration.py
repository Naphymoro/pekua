from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from pekua.orchestration import JobSpec, OrchestrationBase, Orchestrator, TaskResult, Worker
from pekua.orchestration.contracts import PermanentTaskError, RetryPolicy
from pekua.orchestration.models import DeadLetter, Job


def factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def initialize(engine):
    async with engine.begin() as connection:
        await connection.run_sync(OrchestrationBase.metadata.create_all)


async def test_idempotent_submission_returns_original_job():
    engine, sessions = factory()
    await initialize(engine)
    orchestrator = Orchestrator(sessions)
    spec = JobSpec(
        task_type="search",
        payload={"q": "ammonia"},
        tenant_id="aims",
        idempotency_key="same",
    )
    first, created = await orchestrator.submit(spec)
    second, created_again = await orchestrator.submit(spec)
    assert created is True
    assert created_again is False
    assert first.id == second.id
    await engine.dispose()


async def test_worker_succeeds_and_persists_output():
    engine, sessions = factory()
    await initialize(engine)
    job, _ = await Orchestrator(sessions).submit(
        JobSpec(
            task_type="search",
            payload={"q": "hydrogen"},
            tenant_id="aims",
            idempotency_key="job-1",
        )
    )

    async def search(payload, context):
        return TaskResult({"hits": 3})

    worker = Worker(sessions, "worker-1", {"search": search})
    assert await worker.run_once() is True
    async with sessions() as session:
        stored = await session.get(Job, job.id)
        assert stored is not None
        assert stored.state == "succeeded"
        assert stored.output == {"hits": 3}
    await engine.dispose()


async def test_unknown_task_is_dead_lettered_without_retry():
    engine, sessions = factory()
    await initialize(engine)
    job, _ = await Orchestrator(sessions).submit(
        JobSpec(task_type="missing", payload={}, tenant_id="aims", idempotency_key="job-2")
    )
    await Worker(sessions, "worker-1", {}).run_once()
    async with sessions() as session:
        stored = await session.get(Job, job.id)
        assert stored is not None
        assert stored.state == "dead_lettered"
        count = await session.scalar(select(func.count()).select_from(DeadLetter))
        assert count == 1
    await engine.dispose()


async def test_permanent_failure_is_dead_lettered():
    engine, sessions = factory()
    await initialize(engine)
    job, _ = await Orchestrator(sessions).submit(
        JobSpec(task_type="bad", payload={}, tenant_id="aims", idempotency_key="job-3")
    )

    async def fail(payload, context):
        raise PermanentTaskError("invalid query")

    await Worker(sessions, "worker-1", {"bad": fail}).run_once()
    async with sessions() as session:
        stored = await session.get(Job, job.id)
        assert stored is not None
        assert stored.state == "dead_lettered"
    await engine.dispose()


async def test_retryable_failure_requeues_job():
    engine, sessions = factory()
    await initialize(engine)
    job, _ = await Orchestrator(sessions).submit(
        JobSpec(
            task_type="flaky",
            payload={},
            tenant_id="aims",
            idempotency_key="job-4",
            max_attempts=2,
        )
    )

    async def fail(payload, context):
        raise RuntimeError("temporary")

    policy = RetryPolicy(initial_delay_seconds=0, maximum_delay_seconds=0)
    await Worker(sessions, "worker-1", {"flaky": fail}, retry_policy=policy).run_once()
    async with sessions() as session:
        stored = await session.get(Job, job.id)
        assert stored is not None
        assert stored.state == "queued"
        assert stored.attempts == 1
    await engine.dispose()
