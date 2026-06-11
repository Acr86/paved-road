#!/usr/bin/env bash
# Bring up the local platform: k3d cluster + Argo CD + the root application.
# Idempotent: safe to re-run; existing pieces are left alone.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/infra/local/versions.env"

say() { printf '\n==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

say "checking prerequisites"
for tool in docker k3d kubectl; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required (see README: Run it in five minutes)"
done
docker info >/dev/null 2>&1 || die "docker daemon is not running"

if k3d cluster list 2>/dev/null | grep -q "^${CLUSTER_NAME}\b"; then
  say "cluster '${CLUSTER_NAME}' already exists — reusing it"
else
  say "creating k3d cluster '${CLUSTER_NAME}' (${K3S_IMAGE})"
  k3d cluster create --config "${ROOT}/infra/local/k3d-config.yaml"
fi

kubectl config use-context "k3d-${CLUSTER_NAME}" >/dev/null

if kubectl get namespace argocd >/dev/null 2>&1; then
  say "argocd namespace already exists — skipping install"
else
  say "installing Argo CD ${ARGOCD_VERSION}"
  kubectl create namespace argocd
  kubectl apply -n argocd \
    -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml" \
    >/dev/null
fi

say "waiting for Argo CD to become ready (this is the slow part)"
kubectl -n argocd rollout status deployment/argocd-repo-server --timeout=300s
kubectl -n argocd rollout status deployment/argocd-server --timeout=300s

say "applying the root application (app-of-apps)"
kubectl apply -f "${ROOT}/deploy/argocd/root-app.yaml"

say "done"
cat <<EOF

The platform is converging. Useful entry points:

  watch the apps     kubectl get applications -n argocd -w
  fx-rates           http://fx-rates.127.0.0.1.nip.io:${INGRESS_HTTP_PORT}/rates
  argocd UI          kubectl -n argocd port-forward svc/argocd-server 8443:443
                     (user: admin — password: make argocd-password)
  grafana            http://grafana.127.0.0.1.nip.io:${INGRESS_HTTP_PORT}
                     (user: admin — password: make grafana-password)

First sync pulls images from ghcr.io and can take a few minutes.
Tear everything down with: make down
EOF
