# Pekua production runbook

## Service objectives

| Signal | Target | Page threshold |
|---|---:|---:|
| API availability | 99.9% monthly | unavailable for 2 minutes |
| Search-job success | 99% excluding upstream denials | below 95% for 15 minutes |
| Evidence provenance | 100% of accepted claims | any orphan graph claim |
| Secret disclosure | zero | any occurrence |
| Queue age | below 10 minutes | above 30 minutes |

Upstream `AUTH_REQUIRED`, `LICENSE_REQUIRED`, `PARTNERSHIP_REQUIRED`, and
`RATE_LIMITED` responses are reported separately and are not converted into
successful searches.

## Deployment

1. Create production secrets in the deployment platform. Never commit `.env`.
2. Run `alembic upgrade head` as a one-shot release task.
3. Start the API and one worker. Confirm `/health/live` and `/health/ready`.
4. Run the smoke test against the private deployment.
5. Increase workers gradually while watching queue age, error rate, and each
   source's documented concurrency ceiling.
6. Enable only public connectors whose manifests and compliance checks pass.
7. Record the deployed image digest and migration revision.

The release must fail closed if a required secret is absent. EPO OPS and
licensed WIPO services remain disabled until credentials or agreements are
validated. ARIPO, OAPI, CIPC, and AJOL remain partnership-gated unless
documented machine access has been approved.

## Rollback

1. Pause new job admission.
2. Allow leased jobs to finish or cancel them at a safe checkpoint.
3. Redeploy the last known-good immutable image digest.
4. Do not automatically downgrade the database. Use a forward repair migration.
5. Verify ledger-chain integrity, queue leases, object references, and graph
   projection state before resuming admission.

## Incident response

### Credential exposure

1. Disable the connector and stop affected workers.
2. Revoke and rotate the credential at the source.
3. Search structured logs and traces by connector and time window without
   copying the secret into the search query.
4. Preserve the immutable security audit record.
5. Assess tenant and source scope, notify the authorised owners, and document
   corrective actions before re-enabling.

### Upstream rate limiting or blocking

1. Open the connector circuit breaker.
2. Retain the source's `Retry-After` response and checkpoint.
3. Confirm the manifest's rate and concurrency limits against official terms.
4. Resume with jittered backoff. Do not rotate IP addresses or credentials to
   evade limits.

### Extraction compromise or prompt injection

1. Quarantine the object and all derived records.
2. Stop graph projection for the affected evidence lineage.
3. Preserve the original hash, parser version, and trace identifier.
4. Patch and test the isolated parser, then append corrected evidence events.
5. Never mutate or delete prior ledger events to hide the incident.

### Evidence-chain failure

1. Stop graph writes and place new evidence into a quarantine queue.
2. Run the ledger integrity verifier from the last signed checkpoint.
3. Restore missing objects from versioned storage if necessary.
4. Append repair events. Never rewrite historical ledger rows.

## Backup and recovery

- PostgreSQL: daily encrypted backup plus continuous WAL archival.
- Object storage: versioning, retention policy, and cross-region replication.
- Graph database: reproducible projection from PostgreSQL evidence, with an
  additional snapshot for faster recovery.
- Vault: provider-managed encrypted backup and audited break-glass access.

Quarterly recovery tests must restore into an isolated environment and prove:

1. database migration revision and row counts;
2. evidence hash-chain continuity;
3. object checksum agreement;
4. tenant isolation;
5. graph reconstruction from accepted ledger events;
6. no connector is enabled solely because a secret exists.

## Safe shutdown

Pause admissions, wait for leases to checkpoint, terminate workers, then stop
the API. PostgreSQL and object storage are stopped last. On restart, expired
leases return to the queue through the normal recovery path.
