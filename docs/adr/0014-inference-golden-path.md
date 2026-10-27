# 0014. A golden path for model-inference services

Date: 2026-10

## Status

Accepted

## Context

Model-serving services fail in ways the `fastapi-service` path does not anticipate, and the failures are well known enough to be designed out once rather than rediscovered per team:

- **Slow loads fight liveness.** Loading weights can take tens of seconds to minutes. With only a liveness probe, the kubelet kills the pod mid-load, it restarts, loads again, and is killed again — a crash loop with no bug in it.
- **"Up" is not "able to answer."** A process that is running but has no model in memory passes a naive health check and returns 500s to every request.
- **Unattributable answers.** When results degrade, the first question is "which model produced this?" If the answer requires reading code or deploy history, incidents take longer than they should.
- **Unbounded requests.** A single request with ten thousand inputs pins a CPU and the heap for everyone sharing the pod. Tail latency for inference is set by the largest request allowed, not the average one.
- **Per-team alerting.** Each team writes its own latency and availability rules, or none, and the platform cannot say which inference services are covered.

A second constraint is specific to this repository: everything on the paved road must run on a laptop and in CI ([ADR-0002](0002-runnable-core-validated-blueprint.md)). A path that only works with a GPU and a multi-gigabyte download is a blueprint, not a golden path.

## Decision

Add an `inference-service` Copier template alongside `fastapi-service`, with the same one-render contract ([ADR-0007](0007-copier-golden-paths.md)) and these platform-level guarantees:

1. **Model lifecycle.** The model loads once in the application lifespan. `/readyz` returns 503 until it is in memory and is the target of both the `startupProbe` (150s budget) and the `readinessProbe`. `/healthz` never touches the model. A failed load exits the process so the failure is visible as `CrashLoopBackOff`, never as a pod that serves errors.
2. **A backend interface, not a model.** The service depends on an `Embedder` protocol resolved by name (`MODEL_BACKEND`). The default `hashing` backend — character n-gram feature hashing with BLAKE2b — is deterministic, CPU-only and has no weights, so the generated service, its tests and the reference service run anywhere and assert exact behavior. A real model (a sentence-transformer, a DINOv2 image encoder exported to ONNX, a hosted API) is one class plus one registry entry; the HTTP surface, probes, guardrails and alerts do not change.
3. **Provenance.** Every inference response carries `X-Model: <name>@<version>`; pods carry a `pavedroad.dev/model` annotation; `inference_model_info` exposes the same identity to Prometheus.
4. **Bounded requests.** Batch size (`MAX_BATCH`), input length and `k` are validated at the schema layer and rejected with 422.
5. **A metrics contract, alerted once.** Services emit `inference_duration_seconds` (model time only), `inference_batch_size`, `inference_model_loaded`, `inference_model_info`, `inference_max_batch` and `inference_index_vectors`. [observability/alerts/inference.yaml](../../observability/alerts/inference.yaml) defines the rules once, grouped `by (service)`, so a newly scaffolded service is covered as soon as it is scraped. Golden tests in `platform-cli` pin the metric names so a rename cannot silently blind the alerts.
6. **Policy, opt-in by label.** Workloads labelled `pavedroad.dev/workload: inference` must declare a startupProbe, a readinessProbe and the model annotation ([policy/kubernetes/workloads.rego](../../policy/kubernetes/workloads.rego)). Plain services are unaffected.
7. **GPU as a validated blueprint.** Each inference service renders an `overlays/gpu` overlay — GPU limit, accelerator node selector, taint toleration, larger memory and cache — that CI renders, schema-checks and policy-checks, but no ApplicationSet deploys.

`services/similarity-search` is the reference service, scaffolded with `platform new service --template inference-service`, exactly like `fx-rates` comes from the HTTP path.

## Alternatives considered

- **A dedicated serving stack (KServe, Triton, Ray Serve).** The right answer for many models, autoscaling to zero, or multi-model GPU sharing. Rejected for the reference path: each adds CRDs, controllers and a control plane to bootstrap, and none runs meaningfully on a single-node laptop cluster. The contract above — lifecycle, probes, provenance, bounded requests, metrics — is what a team needs regardless of stack; adopting one later replaces the container, not the contract.
- **Bake weights into the image.** Simple and reproducible, but couples image size and vulnerability scanning to model size and release cadence, and every model update becomes a multi-gigabyte image push. Rejected in favor of loading into a size-bounded `emptyDir` (`MODEL_CACHE_DIR`), with the image staying small enough to scan on every PR.
- **Default to a small real model.** More realistic, but downloads in CI make tests slow and network-dependent, and floating-point output varies across CPUs, which turns exact assertions into tolerance games. The deterministic default keeps the path's tests exact; realism is one backend away.
- **Approximate nearest-neighbor index (FAISS) by default.** Brute-force cosine is exact and needs no tuning up to tens of thousands of vectors; FAISS is documented as the swap point when `inference_index_vectors` says it is needed.

## Consequences

- Every inference service gets correct probe semantics, bounded requests, provenance and alerting without writing any of it.
- The default backend measures the platform, not model quality. Similarity from feature hashing is lexical; anyone evaluating search relevance needs a real backend first.
- The index is in process memory and lost on restart. That keeps the platform stateless; a production service rebuilds the index from a source of truth at startup or moves it to a dedicated vector store.
- One shared rule file means one shared objective: model-time p95 under 500ms for every inference service. A service that needs a different objective needs its own rule — a per-service SLO generator (sloth) is the scale answer, already noted in [docs/slo.md](../slo.md).
- The GPU overlay is unexercised on real hardware here. It is validated for shape and policy, not for scheduling behavior.
