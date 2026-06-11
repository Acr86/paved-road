#!/usr/bin/env bash
# Inner-loop deploy: build a service image locally, import it into the k3d
# cluster and apply its local overlay — no registry round-trip, no GitOps
# wait. The GitOps path (merge to main -> ArgoCD) is the source of truth;
# this is the fast path for iterating before a commit exists.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/infra/local/versions.env"

SERVICE="${1:?usage: deploy-local.sh <service-name>}"
SERVICE_DIR="${ROOT}/services/${SERVICE}"
OVERLAY="${ROOT}/deploy/kustomize/services/${SERVICE}/overlays/local"
IMAGE="ghcr.io/acr86/andamio/${SERVICE}:main"

[ -d "${SERVICE_DIR}" ] || { echo "error: services/${SERVICE} does not exist" >&2; exit 1; }
[ -d "${OVERLAY}" ] || { echo "error: ${OVERLAY} does not exist" >&2; exit 1; }

echo "==> building ${IMAGE}"
docker build -q -t "${IMAGE}" "${SERVICE_DIR}"

echo "==> importing image into k3d cluster '${CLUSTER_NAME}'"
k3d image import -c "${CLUSTER_NAME}" "${IMAGE}"

echo "==> applying local overlay"
kubectl get namespace services >/dev/null 2>&1 || kubectl create namespace services
kubectl apply -k "${OVERLAY}"
kubectl -n services rollout restart "deployment/${SERVICE}" >/dev/null 2>&1 || true
kubectl -n services rollout status "deployment/${SERVICE}" --timeout=180s

echo "==> ${SERVICE} is live: http://${SERVICE}.127.0.0.1.nip.io:${INGRESS_HTTP_PORT}/"
