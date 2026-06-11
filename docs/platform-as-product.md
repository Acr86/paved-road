# Platform as a product

Paved Road is built the way a product team would build it: it has customers with jobs to be done, a
paved road whose friction is deliberately measured, metrics that say whether the platform is
working, and feedback loops that change the product when it fights its users. This document is the
product spec behind the engineering.

## Customers

**The application developer** — "I need a service in production, not a Kubernetes education."
They touch exactly four things: `platform new service` to scaffold, the PR loop (path-filtered CI
runs only their service), the `preview` label when they want a live environment, and a Grafana
dashboard that already knows about their service. They never open an ArgoCD config: the
[services ApplicationSet](../deploy/argocd/apps/applicationset-services.yaml) discovers the merged
overlay, and the kube-prometheus-stack scrape config maps `app.kubernetes.io/name` to the `service`
label, so the [golden-signals dashboard](../observability/dashboards/service-golden-signals.json)
works on day one. The hardened Dockerfile, probes, resource limits, and catalog entry are decisions
the platform already made for them.

**The platform engineer** — "I change shared machinery without breaking ten teams." Their surface
is the [Copier template](../templates/fastapi-service/), the
[Rego policies](../policy/kubernetes/), and the ADRs that record why each decision was made.
The blast-radius controls are structural: scaffolds render from committed template state (never a
dirty working tree), `copier update` propagates template evolution per service as a reviewable
diff rather than a forced flag-day, and every policy rule ships with `conftest verify` unit tests
so a tightened control fails in the policy repo's own CI before it fails ten service pipelines.

**The reviewer or auditor** — "show me evidence, not promises." They get artifacts, not
assertions: cosign keyless signatures and syft SBOMs produced by
[release.yml](../.github/workflows/release.yml), Trivy and conftest gates that fail closed in
[ci.yml](../.github/workflows/ci.yml), a capability map from the catalog (`platform catalog
render`), and a [runbook](runbooks/) linked from every alert via `runbook_url`. If a control
matters, there is a pipeline that enforces it and a file that proves it ran.

## The golden path, measured

| Step | What the developer does | What the platform does | Friction removed |
|---|---|---|---|
| Scaffold | `platform new service payments --owner team-x --tier t2` | Renders service code, hardened manifests, and the catalog entry in one pass | No registration step; merging the directory is the deployment — the ApplicationSet needs zero edits |
| First PR | Opens a PR | Path-filtered CI lints, tests, builds, and Trivy-scans only the changed service; on red, [ci-triage](../aiops/ci-triage/) names the failure class with evidence lines and an owner hint | No whole-repo pipeline tax; no log spelunking to learn it was a CVE gate, not their test |
| Preview | Adds the `preview` label | A complete environment appears at `pr-<N>.<svc>.127.0.0.1.nip.io` with a sticky comment listing image and URL; the namespace is TTL-labelled and janitor-reclaimed | No ticket to ops for a test environment; no forgotten namespaces accruing forever |
| Merge | Clicks merge | The PR-tested digest is promoted by tag — never rebuilt — then signed and SBOM-attached | No "the image we tested is not the image we shipped"; zero release clicks |
| Operate | Opens Grafana | Dashboard templated by the `service` label; [burn-rate alerts](../observability/alerts/slo-burn-rate.yaml) page only on real budget burn, each with a runbook link | No per-service dashboard authoring; no static-threshold alert noise |

## Metrics that matter

The DORA four, with honesty about instrumentation:

- **Deployment frequency** and **lead time for changes** are derivable today from git history plus
  ArgoCD sync events — merge-to-sync is observable without new telemetry.
- **Change failure rate** is not measured yet. It needs incident labels (or revert detection) that
  the platform does not emit; until then any number would be invented.
- **MTTR** is partially covered: ci-triage timestamps time-to-diagnosis for pipeline failures, but
  production MTTR needs the same incident labels as CFR.

Platform-product metrics, which say whether the paved road is actually paved:

- **Time-to-first-deploy for a new service.** `make demo` in the [Makefile](../Makefile) is the
  executable measurement: scaffold, test, validate, build, deploy, curl. If that journey degrades,
  CI's bootstrap job notices before a developer does.
- **Percentage of services on the paved road.** The catalog's template field makes this a
  one-liner over [catalog/](../catalog/) — no survey, no spreadsheet.
- **Preview lead time.** Label to working URL is bounded at roughly five minutes by the PR
  generator's 300-second poll; the sticky comment timestamp makes it auditable per PR.
- **Janitor reclaim compliance**, defined alongside the service SLOs in [slo.md](slo.md): expired
  preview environments must actually be reclaimed, and the safety rules (grace period,
  malformed-TTL refusal) are unit-tested so reclaim never becomes mass deletion.

## Feedback loops

The product improves through three signals. Every `unclassified` result from ci-triage is a
missing taxonomy rule; the fix is a new regex plus a committed log fixture, so the classifier
ratchets toward coverage instead of decaying. Recurring `platform validate` failures on the same
check mean the paved road is fighting its users — either the check is wrong or the template should
make compliance automatic, and either way the template changes, not the developer's habits.
Preview label adoption is the usage metric: if developers stop labelling PRs, the environment is
too slow or not trusted, and that is a product regression even when every pipeline is green.

A platform nobody is forced to use gets adopted by being the easiest correct path — that is the
bar this one is built against.
