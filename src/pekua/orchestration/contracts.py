from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTERED = "dead_lettered"


class EventKind(StrEnum):
    SUBMITTED = "submitted"
    LEASED = "leased"
    STARTED = "started"
    CHECKPOINTED = "checkpointed"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    DEAD_LETTERED = "dead_lettered"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 4
    initial_delay_seconds: float = 2.0
    maximum_delay_seconds: float = 300.0
    multiplier: float = 2.0
    jitter_ratio: float = 0.2

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay_seconds < 0 or self.maximum_delay_seconds < 0:
            raise ValueError("retry delays cannot be negative")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class JobSpec:
    task_type: str
    payload: dict[str, Any]
    tenant_id: str
    idempotency_key: str
    connector: str | None = None
    priority: int = 100
    max_attempts: int = 4
    parent_job_id: str | None = None
    trace_id: str | None = None
    scheduled_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.task_type.strip():
            raise ValueError("task_type is required")
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")


@dataclass(slots=True)
class TaskContext:
    job_id: str
    attempt: int
    tenant_id: str
    trace_id: str
    checkpoint: dict[str, Any] | None = None
    cancellation_requested: bool = False


@dataclass(frozen=True, slots=True)
class TaskResult:
    output: dict[str, Any] = field(default_factory=dict)


class RetryableTaskError(RuntimeError):
    """A transient error that is safe to retry."""


class PermanentTaskError(RuntimeError):
    """A terminal task error that must not be retried."""


class CircuitOpenError(RetryableTaskError):
    """The connector circuit is open and should not receive traffic."""
