from __future__ import annotations

import numpy as np
import pytest

from app.embedder import HashingEmbedder, available_backends, load_embedder
from app.index import VectorIndex


def test_unknown_backend_fails_with_guidance() -> None:
    with pytest.raises(ValueError, match="hashing"):
        load_embedder("does-not-exist", 64)


def test_registry_lists_the_default_backend() -> None:
    assert "hashing" in available_backends()


def test_hashing_is_stable_across_instances() -> None:
    # BLAKE2b, not hash(): identical output across processes and machines.
    a = HashingEmbedder(dim=64).embed(["paved road"])
    b = HashingEmbedder(dim=64).embed(["paved road"])
    assert np.array_equal(a, b)


def test_similar_texts_score_higher_than_unrelated_ones() -> None:
    embedder = HashingEmbedder(dim=256)
    base, near, far = embedder.embed(
        ["kubernetes ingress controller", "kubernetes ingress", "chocolate cake recipe"]
    )
    assert float(base @ near) > float(base @ far)


def test_index_returns_at_most_k_and_handles_empty() -> None:
    index = VectorIndex(dim=16)
    assert index.search(np.ones(16, dtype=np.float32), k=3) == []
    vectors = HashingEmbedder(dim=16).embed(["a", "b"])
    index.upsert(["a", "b"], vectors)
    assert len(index.search(vectors[0], k=10)) == 2


def test_index_last_write_wins_within_a_batch() -> None:
    index = VectorIndex(dim=16)
    vectors = HashingEmbedder(dim=16).embed(["first", "second"])
    index.upsert(["dup", "dup"], vectors)
    assert len(index) == 1
    assert index.search(vectors[1], k=1)[0].id == "dup"


def test_index_rejects_wrong_shape() -> None:
    with pytest.raises(ValueError, match="shape"):
        VectorIndex(dim=16).upsert(["a"], np.zeros((1, 8), dtype=np.float32))
