# Capability map

This page maps each platform capability to where it lives in the repository
and how to verify it. Status is precise:

- **runnable** — executes in the local platform and is exercised by this
  repository's own CI on every relevant change.
- **blueprint** — the code is validated in CI (terraform fmt/validate, tflint,
  Checkov) but never deployed, by design. See
  [ADR-0002](adr/0002-runnable-core-validated-blueprint.md).
- **design** — the decision is documented in an ADR; no code claims to
  implement it.

| Capability | Where | Status | Verify |
|---|---|---|---|
| Service catalog, validated against reality | [catalog/](../catalog/), [platform-cli](../platform-cli/) | runnable | `make catalog` |
| Golden-path scaffolding (one pass: service + manifests + catalog entry) | [templates/fastapi-service/](../templates/fastapi-service/), [ADR-0007](adr/0007-copier-golden-paths.md) | runnable | `make demo` |
| GitOps delivery (apps appear by existing) | [deploy/argocd/](../deploy/argocd/), [ADR-0004](adr/0004-gitops-argocd-app-of-apps.md) | runnable | `make up && kubectl get applications -n argocd` |
| Change-scoped CI (only what the diff touches runs) | [.github/workflows/ci.yml](../.github/workflows/ci.yml) | runnable | open any PR; check the `changes` job routing |
| Build once, promote by digest (+ keyless signing, SBOM) | [.github/workflows/release.yml](../.github/workflows/release.yml), [ADR-0005](adr/0005-build-once-promote-by-digest.md) | runnable | `cosign verify ghcr.io/acr86/paved-road/fx-rates:main ...` |
| Ephemeral preview environments per PR, TTL + orphan GC | [deploy/argocd/apps/applicationset-previews.yaml](../deploy/argocd/apps/applicationset-previews.yaml), [ADR-0009](adr/0009-previews-applicationset-ttl-janitor.md) | runnable | label a PR `preview`; offline: `make preview PR=123` |
| Policy-as-code on every rendered manifest (policies unit-tested) | [policy/kubernetes/](../policy/kubernetes/) | runnable | `conftest verify --policy policy/kubernetes` |
| Vulnerability gates on every image | [reusable-service-ci.yml](../.github/workflows/reusable-service-ci.yml) | runnable | any PR touching a service |
| SLOs and multi-window burn-rate alerting | [observability/alerts/](../observability/alerts/), [docs/slo.md](slo.md), [ADR-0010](adr/0010-burn-rate-slo-alerting.md) | runnable | `make up`; alerts load in Prometheus |
| Dashboards as code (sidecar-loaded) | [observability/dashboards/](../observability/dashboards/) | runnable | Grafana at `grafana.127.0.0.1.nip.io:8080` |
| CI failure triage (rules-first, LLM-assisted) | [aiops/ci-triage/](../aiops/ci-triage/) | runnable | `uv run --project aiops/ci-triage ci-triage --log-file aiops/ci-triage/tests/fixtures/pytest-failure.log` |
| Multi-cloud IaC: GCP + AWS mirrored module contracts | [infra/terraform/](../infra/terraform/), [ADR-0011](adr/0011-provider-neutral-contracts-aws-gcp.md) | blueprint | `make tf-validate` |
| Keyless CI→cloud identity (OIDC, no stored keys) | [modules/gcp/cicd-identity](../infra/terraform/modules/gcp/cicd-identity/), [modules/aws/cicd-identity](../infra/terraform/modules/aws/cicd-identity/), [ADR-0006](adr/0006-keyless-oidc-cicd.md) | blueprint | `make tf-validate` |
| Drift detection (nightly plan, exit-code 2 = red) | [.github/workflows/drift.yml](../.github/workflows/drift.yml) | blueprint | read the workflow; armed by `ENABLE_CLOUD` |
| Audit log archive with WORM retention | [modules/aws/audit-log-sink](../infra/terraform/modules/aws/audit-log-sink/), [modules/gcp/audit-log-sink](../infra/terraform/modules/gcp/audit-log-sink/) | blueprint | `make tf-validate` |
| Progressive delivery (canary / blue-green decision matrix) | [ADR-0013](adr/0013-scope-boundaries.md) | design | read the ADR |
| Backstage migration path | [docs/backstage-migration.md](backstage-migration.md), [ADR-0008](adr/0008-catalog-cli-now-backstage-later.md) | design | read the mapping |
| Log aggregation pipeline | [ADR-0013](adr/0013-scope-boundaries.md) (services already emit single-line JSON) | design | read the ADR |

Anything this repository claims, one of these commands or files verifies.
If a claim cannot be verified here, treat it as a bug in the documentation
and [open an issue](https://github.com/Acr86/paved-road/issues).
