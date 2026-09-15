# Durable orchestration

Pekua's orchestration package uses PostgreSQL as the durable system of record. Workers lease jobs with `FOR UPDATE SKIP LOCKED`, so multiple processes can claim work concurrently without serialising the entire queue. Expired leases make interrupted work recoverable.

## Guarantees

- At-least-once execution with tenant-scoped idempotent submission
- Priority and scheduled execution
- Durable attempts, checkpoints and append-only lifecycle events
- Exponential backoff with jitter
- Dead-letter capture and controlled replay
- Per-connector circuit breakers
- Cooperative cancellation and lease heartbeats
- Trace identifiers across jobs and events

Handlers must be idempotent because a worker can fail after completing an external action but before committing success. Connector writes should use a stable operation key derived from the job ID and logical record ID.

## Worker task contract

A handler accepts a JSON-compatible payload and `TaskContext`, then returns `TaskResult`. It may raise `RetryableTaskError` for transient failures or `PermanentTaskError` for invalid or prohibited work. Unknown failures are retried and ultimately dead-lettered.

Long-running handlers must heartbeat before the lease expires, save checkpoints at safe boundaries, and inspect cancellation state between batches.

## API

- `POST /api/v1/jobs`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/cancel`
- `POST /api/v1/jobs/{job_id}/retry`
- `GET /api/v1/jobs/{job_id}/events`

All routes require `X-Tenant-ID`. Submissions also require `Idempotency-Key`. Production authentication middleware must derive and overwrite the tenant identity rather than trusting an arbitrary public header.
