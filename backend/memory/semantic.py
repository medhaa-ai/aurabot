"""Hash-based vector embedding for ChromaDB — no ML packages required."""

import hashlib
import math


def embed(text: str, dim: int = 384) -> list:
    """
    Deterministic word-level bag-of-words embedding via SHA-256 hash projection.
    Cosine similarity approximates keyword overlap — sufficient for personal memory
    retrieval without any ML dependencies or internet download.
    """
    vec = [0.0] * dim
    for word in text.lower().split():
        h = int(hashlib.sha256(word.encode()).hexdigest(), 16)
        for i in range(8):
            idx = (h >> (i * 8)) % dim
            vec[idx] += 1.0
    mag = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / mag for x in vec]


class HashEmbeddingFn:
    """ChromaDB EmbeddingFunction duck-type (no ABC required in 0.6.x)."""
    def __call__(self, input: list) -> list:
        return [embed(str(text)) for text in input]
