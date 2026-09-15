# Pekua connector service

This package provides Pekua's source-access boundary. Connectors cannot issue a
request until the registry has evaluated their access state. Public connectors
use documented machine interfaces; credential and partnership sources are
disabled by default.

The initial executable adapters cover Crossref, OpenAlex, DataCite, arXiv and
Europe PMC. The source registry also declares the intended posture for patent,
African and licensed sources. A declaration is not evidence of permission: only
`ENABLED` sources with a permitted access class can run.

Run the isolated test suite with:

```bash
python -m unittest discover -s tests/connectors -v
```
