# Pekua connector service

This package provides Pekua's source-access boundary. Connectors cannot issue a
request until the registry has evaluated their access state. Public connectors
use documented machine interfaces; credential and partnership sources are
disabled by default.

The executable discovery adapters cover Crossref, OpenAlex, DataCite, arXiv,
Europe PMC, DOAJ and Zenodo. The source registry also declares the intended
posture for patent, African and licensed sources. A declaration is not evidence
of permission: only `ENABLED` sources with a permitted access class can run.

Unavailable sources expose a precise `activation_state` and `activation_action`:

- `CODE_PENDING`: a documented adapter still needs implementation and contract tests.
- `CREDENTIAL_MISSING`: approved credentials must be added to the vault.
- `AGREEMENT_REQUIRED`: machine access must be approved by the source owner.
- `ENDPOINT_UNVERIFIED`: a documented upstream endpoint or licence must be verified.
- `CONFIGURATION_REQUIRED`: an official data product must be selected and configured.

Search access is distinct from document acquisition. DOAJ and Zenodo return a
`full_text_url` only when an item-level licence is present. Downstream acquisition
must still evaluate that licence before storing content.

Run the isolated test suite with:

```bash
python -m unittest discover -s tests/connectors -v
```
