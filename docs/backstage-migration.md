# Migrating the catalog to Backstage

## Position

The catalog format is deliberately Backstage-shaped ([ADR-0008](adr/0008-catalog-cli-now-backstage-later.md)).
Every field in `catalog/<name>.yaml` has a one-to-one home in a Backstage Component entity, so
the migration is a mechanical export, not a remodel. We run it when the triggers in the ADR fire
— multiple teams, entity search at scale, an RBAC'd UI — and not before.

One thing does not migrate: the validation gate. `platform validate` enforces invariants Backstage
does not (tier t1/t2 requires a runbook that exists on disk, a service directory without a catalog
entry fails, an entry without deploy manifests "would never deploy"). After migration Backstage is
a view over the catalog; this repo's `validate` in CI remains the source of truth, and the exporter
runs after it so Backstage never ingests an entry that failed the gate.

## Field mapping

| `catalog/<name>.yaml` | Backstage entity |
| --- | --- |
| `name` | `metadata.name` |
| `description` | `metadata.description` |
| `kind: service` | `kind: Component`, `spec.type: service` |
| `kind: tool` | `kind: Component`, `spec.type: tool` |
| `kind: system` | `kind: System` |
| `owner` | `spec.owner: group:<owner>` |
| `lifecycle` | `spec.lifecycle` |
| `tier` | `metadata.labels["pavedroad.dev/tier"]` |
| `language` | `metadata.tags` |
| `template` | `metadata.annotations["pavedroad.dev/scaffolded-from"]` |
| `links.runbook` / `links.dashboard` / `links.source` | `metadata.links` (with `docs`/`dashboard`/`code` icons); `source` additionally as `backstage.io/source-location` |

Our link values are repo-relative paths checked against the working tree by `validate`; the
exporter absolutizes them into GitHub URLs. Worked example, [`catalog/fx-rates.yaml`](../catalog/fx-rates.yaml):

```yaml
name: fx-rates
kind: service
owner: team-markets
description: "Reference FX quotes service: serves indicative exchange rates with golden-signal metrics."
tier: t2
lifecycle: production
language: python
template: fastapi-service
links:
  runbook: docs/runbooks/rb-002-fast-burn-slo.md
  dashboard: http://grafana.127.0.0.1.nip.io:8080/d/service-golden-signals
  source: services/fx-rates
```

becomes:

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: fx-rates
  description: "Reference FX quotes service: serves indicative exchange rates with golden-signal metrics."
  labels:
    pavedroad.dev/tier: t2
  tags:
    - python
  annotations:
    pavedroad.dev/scaffolded-from: fastapi-service
    backstage.io/source-location: url:https://github.com/Acr86/paved-road/tree/main/services/fx-rates
  links:
    - url: https://github.com/Acr86/paved-road/blob/main/docs/runbooks/rb-002-fast-burn-slo.md
      title: Runbook
      icon: docs
    - url: http://grafana.127.0.0.1.nip.io:8080/d/service-golden-signals
      title: Dashboard
      icon: dashboard
    - url: https://github.com/Acr86/paved-road/tree/main/services/fx-rates
      title: Source
      icon: code
spec:
  type: service
  owner: group:team-markets
  lifecycle: production
```

## Scaffolder mapping

[`templates/fastapi-service`](../templates/fastapi-service/copier.yml) is a Copier template; the
Backstage scaffolder renders nunjucks via `fetch:template` actions. Two options:

(a) Wrap Copier in a custom scaffolder action — recommended. The action shells out to
`copier copy` with the same arguments the CLI uses, including `vcs_ref=HEAD` so scaffolds render
from committed template state. Provenance survives: `.copier-answers.yml` lands in the service and
`copier update` keeps propagating template evolution to existing services.

(b) Port the template to nunjucks. This buys native scaffolder rendering and costs `copier update`
permanently — every existing service is orphaned from template evolution. Not worth it.

Either way, the one-pass render (service source, kustomize manifests, catalog entry) maps to a
multi-target fetch step followed by a `publish:github:pull-request` action. The PR then flows
through the same CI: `validate`, the manifest gates, and the ApplicationSet picks it up on merge.

## What Backstage adds, and what it does not replace

Earns its keep: TechDocs co-located with code, search across hundreds of entities, an RBAC'd UI
for non-platform users, and the plugin ecosystem (cost insights, on-call ownership) that a static
HTML page from `platform catalog render` will never grow into.

Does not replace: `platform validate` in CI (Backstage's processors validate shape, not
cross-checks against the repo tree), the ApplicationSets that turn a merged directory into a
running service, or the preview janitor. Backstage displays; this repo still decides and deploys.

## Migration plan

1. Generate `catalog-info.yaml` from `catalog/*.yaml` with a ~50-line converter in platform-cli
   (`platform catalog export --backstage`), unit-tested against the table above — half a day.
2. Add the export to CI after `platform validate`, committing generated entities to a
   `catalog-info/` directory so Backstage only ever sees validated entries — a couple of hours.
3. Stand up Backstage with the GitHub discovery provider pointed at that directory, read-only,
   no scaffolder — one day including auth.
4. Build the Copier scaffolder action and a Software Template that fronts
   `platform new service` — two to three days; this is the bulk of the work.
5. Deprecate `platform catalog render` once teams use Backstage daily; keep `validate` and the
   exporter permanently — half a day plus a deprecation window.
