# platform-cli

The `platform` command: golden-path tooling for the paved-road reference platform.

```bash
uv tool install ./platform-cli      # or: uvx --from ./platform-cli platform --help

platform new service fx-rates --owner team-markets --tier t2
platform list
platform validate                   # the same check CI runs on every push
platform preview gc --dry-run
platform catalog render
```

## Design notes

- **One pass, three artifacts.** `platform new service` renders the service
  source tree, its kustomize manifests and its catalog entry from a single
  Copier template. There is no separate registration step to forget.
- **The catalog cannot drift.** `platform validate` cross-checks the catalog
  against the repository tree (service dirs, deploy manifests, runbook links)
  and CI runs it on every push: an inconsistent catalog fails the build.
- **The janitor is this code.** The in-cluster preview garbage collector runs
  this same package, so its deletion rules — including the ones that protect
  namespaces from deletion — are unit-tested without a cluster.

See `tests/` for the golden tests: the template is tested by rendering it and
running the generated service's own test suite.
