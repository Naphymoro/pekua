#!/usr/bin/env sh
set -eu

: "${PEKUA_BASE_URL:?Set PEKUA_BASE_URL to the deployment under test}"

curl --fail --silent --show-error "${PEKUA_BASE_URL%/}/health/live" >/dev/null
curl --fail --silent --show-error "${PEKUA_BASE_URL%/}/health/ready" >/dev/null
curl --fail --silent --show-error "${PEKUA_BASE_URL%/}/openapi.json" >/dev/null

echo "Pekua smoke test passed for ${PEKUA_BASE_URL%/}"
