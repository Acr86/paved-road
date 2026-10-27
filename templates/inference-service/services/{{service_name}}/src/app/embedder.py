"""Embedding backends behind one interface.

The service never imports a model library directly: it asks the registry for
an ``Embedder`` by name. That indirection is the whole point of the golden
path — the HTTP surface, probes, metrics and guardrails stay identical when
the deterministic default is swapped for a real model (a sentence-transformer,
a DINOv2 image encoder exported to ONNX, a hosted embeddings API).

``HashingEmbedder`` is the default because it makes the path runnable
everywhere: no weights to download, no GPU, byte-identical output on every
machine, so tests assert exact behavior instead of "roughly similar".
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    """What the service needs from a model. Nothing more."""

    name: str
    version: str
    dim: int

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Return a float32 array of shape (len(texts), dim), rows L2-normalized."""
        ...


class HashingEmbedder:
    """Feature-hashing over character n-grams.

    Each n-gram is hashed (BLAKE2b, so output is stable across processes and
    Python versions — unlike ``hash()``) into one of ``dim`` buckets with a
    sign bit, then the vector is L2-normalized. Texts that share n-grams land
    close together; that is enough lexical similarity to exercise search
    end to end, and it is fully deterministic.
    """

    name = "hashing"
    version = "v1"

    def __init__(self, dim: int, ngram: int = 3) -> None:
        if dim < 16:
            raise ValueError("dim must be at least 16")
        self.dim = dim
        self._ngram = ngram

    def _features(self, text: str) -> list[str]:
        padded = f" {text.lower().strip()} "
        if len(padded) <= self._ngram:
            return [padded]
        return [
            padded[i : i + self._ngram] for i in range(len(padded) - self._ngram + 1)
        ]

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for feature in self._features(text):
                digest = hashlib.blake2b(
                    feature.encode("utf-8"), digest_size=8
                ).digest()
                value = int.from_bytes(digest, "little")
                bucket = value % self.dim
                sign = 1.0 if (value >> 63) & 1 else -1.0
                out[row, bucket] += sign
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


# Backend registry. Adding a real model is one entry here plus one class that
# satisfies ``Embedder`` — the rest of the service does not change.
_BACKENDS: dict[str, Callable[[int], Embedder]] = {
    "hashing": lambda dim: HashingEmbedder(dim=dim),
}


def available_backends() -> list[str]:
    return sorted(_BACKENDS)


def load_embedder(backend: str, dim: int) -> Embedder:
    try:
        factory = _BACKENDS[backend]
    except KeyError:
        raise ValueError(
            f"unknown MODEL_BACKEND {backend!r} (available: {', '.join(available_backends())})"
        ) from None
    return factory(dim)
