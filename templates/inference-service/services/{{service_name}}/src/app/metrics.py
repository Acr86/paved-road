"""The inference metrics contract.

These names are a platform interface, not a service detail: the alert rules
in observability/alerts/inference.yaml select on them across every service
scaffolded from this path, so a new inference service is covered by
alerting the moment it is scraped. Rename one here and the alerts go blind —
the golden test in platform-cli pins the names.

HTTP golden signals (rate, errors, latency per route) still come from the
instrumentator in main.py; these add what HTTP metrics cannot see: time
spent in the model versus in the web stack, batch sizes, and whether a
model is loaded at all.
"""

from __future__ import annotations

from prometheus_client import Gauge, Histogram

# Model time only, per operation (embed / search). Buckets skew low: a
# CPU embedding of a small batch should land in single-digit milliseconds,
# and the 0.5s bucket is the platform's default p95 objective.
INFERENCE_DURATION = Histogram(
    "inference_duration_seconds",
    "Time spent inside the model or index, excluding HTTP overhead.",
    labelnames=("operation",),
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

INFERENCE_BATCH_SIZE = Histogram(
    "inference_batch_size",
    "Inputs per inference call.",
    labelnames=("operation",),
    buckets=(1, 2, 4, 8, 16, 32, 64, 128, 256),
)

MODEL_LOADED = Gauge(
    "inference_model_loaded",
    "1 when the model is loaded and serving, 0 otherwise.",
)

MODEL_LOAD_SECONDS = Gauge(
    "inference_model_load_seconds",
    "Wall-clock time the last model load took.",
)

MODEL_INFO = Gauge(
    "inference_model_info",
    "Identity of the loaded model (value is always 1).",
    labelnames=("model", "version", "dim"),
)

MAX_BATCH = Gauge(
    "inference_max_batch",
    "Configured ceiling on inputs per request (MAX_BATCH).",
)

INDEX_VECTORS = Gauge(
    "inference_index_vectors",
    "Vectors currently held in the in-memory index.",
)
