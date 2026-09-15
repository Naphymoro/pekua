# Persistence and evidence contract

Pekua stores bibliographic metadata separately from acquired objects. `documents.access_scope`
and every `document_objects.access_scope` are authoritative. Restricted or tenant objects use
keys under `tenants/{tenant_id}/`; public objects use `public/`. Callers must never expose an
object-store key as an unauthorised download URL.

## Evidence lifecycle

1. Create one `evidence_streams` row for a document version.
2. Append extraction, claim, review, contradiction and supersession events through
   `EvidenceLedger.append` in the same transaction as related state changes.
3. Link graph facts only to claims accepted by the validation policy using `graph_evidence`.
4. Verify a stream using `verify_chain`. Events cannot be updated or deleted; the database
   trigger enforces this independently of application code.

Corrections are new events. They reference the superseded claim or event in their payload.
Document versions are separate rows under the `(source_id, canonical_id, version)` constraint.

## Operations

Run `alembic upgrade head` before starting workers. Database health is `Database.healthy()`.
Object-store health is `S3ObjectStore.healthy()`. Backup PostgreSQL and the object bucket as one
recovery set, then verify representative evidence chains after restoration.

Object deletion is a governed retention operation. Delete the object through `ObjectStore`, set
`document_objects.deleted_at`, and append a deletion event. Do not delete the document metadata
or evidence history unless a legally reviewed erasure procedure specifically requires it.
