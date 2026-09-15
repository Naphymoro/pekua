# Monitoring and audit specification

All requests and jobs carry a non-secret trace ID. Logs are structured JSON and
include tenant ID, actor ID, job ID, connector name, connector state, attempt,
duration, outcome, and error class. Query strings, document content,
credentials, authorization headers, signed URLs, and tokens are excluded.

## Required metrics

- HTTP request count, latency, status, and in-flight count
- queued, leased, completed, failed, cancelled, and dead-letter jobs
- oldest queued job age and lease expirations
- connector requests, outcomes, latency, retries, throttling, and circuit state
- documents acquired, denied, quarantined, parsed, and deduplicated
- evidence events accepted, rejected, disputed, and orphaned
- graph projection delay and rejected graph writes
- storage bytes by tenant and access class
- model calls, token usage, cost budget, and validation failures

Metric labels must be bounded. Never use document IDs, URLs, queries, patent
numbers, DOIs, user-provided text, or raw error messages as metric labels.

## Audit events

Security-relevant events are immutable and include connector enable/disable,
credential creation/rotation/revocation, terms approval, role changes,
restricted-object access, export, deletion request, retention action, evidence
validation, graph acceptance, and administrative override.

Operational logs are not the evidence ledger. Evidence history and security
audit history have independent retention and integrity controls.
