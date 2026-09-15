# Pekua security threat model

## Scope and trust boundaries

Pekua processes untrusted publications, preprints, patents, metadata, URLs, files and model outputs. Its principal boundaries are: browser to API; API to orchestrator; orchestrator to connector worker; worker to external source; worker to object storage; extraction sandbox to evidence ledger; ledger to validator; and tenant to tenant. The credential vault and append-only audit trail are separate high-value security domains.

## Protected assets

- API credentials, OAuth tokens and institutional entitlements
- Tenant-restricted documents and derived content
- Original documents, checksums and provenance
- Evidence-ledger history and validator decisions
- Connector policy, licence state and enablement controls
- User identity, roles and audit history

## Primary threats and required controls

| Threat | Required control | Verification |
|---|---|---|
| Cross-tenant data access | Tenant key on every resource, deny on mismatch, database row policies where supported | Negative integration tests |
| Credential disclosure | External vault in production, encrypted development vault, reference-only records, log redaction | Secret scanning and redaction tests |
| Prompt injection in documents | Treat documents as data, escape and delimit evidence, block tool use from retrieved text, validate model outputs | Adversarial corpus tests |
| Connector SSRF | Source allowlists, DNS/IP checks, redirect limits, private-address rejection | SSRF test suite |
| Malicious documents | MIME and size validation, malware scan, sandboxed parsing, CPU/memory/time limits | Parser isolation tests |
| Licence violation | Fail-closed licence gate before download, storage, extraction and sharing | Policy tests and audit inspection |
| Privilege escalation | Explicit RBAC grants, short-lived identity, separate connector administration | Authorization tests |
| Audit tampering | Append-only sink, restricted writer identity, integrity/retention controls | Storage policy and recovery test |
| Schema drift poisoning | Contract validation and connector quarantine | Fixture and drift tests |
| Duplicate/replay jobs | Idempotency keys, signed task identity and ledger uniqueness constraints | Orchestration integration tests |
| Dependency compromise | Locked dependencies, SBOM, signature/provenance checks and routine scans | CI security job |
| Data exfiltration by models | No credentials in prompts, scoped retrieval, output validation, egress controls | Canary and policy tests |

## Credential lifecycle

Production must inject an implementation of `ExternalSecretVault` backed by an approved managed secret service or Vault deployment. Connector records store opaque secret references only. Access is tenant-scoped, audited and limited to connector workers. Rotation creates a new version; revocation disables the previous reference. Secrets must not be accepted in query parameters, returned by APIs, included in task payloads, or written to evidence or graph stores.

The local `EnvEncryptedVault` exists only for development. It uses AES-256-GCM, authenticates tenant, connector and version as associated data, refuses plaintext fallback, and requires its key outside the repository.

## Content safety contract

Retrieved text has no authority. It may supply evidence but cannot change system policy, request secrets, select tools or authorize network access. Extraction workers emit typed records. The orchestration layer selects tools from connector policy, never from document text. Flagged content is quarantined or sent for review. Graph writes require schema validation, provenance and the configured validation threshold.

## Known deployment obligations

Before public production use, configure HTTPS, managed identity, external secret storage, database row policies, object-store tenant prefixes and policies, immutable audit retention, backups, malware scanning, restricted worker egress, rate limiting, dependency scanning and incident alerts. EPO OPS and licensed WIPO connectors remain disabled until credentials and agreements are validated. ARIPO, OAPI, CIPC and AJOL remain partnership-required unless documented machine access is approved.
