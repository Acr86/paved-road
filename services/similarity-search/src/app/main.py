"""similarity-search — scaffolded from the inference-service golden path.

Lifecycle contract the platform relies on (ADR-0014):

- The model loads once, at startup, before the pod is marked ready. A slow
  load is absorbed by the startupProbe, never by liveness — so a large model
  is not killed mid-load and restarted forever.
- /healthz answers as soon as the process is up; it never depends on the model.
- /readyz returns 503 until the model is in memory; traffic arrives only then.
- A model that fails to load crashes the process loudly instead of serving
  a half-initialized pod: CrashLoopBackOff is visible, a silent 500 is not.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException, Response
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

from app import metrics
from app.embedder import Embedder, load_embedder
from app.index import VectorIndex
from app.logging_config import configure_logging

configure_logging()
logger = logging.getLogger("similarity-search")

SERVICE_NAME = "similarity-search"
MODEL_BACKEND = os.environ.get("MODEL_BACKEND", "hashing")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "384"))
MAX_BATCH = int(os.environ.get("MAX_BATCH", "64"))
MAX_INPUT_CHARS = int(os.environ.get("MAX_INPUT_CHARS", "2000"))
MAX_K = 50
# Simulates a slow model load so the startupProbe behavior can be observed
# locally (e.g. MODEL_LOAD_DELAY_SECONDS=20). Zero in every real deployment.
MODEL_LOAD_DELAY_SECONDS = float(os.environ.get("MODEL_LOAD_DELAY_SECONDS", "0"))


@dataclass
class ModelState:
    embedder: Embedder | None = None
    index: VectorIndex | None = None
    loaded: bool = False
    load_seconds: float = field(default=0.0)


state = ModelState()


def load_model() -> None:
    started = time.perf_counter()
    if MODEL_LOAD_DELAY_SECONDS > 0:
        time.sleep(MODEL_LOAD_DELAY_SECONDS)
    embedder = load_embedder(MODEL_BACKEND, EMBEDDING_DIM)
    # The first call pays any lazy initialization here, not on a request.
    embedder.embed(["warmup"])
    state.embedder = embedder
    state.index = VectorIndex(dim=embedder.dim)
    state.load_seconds = time.perf_counter() - started
    state.loaded = True
    metrics.MODEL_LOADED.set(1)
    metrics.MODEL_LOAD_SECONDS.set(state.load_seconds)
    metrics.MODEL_INFO.labels(
        model=embedder.name, version=embedder.version, dim=str(embedder.dim)
    ).set(1)
    metrics.INDEX_VECTORS.set(0)
    metrics.MAX_BATCH.set(MAX_BATCH)
    logger.info(
        "model loaded: %s@%s dim=%d in %.3fs",
        embedder.name,
        embedder.version,
        embedder.dim,
        state.load_seconds,
    )


def unload_model() -> None:
    state.embedder = None
    state.index = None
    state.loaded = False
    metrics.MODEL_LOADED.set(0)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    metrics.MODEL_LOADED.set(0)
    load_model()
    try:
        yield
    finally:
        unload_model()


app = FastAPI(
    title=SERVICE_NAME,
    description="Reference inference service: text embeddings and vector search behind the inference golden-path contract.",
    version=os.environ.get("SERVICE_VERSION", "dev"),
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, include_in_schema=False)


def _require_model() -> tuple[Embedder, VectorIndex]:
    if not state.loaded or state.embedder is None or state.index is None:
        raise HTTPException(status_code=503, detail="model is not loaded yet")
    return state.embedder, state.index


def _model_header(response: Response, embedder: Embedder) -> None:
    response.headers["X-Model"] = f"{embedder.name}@{embedder.version}"


# --- request/response schemas: limits are part of the contract ---------------
# Bounded batch sizes and input lengths are what keep tail latency and memory
# predictable; an unbounded request is a denial of service waiting to happen.


class EmbedRequest(BaseModel):
    inputs: list[str] = Field(min_length=1, max_length=MAX_BATCH)


class EmbedResponse(BaseModel):
    model: str
    dim: int
    data: list[list[float]]


class IndexItem(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)


class IndexRequest(BaseModel):
    items: list[IndexItem] = Field(min_length=1, max_length=MAX_BATCH)


class IndexResponse(BaseModel):
    indexed: int
    total: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    k: int = Field(default=5, ge=1, le=MAX_K)


class SearchHit(BaseModel):
    id: str
    score: float


class SearchResponse(BaseModel):
    model: str
    results: list[SearchHit]


def _check_lengths(texts: list[str]) -> None:
    too_long = [i for i, t in enumerate(texts) if not t or len(t) > MAX_INPUT_CHARS]
    if too_long:
        raise HTTPException(
            status_code=422,
            detail=f"inputs {too_long} are empty or exceed {MAX_INPUT_CHARS} characters",
        )


# --- probes -------------------------------------------------------------------


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    """Liveness: the process is up. Deliberately independent of the model."""
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
def readyz(response: Response) -> dict[str, str]:
    """Readiness: 200 only once the model is in memory. Also the startupProbe target."""
    if not state.loaded:
        response.status_code = 503
        return {"status": "loading"}
    return {"status": "ready"}


# --- inference API ------------------------------------------------------------


@app.post("/v1/embeddings", response_model=EmbedResponse)
def embeddings(request: EmbedRequest, response: Response) -> EmbedResponse:
    embedder, _ = _require_model()
    _check_lengths(request.inputs)
    metrics.INFERENCE_BATCH_SIZE.labels(operation="embed").observe(len(request.inputs))
    with metrics.INFERENCE_DURATION.labels(operation="embed").time():
        vectors = embedder.embed(request.inputs)
    _model_header(response, embedder)
    return EmbedResponse(
        model=f"{embedder.name}@{embedder.version}",
        dim=embedder.dim,
        data=vectors.round(6).tolist(),
    )


@app.post("/v1/index", response_model=IndexResponse)
def index_items(request: IndexRequest, response: Response) -> IndexResponse:
    embedder, index = _require_model()
    texts = [item.text for item in request.items]
    metrics.INFERENCE_BATCH_SIZE.labels(operation="embed").observe(len(texts))
    with metrics.INFERENCE_DURATION.labels(operation="embed").time():
        vectors = embedder.embed(texts)
    index.upsert([item.id for item in request.items], vectors)
    metrics.INDEX_VECTORS.set(len(index))
    _model_header(response, embedder)
    return IndexResponse(indexed=len(request.items), total=len(index))


@app.post("/v1/search", response_model=SearchResponse)
def search(request: SearchRequest, response: Response) -> SearchResponse:
    embedder, index = _require_model()
    with metrics.INFERENCE_DURATION.labels(operation="search").time():
        query = embedder.embed([request.query])[0]
        matches = index.search(query, request.k)
    _model_header(response, embedder)
    return SearchResponse(
        model=f"{embedder.name}@{embedder.version}",
        results=[SearchHit(id=m.id, score=round(m.score, 6)) for m in matches],
    )


@app.get("/")
def root() -> dict[str, object]:
    model = (
        f"{state.embedder.name}@{state.embedder.version}"
        if state.embedder is not None
        else None
    )
    return {
        "service": SERVICE_NAME,
        "owner": "team-platform",
        "version": os.environ.get("SERVICE_VERSION", "dev"),
        "model": model,
        "ready": state.loaded,
    }
