# Service catalog

One YAML file per entry; the file name must equal the entry name. The catalog
is the source of truth for what exists on the platform: GitOps deploys from
it indirectly (a service without manifests fails validation), the portal page
is rendered from it, and `platform validate` cross-checks it against the
repository tree on every push — so it cannot drift and still pass CI.

## Entry shape

```yaml
name: fx-rates              # kebab-case, equals the file name
kind: service               # service | tool | system
owner: team-markets         # owning team, used for routing and review
description: One line that says what this is for.
tier: t2                    # t1 | t2 | t3 — criticality, drives validation:
                            #   t1/t2 require links.runbook, t1 also links.dashboard
lifecycle: production       # experimental | production | deprecated
language: python            # optional
template: fastapi-service   # optional: golden-path provenance
links:                      # optional, all relative to the repo root or absolute
  runbook: docs/runbooks/rb-002-fast-burn-slo.md
  dashboard: http://grafana.127.0.0.1.nip.io:8080/d/service-golden-signals
  source: services/fx-rates
```

Each entry maps mechanically onto a Backstage `catalog-info.yaml` Component —
see [docs/backstage-migration.md](../docs/backstage-migration.md) for the
field-by-field mapping.
