# Service level objectives

## Why SLOs

A target below 100% is what makes reliability negotiable instead of absolute: the gap between the objective and perfection is an error budget you are allowed to spend. That budget is the shared currency between shipping and reliability — while budget remains, deploys and risky changes proceed without ceremony; when it is exhausted, the priority flips to reliability work and nobody has to argue about it case by case. It also fixes alerting: we alert on the rate the budget is being spent, not on raw error counts, which is why a single bad minute wakes nobody. The numbers below are deliberately modest for a reference platform; the mechanics are the point.

## fx-rates

| SLI | Definition | SLO target | Window |
| --- | --- | --- | --- |
| Availability | Proportion of requests that do not return 5xx. Error ratio: `sum(rate(http_requests_total{service="fx-rates", status=~"5.."}[5m])) / sum(rate(http_requests_total{service="fx-rates"}[5m]))` | 99.5% | 30 days, rolling |
| Latency | 95th percentile request duration: `histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{service="fx-rates"}[5m])))` | p95 < 300ms | 30 days, rolling |

The budget math. 99.5% over 30 days leaves 0.5% of requests to fail — in time terms, 0.005 × 30 days × 24 hours = 3.6 hours, or 3h36m of full outage per month. Burn rate is the multiple of sustainable spend: at exactly 1x you run out of budget on the last day of the window.

| Burn rate | Budget exhausted in |
| --- | --- |
| 1x | 30 days |
| 6x | 5 days |
| 14.4x | 50 hours |

## Alerting on burn rate

Two burn-rate alerts on the availability SLO live in [slo-burn-rate.yaml](../observability/alerts/slo-burn-rate.yaml):

- `FxRatesFastBurn` — error ratio above 14.4 × 0.005 on both the 5m and the 1h window, sustained for 2m, severity `page`. A 14.4x burn means 2% of the monthly budget disappears in a single hour; that justifies waking someone.
- `FxRatesSlowBurn` — above 6 × 0.005 on both the 30m and the 6h window, sustained for 15m, severity `ticket`. Sustained, the budget is gone in five days; that is a working-hours problem, not a 3am one.

Each alert ANDs a short and a long window, and both must agree. The short window detects quickly and — just as important — clears quickly once the burn stops; the long window establishes that the spend is real. A thirty-second blip trips the short window only and never fires; a genuine burn trips both. That combination is what lets the thresholds stay aggressive without becoming noisy.

The same file carries `FxRatesP95LatencyHigh` (p95 > 300ms for 10m, ticket) — a plain threshold rather than a burn rate, because a quantile is not a ratio you can budget cleanly. Every alert links its runbook via `runbook_url`, here [rb-002-fast-burn-slo.md](runbooks/rb-002-fast-burn-slo.md). The reasoning for two alerts instead of a full multiwindow ladder is recorded in ADR-0010.

## Platform SLOs

The platform is a product too, so it gets objectives — measured honestly rather than precisely.

Preview reclaim: an expired or orphaned preview namespace is reclaimed within 30 minutes. The janitor CronJob runs every 15 minutes in `platform-system`, so 30 minutes is one interval plus headroom for a missed or slow run. Measurement is indirect: `kube_job` success/failure metrics for the janitor jobs in `platform-system`, plus namespace age against the `pavedroad.dev/expires-at` label. The alert covers the proxy, not the SLI itself — `PreviewJanitorFailing` in [platform.yaml](../observability/alerts/platform.yaml) opens a ticket after 15 minutes of failing runs ([rb-001-preview-not-collected.md](runbooks/rb-001-preview-not-collected.md)). A per-namespace reclaim-latency histogram would be more truthful; it is not built.

Golden-path lead time: scaffold to serving locally in under 10 minutes. `make demo` is the executable proof — scaffold `demo-ledger`, run its tests, validate the catalog, build, deploy, curl. The measurement is the duration of the `e2e-bootstrap` CI job on every run. There is no alert: a regression shows up as a slower job that a human notices in review, not a page.

Plainly: the janitor objective has alerting today; lead time is measured but unalerted. Saying so beats pretending both are equally instrumented.

## What is deliberately missing

No multi-service SLO rollups — with one demo service there is nothing to roll up, and a synthetic aggregate would teach the wrong lesson. No SLO-as-code generator: the rules in [slo-burn-rate.yaml](../observability/alerts/slo-burn-rate.yaml) are handwritten and commented; past a handful of services, sloth is the right tool and that file becomes its output. No latency SLO on the platform's own API surfaces (Argo CD, the catalog page) — they are internal and low-traffic, and an objective nobody would act on is decoration. The scope cuts are recorded in ADR-0013.
