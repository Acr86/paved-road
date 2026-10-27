# similarity-search

Reference inference service: text embeddings and vector search behind the inference golden-path contract.

Owned by **team-platform** · tier **t3** · scaffolded from the `inference-service` golden path
([ADR-0014](../../docs/adr/0014-inference-golden-path.md)).

## Develop

```bash
cd services/similarity-search
uv run --extra dev pytest        # run the test suite
uv run uvicorn app.main:app --reload --port 8000
```

Try it:

```bash
curl -s localhost:8000/v1/index -H 'content-type: application/json' \
  -d '{"items":[{"id":"a","text":"restart the ingress controller"},{"id":"b","text":"rotate database credentials"}]}'
curl -s localhost:8000/v1/search -H 'content-type: application/json' \
  -d '{"query":"ingress restart","k":1}'
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/embeddings` | `{"inputs": [...]}` → one vector per input (≤ 64 inputs) |
| POST | `/v1/index` | `{"items": [{"id", "text"}]}` → embed and upsert into the in-memory index |
| POST | `/v1/search` | `{"query", "k"}` → top-k ids by cosine similarity (1 ≤ k ≤ 50) |

Every inference response carries an `X-Model: <name>@<version>` header, so a
client — and a log line — always knows which model produced the answer.

## Endpoints the platform relies on

| Path | Purpose |
|---|---|
| `/healthz` | liveness — process is up, never depends on the model |
| `/readyz` | readiness **and** startupProbe target — 503 until the model is loaded |
| `/metrics` | HTTP golden signals plus the inference contract metrics |

The inference metrics (`inference_duration_seconds`, `inference_batch_size`,
`inference_model_loaded`, `inference_model_info`, `inference_max_batch`, `inference_index_vectors`)
are what [observability/alerts/inference.yaml](../../observability/alerts/inference.yaml)
selects on. Keep the names; the alerts depend on them.

## Swapping in a real model

The backend is chosen by `MODEL_BACKEND` from the registry in `src/app/embedder.py`.
The default, `hashing`, is deterministic and CPU-only so this service runs on a
laptop and in CI. To serve a real model:

1. Add a class that satisfies the `Embedder` protocol (`name`, `version`, `dim`,
   `embed(texts) -> float32 array`, rows L2-normalized) and register it.
2. Load weights in its constructor from `MODEL_CACHE_DIR` — never bake them into
   the image. The startupProbe already budgets 150s for the load.
3. Raise memory requests/limits in `deploy/kustomize/services/similarity-search/base/`
   to fit the weights, and use the `gpu` overlay if the model needs one.

The HTTP surface, probes, guardrails and alerts do not change.

## Deploy

`deploy/kustomize/services/similarity-search/` was rendered alongside this service;
GitOps picks up `overlays/local` on merge. `overlays/gpu` is a validated blueprint —
CI renders and policy-checks it, but nothing deploys it on the local single-node cluster.
