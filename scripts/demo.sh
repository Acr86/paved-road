#!/usr/bin/env bash
# The golden path, end to end, against the local cluster:
#   scaffold -> test -> validate -> build -> deploy -> observe
# This script is what the README demo recording runs. Clean up afterwards
# with: make demo-clean
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/infra/local/versions.env"
cd "${ROOT}"

SERVICE="demo-ledger"

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

if [ -d "services/${SERVICE}" ]; then
  echo "services/${SERVICE} already exists — run 'make demo-clean' first" >&2
  exit 1
fi

step "1/6 scaffold a new service from the golden path"
uv run --project platform-cli platform new service "${SERVICE}" \
  --owner team-demo --tier t3 \
  --description "Demo service scaffolded live to walk the golden path end to end."

step "2/6 the generated service's own test suite passes"
(cd "services/${SERVICE}" && uv run --extra dev --project . pytest)

step "3/6 the catalog stays consistent (the same gate CI enforces)"
uv run --project platform-cli platform validate

step "4/6 build and deploy to the local cluster"
bash "${ROOT}/scripts/deploy-local.sh" "${SERVICE}"

step "5/6 the service answers through the platform ingress"
curl -fsS "http://${SERVICE}.127.0.0.1.nip.io:${INGRESS_HTTP_PORT}/healthz"
echo
curl -fsS "http://${SERVICE}.127.0.0.1.nip.io:${INGRESS_HTTP_PORT}/"
echo

step "6/6 it is in the catalog"
uv run --project platform-cli platform list

printf '\nDone. In the real flow this would now be a pull request: CI builds and\n'
printf 'scans the image, the preview label spawns an ephemeral environment, and\n'
printf 'merging promotes the tested digest — no rebuild. Clean up: make demo-clean\n'
