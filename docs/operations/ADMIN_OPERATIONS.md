# Administrative operations

Administrative controls expose backend truth. They must never display a
simulated health result, secret value, signed object URL, or success state that
has not been recorded by the relevant service.

## Connector registry

For each connector, show access class, execution state, owner, jurisdiction,
approved endpoint, documentation, last terms verification, credential status,
rate and concurrency ceiling, last successful request, current circuit state,
schema version, quarantine reason, and required activation action.

Changing a connector from disabled to enabled requires:

1. connector-administrator permission;
2. an executable access class;
3. current terms review;
4. credential validation where applicable;
5. a passing connector health and schema test;
6. a durable audit event recording the actor, reason, and trace ID.

Possessing a credential alone is not sufficient. EPO OPS and licensed WIPO
services require validated credentials and agreements. ARIPO, OAPI, CIPC, and
AJOL require documented machine access or an approved partnership.

## Job operations

Administrators can pause new admissions, cancel safely at a checkpoint, inspect
attempts, replay a dead-letter once its cause is addressed, and open a connector
circuit. Replays preserve the original job and evidence history. Bulk replay
requires an additional confirmation and a bounded selection.

## Evidence and graph operations

Validation views display source, version, licence, passage anchor, extraction
model, proposed claim, confidence, contradictions, and prior decisions. Accept,
reject, dispute, and supersede actions append events. They do not update or
delete historical evidence.

Graph changes show the accepted evidence IDs supporting every node or edge.
Any orphan projection is a release-blocking incident.

## Restricted data

Document access is scoped to the source licence, tenant, role, and purpose.
Exports apply the same policy as interactive access. Administrative roles do
not automatically grant access to licensed full text.

## Audit review

Review connector changes and failed authorisation weekly. Review credential
rotation, restricted exports, administrative overrides, evidence supersession,
retention actions, and cross-tenant denials monthly. Export audit reports only
to approved protected storage.
