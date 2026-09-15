# Pekua

Pekua is an evidence-first research intelligence platform for scholarly literature,
preprints, patents, African repositories, policy documents, and grey literature.
It retrieves only through documented and authorised access methods, preserves
document-level provenance, and requires validated evidence before graph publication.

## Architecture

- FastAPI control plane and administrative API
- PostgreSQL-backed durable orchestration and append-only evidence ledger
- S3-compatible content-addressable document storage
- Pluggable extraction and citation-validation services
- Provenance graph with an in-memory reference store and optional Neo4j projection
- Typed, access-gated source connector SDK
- Tenant-aware credential vault and policy enforcement
- Docker Compose development and production-reference environment

Restricted connectors such as EPO OPS and credentialed WIPO services remain disabled
until credentials and agreements are configured. ARIPO, OAPI, CIPC, and AJOL are
partnership or documented-machine-access sources and are never scraped by default.

## Local development

Requirements: Python 3.12 and `uv`.

```bash
cp .env.example .env
uv sync --all-extras
uv run pytest
uv run pekua-api
```

OpenAPI documentation is available at `http://localhost:8000/docs`.

## Operating principle

Every graph assertion must resolve to a ledger entry, source record, document version,
and location anchor. Retrieved documents are treated as untrusted input. Public page
visibility is not interpreted as permission for automated acquisition.

See `docs/` for connector governance, security, deployment, and operations guidance.

## Licence

Apache-2.0. Third-party metadata and documents retain their own licences and access
conditions.
