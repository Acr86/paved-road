# Security

This is a reference platform that runs on a local cluster; it operates no
hosted service and stores no user data. Its security-relevant surface is the
patterns it demonstrates: SHA-pinned actions, least-privilege workflow
permissions, keyless OIDC identity, signed digests with SBOMs, unit-tested
admission policies, and scanners that gate rather than report.

If you find a vulnerability in the code itself — a policy that can be
bypassed, a workflow that leaks a privilege, a janitor rule that deletes the
wrong thing — please report it via
[GitHub security advisories](https://github.com/Acr86/paved-road/security/advisories/new)
rather than a public issue. Threat-model context for the load-bearing
decisions lives in [docs/adr/](docs/adr/), notably 0005 (promotion
integrity), 0006 (CI identity) and 0009 (preview isolation limits).
