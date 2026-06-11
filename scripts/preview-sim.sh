#!/usr/bin/env bash
# Offline preview-environment simulation: render and apply every service's
# preview overlay into a TTL-labelled pr-<N> namespace WITHOUT opening a pull
# request. The real path is the ApplicationSet pull-request generator; this
# lets a reviewer see the mechanics without GitHub in the loop.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PR="${1:?usage: preview-sim.sh <pr-number> [ttl-seconds]}"
TTL="${2:-7200}"
NS="pr-${PR}"

command -v kubectl >/dev/null 2>&1 || { echo "kubectl is required" >&2; exit 1; }

echo "==> creating TTL-labelled namespace ${NS} (ttl ${TTL}s)"
(cd "${ROOT}" && uv run --project platform-cli platform preview create --pr "${PR}" --ttl-seconds "${TTL}")

for overlay in "${ROOT}"/deploy/kustomize/services/*/overlays/preview; do
  service="$(basename "$(dirname "$(dirname "${overlay}")")")"
  echo "==> applying ${service} preview overlay into ${NS}"
  kubectl apply -k "${overlay}" -n "${NS}"
done

echo
echo "Simulated preview is converging. Note: simulated previews keep the"
echo "default preview host (the ApplicationSet patches per-PR hosts):"
for overlay in "${ROOT}"/deploy/kustomize/services/*/overlays/preview; do
  service="$(basename "$(dirname "$(dirname "${overlay}")")")"
  echo "  http://preview.${service}.127.0.0.1.nip.io:8080/"
done
echo
echo "It will be garbage-collected by the janitor after the TTL, or sooner with:"
echo "  uv run --project platform-cli platform preview gc"
