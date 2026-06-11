# RB-003: Roll back a bad release

**Alert:** invoked from RB-002 (`FxRatesFastBurn`) or from `ArgoAppDegraded` / `ArgoAppOutOfSyncTooLong` when the degradation is deploy-correlated.

**Severity:** page (executed under page conditions; the procedure itself is low-risk)

This runbook is short on purpose. Releases promote by digest — `release.yml` retags the PR-tested digest, it never rebuilds — so rolling back is moving a tag pointer back to a digest that already passed CI, Trivy, and policy gates. There is no rebuild, no new artifact, no untested code path involved.

## Symptoms

- RB-002 concluded the burn is deploy-correlated, or an ArgoCD Application went Degraded right after a promotion.

## Triage

1. Confirm which deploy you are undoing:

       gh run list --workflow release.yml --limit 5
       git log -1 origin/main
       kubectl -n services rollout history deployment/fx-rates

2. Identify the previous good image digest and verify its provenance — every promoted digest is keyless-signed from GitHub Actions OIDC:

       crane ls ghcr.io/acr86/paved-road/fx-rates
       cosign verify ghcr.io/acr86/paved-road/fx-rates@sha256:<previous> \
         --certificate-identity-regexp 'github.com/Acr86/paved-road' \
         --certificate-oidc-issuer https://token.actions.githubusercontent.com

## Resolution

Path A — GitOps history (fast, not durable):

    argocd app history svc-fx-rates
    argocd app rollback svc-fx-rates <ID>

Caveat: the services ApplicationSet runs auto-sync with self-heal, so ArgoCD will fight a manual rollback and converge back to the desired state in git. Use Path A only to stop the bleeding while you execute Path B.

Path B — move the desired state (durable):

    crane ls ghcr.io/acr86/paved-road/fx-rates
    crane tag ghcr.io/acr86/paved-road/fx-rates@sha256:<previous> main
    kubectl -n services rollout restart deployment/fx-rates

The retag moves what `main` means; the restart makes the pods pull it. ArgoCD self-heal keeps everything else converged.

Alternatively, revert in git and let the pipeline re-promote:

    git revert <offending-merge-commit>

`release.yml` re-promotes the now-good digest after CI passes.

Choosing between them: if the code is wrong, prefer `git revert` — history then tells the truth, CI re-tests the reverted state, and the promotion machinery does the rest. If the build or promotion is wrong (the wrong digest got tagged, or you have a supply-chain doubt about the artifact), retag directly to the known-good digest first — it is immediate and skips a CI round-trip — and fix the pipeline afterwards.

## Root causes seen

- Logic regression that passed unit tests but failed under real traffic — reverted in git, re-promoted clean.
- A promotion race where `main` was retagged from a stale workflow run — fixed by retagging to the verified previous digest.

## Automation status

Everything around the rollback is automated: history is in ArgoCD and `crane ls`, provenance is verifiable with one `cosign verify`, and redeploy after the pointer moves is ArgoCD's job. The rollback decision and the tag move themselves are manual by design — a human chooses which digest the fleet runs, and promote-by-digest keeps that choice to three commands.
