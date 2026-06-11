# ci-triage

Classify a failed CI run before a human reads raw logs. Wired to the `ci`
workflow via `workflow_run`: every red pipeline gets a job summary naming the
failure category, a likely owner and a suggested first action.

```bash
# against a failed run (gh CLI authenticated)
uv run --project aiops/ci-triage ci-triage --repo acr86/paved-road --run-id 123456789

# against any log file
uv run --project aiops/ci-triage ci-triage --log-file build.log --format json
```

## Design: rules first, LLM assisted

Failure classification is mostly a pattern-matching problem, and pattern
matching wants determinism: the same log must classify the same way, the
rules must be reviewable in a diff, and the classifier must run in airgapped
CI without secrets. So the taxonomy is ordered regex rules
([rules.py](src/ci_triage/rules.py)), unit-tested against committed log
fixtures — when a new failure mode appears, the fix is a fixture plus a rule,
and the test suite guarantees it never regresses.

The LLM layer is strictly additive: when `ANTHROPIC_API_KEY` is configured it
writes a short root-cause hypothesis from the evidence lines. It never
overrides a rule, and the tool's exit code and category never depend on it.

| Category | Typical trigger | Routed to |
|---|---|---|
| vulnerability-gate | Trivy CRITICAL/HIGH gate | service owner |
| policy-violation | conftest deny / checkov | change author |
| test-failure | pytest assertion | change author |
| dependency-resolution | resolver conflict | change author |
| docker-build | Dockerfile/build error | change author |
| kubernetes-rollout | ImagePullBackOff, rollout timeout | platform team |
| infra-flake | network resets, DNS, 503s | platform team (retry first) |
| timeout | job time budget exceeded | author or platform |
| lint | formatter/linter | change author |
| unclassified | nothing matched | human + add a rule |
