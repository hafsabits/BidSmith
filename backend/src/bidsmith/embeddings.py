"""Local sentence-transformers embeddings (no API cost). Swap for Vertex AI later."""

from functools import lru_cache

from bidsmith.settings import get_settings


@lru_cache
def _model():
    from sentence_transformers import SentenceTransformer  # heavy import, load lazily

    return SentenceTransformer(get_settings().embedding_model)


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = _model().encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
