from __future__ import annotations

import random

from .contracts import RetryPolicy


def retry_delay(
    policy: RetryPolicy, failed_attempt: int, *, random_value: float | None = None
) -> float:
    base = min(
        policy.maximum_delay_seconds,
        policy.initial_delay_seconds * (policy.multiplier ** max(0, failed_attempt - 1)),
    )
    # Jitter is scheduling noise, not a security token or identifier.
    sample = random.random() if random_value is None else random_value  # noqa: S311
    jitter = base * policy.jitter_ratio * ((sample * 2) - 1)
    return max(0.0, base + jitter)
