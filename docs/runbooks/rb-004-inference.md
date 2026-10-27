# RB-004: inference service degraded

**Alerts:** `InferenceNoModelLoaded` (page), `InferenceP95LatencyHigh` (ticket), `InferenceBatchesAtLimit` (ticket) — defined once in [inference.yaml](../../observability/alerts/inference.yaml) for every service on the `inference-service` golden path. The `service` label on the alert names which one.

## InferenceNoModelLoaded

**Meaning:** no scraped replica of the service has a model in memory. Readiness is gated on the model, so the Service has no endpoints and every request fails.

1. Look at the pods — the state tells you which phase failed:

       kubectl -n services get pods -l app.kubernetes.io/name=<service>
       kubectl -n services describe pod -l app.kubernetes.io/name=<service>

   - `CrashLoopBackOff` — the model failed to load and the process exited on purpose (a half-loaded pod never serves). Read the reason: `kubectl -n services logs deploy/<service> --previous`. Typical causes: unknown `MODEL_BACKEND`, missing weights in `MODEL_CACHE_DIR`, OOM while loading (check `Last State: OOMKilled` in `describe`).
   - `Running` but `0/1 READY`, restarted by the startupProbe — the load takes longer than the 150s startup budget. Either the model grew or the node is slower; raise `failureThreshold` on the startupProbe, never the liveness probe.
   - `Pending` — the scheduler cannot place it. For the `gpu` overlay this almost always means no node satisfies the `pavedroad.dev/accelerator` selector or no GPU is free.
2. If the failure started right after a promotion, roll back per [RB-003](rb-003-rollback.md) — a model or config change is a deploy like any other.
3. Confirm recovery: `inference_model_loaded` returns to 1 and `/readyz` answers 200.

## InferenceP95LatencyHigh

**Meaning:** time spent inside the model or index (HTTP overhead excluded) has p95 above 500ms for 10 minutes.

1. Check whether batches grew: compare `inference_batch_size` with the latency increase — bigger batches legitimately take longer per call.
2. Check CPU throttling against the container limit; model inference is CPU-bound on the default backend:

       kubectl -n services top pod -l app.kubernetes.io/name=<service>

3. Check index size (`inference_index_vectors`). The default index is exact brute-force search; latency grows linearly with it. Past tens of thousands of vectors, swap to an approximate index (FAISS IVF/HNSW) as the template README describes.
4. Correlate with the last promotion — a new model version is the most common cause of a latency step change.

## InferenceBatchesAtLimit

**Meaning:** p95 of request batch sizes has sat at the service's batch ceiling (`MAX_BATCH`, exported as `inference_max_batch`) for an hour. Clients are splitting work into more round trips than they want.

This is capacity planning, not an incident: decide with the owning team whether to raise `MAX_BATCH` (and the memory limit with it) or to keep the ceiling and have clients batch differently. Record the decision in the service README.
