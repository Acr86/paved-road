# RB-001: Preview environment not collected

**Alert:** `PreviewJanitorFailing` (janitor jobs failing in `platform-system`), or a human notices a `pr-<N>` namespace alive after its pull request closed.

**Severity:** ticket

## Symptoms

- A `pr-<N>` namespace exists although the PR is merged or closed.
- `PreviewJanitorFailing` is firing, meaning `kube_job_status_failed` is non-zero for `preview-janitor` jobs.
- Preview namespaces accumulate over days instead of disappearing within one janitor interval (15 min) plus grace.

## Triage

1. See what the platform thinks exists and whether the TTL already passed:

       platform preview list

   A namespace shown as `expired` should have been reaped on the next janitor run.
2. Check the janitor itself:

       kubectl -n platform-system get cronjob,jobs

   `preview-janitor` runs every 15 minutes with `concurrencyPolicy: Forbid`. Failed jobs here confirm the alert; no recent jobs at all means the CronJob is suspended or the controller never scheduled it.
3. Read the most recent job's logs:

       kubectl -n platform-system get jobs --sort-by=.metadata.creationTimestamp
       kubectl -n platform-system logs job/<most-recent-job>

4. Look for the warning `has a missing or malformed pavedroad.dev/expires-at label — refusing to touch it`. This is a safety, not a bug: the janitor never deletes a namespace whose deadline it cannot parse. If your surviving namespace is in that list, the label is the problem, not the janitor.
5. Verify the orphan rule's precondition — the ArgoCD Application must be gone:

       kubectl get applications -n argocd | grep pr-

   Previews are named `pr-<N>-<service>`. If the Application still exists, the PR generator still sees the PR as open and labelled `preview`; the janitor is correct to keep the namespace.
6. If janitor pods never start, check whether `ghcr.io/acr86/paved-road/platform-cli:main` is pullable:

       kubectl -n platform-system get pods
       docker pull ghcr.io/acr86/paved-road/platform-cli:main

   `ImagePullBackOff` on the janitor pod points at the image, not the rules.

## Resolution

- Targeted manual reap, after a dry run:

      platform preview gc --orphans --dry-run
      platform preview gc --orphans

  or, for a single namespace the janitor refuses to touch:

      kubectl delete namespace pr-<N>

- For a malformed deadline you want the janitor to handle instead, repair the label and let the next run collect it:

      kubectl label namespace pr-<N> pavedroad.dev/expires-at=<unix-epoch> --overwrite

- If the image was the cause, fix the publish path (release.yml pushes `platform-cli:main`) and let the next scheduled run proceed.

## Root causes seen

- CLI image not yet published: a fresh cluster bootstrap referenced `platform-cli:main` before the first `release.yml` run had pushed it (ordering, resolves itself after the first merge to main).
- RBAC drift on the `preview-janitor` ClusterRole — the janitor could list namespaces but no longer delete them.
- ArgoCD outage: with the Applications API down, every preview looks orphaned. The 30-minute grace period exists for exactly this; nothing fresh gets mass-deleted during a transient outage.

## Automation status

TTL expiry and orphan reaping are fully automated: the CronJob runs the same unit-tested `platform preview gc --orphans` code path every 15 minutes. The residual human work is namespaces with malformed `pavedroad.dev/expires-at` labels — the janitor reports them and deliberately refuses to delete them, so a person must repair the label or delete the namespace.
