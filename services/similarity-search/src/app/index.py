"""In-memory vector index: exact cosine search over normalized vectors.

Brute force is the honest default up to tens of thousands of vectors — one
matrix-vector product, no recall/latency trade-off to tune, no index to
rebuild. Past that, swap this class for FAISS (IVF/HNSW) or a managed vector
store; the service only depends on ``upsert``, ``search`` and ``__len__``.

State lives in process memory and is lost on restart by design: the
reference path keeps the platform stateless. A production index is either
rebuilt from a source of truth at startup or lives in a dedicated store.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Match:
    id: str
    score: float


class VectorIndex:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self._ids: list[str] = []
        self._positions: dict[str, int] = {}
        self._matrix = np.zeros((0, dim), dtype=np.float32)
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._ids)

    def upsert(self, ids: list[str], vectors: np.ndarray) -> None:
        if vectors.shape != (len(ids), self.dim):
            raise ValueError(f"expected vectors of shape ({len(ids)}, {self.dim})")
        # Last write wins when the same id appears twice in one batch.
        latest = dict(zip(ids, vectors, strict=True))
        with self._lock:
            new_rows: list[np.ndarray] = []
            for item_id, vector in latest.items():
                position = self._positions.get(item_id)
                if position is None:
                    self._positions[item_id] = len(self._ids)
                    self._ids.append(item_id)
                    new_rows.append(vector)
                else:
                    self._matrix[position] = vector
            if new_rows:
                self._matrix = np.vstack([self._matrix, np.stack(new_rows)])

    def search(self, query: np.ndarray, k: int) -> list[Match]:
        with self._lock:
            if not self._ids:
                return []
            scores = self._matrix @ query
            k = min(k, len(self._ids))
            top = np.argpartition(-scores, k - 1)[:k]
            ranked = top[np.argsort(-scores[top], kind="stable")]
            return [Match(id=self._ids[i], score=float(scores[i])) for i in ranked]
