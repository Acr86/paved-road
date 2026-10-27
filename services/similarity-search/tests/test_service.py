from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app


@pytest.fixture()
def client() -> Iterator[TestClient]:
    # The context manager runs the lifespan: the model loads exactly as in a pod.
    with TestClient(app) as test_client:
        yield test_client


class TestProbes:
    def test_healthz_is_alive(self, client: TestClient) -> None:
        assert client.get("/healthz").json() == {"status": "ok"}

    def test_readyz_is_ready_once_model_loaded(self, client: TestClient) -> None:
        response = client.get("/readyz")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    def test_not_ready_and_refuses_inference_before_load(self) -> None:
        # No lifespan: the state of a pod whose model is still loading.
        main.unload_model()
        bare = TestClient(app)
        healthz = bare.get("/healthz")
        assert healthz.status_code == 200, "liveness must not depend on the model"
        assert bare.get("/readyz").status_code == 503
        assert bare.post("/v1/embeddings", json={"inputs": ["x"]}).status_code == 503


class TestInference:
    def test_embeddings_have_contract_shape(self, client: TestClient) -> None:
        response = client.post("/v1/embeddings", json={"inputs": ["hello", "world"]})
        assert response.status_code == 200
        body = response.json()
        assert body["dim"] == 384
        assert len(body["data"]) == 2
        assert all(len(row) == 384 for row in body["data"])
        assert response.headers["X-Model"] == body["model"]

    def test_embeddings_are_deterministic_and_normalized(
        self, client: TestClient
    ) -> None:
        payload = {"inputs": ["same text"]}
        first = client.post("/v1/embeddings", json=payload).json()["data"][0]
        second = client.post("/v1/embeddings", json=payload).json()["data"][0]
        assert first == second
        assert abs(sum(v * v for v in first) - 1.0) < 1e-4

    def test_search_ranks_the_closest_item_first(self, client: TestClient) -> None:
        items = [
            {"id": "invoice", "text": "monthly invoice for cloud hosting services"},
            {"id": "recipe", "text": "slow cooked cochinita pibil with achiote"},
            {"id": "runbook", "text": "runbook: restart the ingress controller"},
        ]
        indexed = client.post("/v1/index", json={"items": items}).json()
        assert indexed == {"indexed": 3, "total": 3}
        query = {"query": "cochinita pibil", "k": 2}
        hits = client.post("/v1/search", json=query).json()
        assert [h["id"] for h in hits["results"]][0] == "recipe"
        assert len(hits["results"]) == 2

    def test_reindexing_an_id_replaces_it(self, client: TestClient) -> None:
        client.post("/v1/index", json={"items": [{"id": "a", "text": "first version"}]})
        total = client.post(
            "/v1/index", json={"items": [{"id": "a", "text": "second version"}]}
        ).json()["total"]
        assert total == 1


class TestGuardrails:
    def test_batch_over_limit_is_rejected(self, client: TestClient) -> None:
        response = client.post("/v1/embeddings", json={"inputs": ["x"] * (64 + 1)})
        assert response.status_code == 422

    def test_oversized_input_is_rejected(self, client: TestClient) -> None:
        huge = "a" * (main.MAX_INPUT_CHARS + 1)
        assert client.post("/v1/embeddings", json={"inputs": [huge]}).status_code == 422

    def test_k_is_bounded(self, client: TestClient) -> None:
        for k in (0, 10_000):
            response = client.post("/v1/search", json={"query": "x", "k": k})
            assert response.status_code == 422, k


def test_metrics_expose_the_inference_contract(client: TestClient) -> None:
    client.post("/v1/embeddings", json={"inputs": ["observe me"]})
    text = client.get("/metrics").text
    for name in (
        "inference_duration_seconds",
        "inference_batch_size",
        "inference_model_loaded 1.0",
        "inference_model_info",
        "inference_index_vectors",
        "inference_max_batch 64.0",
        "http_request_duration_seconds",
    ):
        assert name in text, f"metric {name!r} missing from /metrics"
