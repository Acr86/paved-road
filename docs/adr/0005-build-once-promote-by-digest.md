# 0005. Build once, promote by digest

Date: 2026-06

## Status

Accepted

## Context

The common pattern — build an image in the PR for testing, then build it again on merge to main — has a quiet integrity hole: the bytes that reach an environment are not the bytes that were reviewed, tested, and scanned. A rebuild minutes or days later can resolve different dependency versions, pull a different base-image digest, or run on a drifted toolchain. The Trivy verdict from the PR then describes an artifact that no longer exists, and any incident analysis starts with "what exactly is running?"

For a platform whose CI gates (tests, vulnerability scan, policy checks) are the merge contract, the artifact those gates approved must be the artifact that ships.

## Decision

Images are built and validated exactly once, inside the PR. [reusable-service-ci.yml](../../.github/workflows/reusable-service-ci.yml) runs pytest, builds with buildx, gates on Trivy (fail on CRITICAL/HIGH), and pushes `ghcr.io/acr86/paved-road/<service>:pr-<N>`.

On merge, [release.yml](../../.github/workflows/release.yml) promotes instead of rebuilding: it resolves the digest behind `:pr-<N>` with `crane digest` and re-tags that exact digest as `:main` and `:sha-<short>` — a registry metadata operation, no build. The promoted digest is then signed with cosign (keyless, GitHub OIDC; see ADR 0006) and a syft SBOM is attached as a release artifact. Rollback is the same primitive in reverse: re-point `:main` at a previous known-good digest with `crane tag`, as documented in runbook RB-003 — no pipeline rerun, no rebuild, seconds not minutes.

When no PR image exists (a direct push to main), the workflow falls back to a bootstrap build-and-push, deliberately loud in the logs so the weaker path is never silent.

## Alternatives considered

**Rebuild on main.** The default in most pipelines, and operationally simpler: no registry writes from PRs, no digest plumbing. Rejected on integrity grounds: the deployed bytes are not the reviewed bytes. Even with pinned dependencies, a later rebuild can pull an updated base-image digest or run under a different builder version, and the PR's scan result no longer covers the shipped artifact. It also doubles build cost for zero added confidence.

## Consequences

- PRs must push images. That means registry write access from PR workflows — acceptable for same-repo branches, but fork PRs cannot push to ghcr, so merges of fork contributions take the bootstrap path: the deployed image is built post-merge and never went through the PR-time Trivy gate as the same artifact. For a public reference repo this is a real, accepted weakening; the fallback's visibility in logs is the compensating control.
- Clusters track a moving `:main` tag, not a pinned digest. Git alone cannot tell you which digest is live; the answer lives in the registry (tag history, `sha-<short>` tags) and in the cosign signatures, which are made over digests precisely so the moving tag is auditable after the fact. The stricter alternative — committing digests back to manifests — would add a bot-commit loop this platform deliberately avoids.
- Rollback by re-tagging is fast but happens outside git: RB-003 requires recording the action because the repository will not show it.
- Every PR image occupies registry storage until cleanup; the cost of "build once" is keeping what you built.
