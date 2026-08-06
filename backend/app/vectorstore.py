"""Qdrant (embedded, on-disk) + FastEmbed vector store wrapper.

Uses qdrant-client's local inference: models.Document values are embedded
locally with FastEmbed at upsert/query time.
"""

import uuid

from qdrant_client import QdrantClient, models

from . import config
from .parsing import Chunk

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(path=config.QDRANT_PATH)
    return _client


def reset_collection() -> None:
    client = get_client()
    if client.collection_exists(config.COLLECTION):
        client.delete_collection(config.COLLECTION)
    client.create_collection(
        collection_name=config.COLLECTION,
        vectors_config=models.VectorParams(
            size=client.get_embedding_size(config.EMBED_MODEL),
            distance=models.Distance.COSINE,
        ),
    )


def index_chunks(chunks: list[Chunk]) -> int:
    client = get_client()
    client.upsert(
        collection_name=config.COLLECTION,
        points=[
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, c.chunk_id)),
                vector=models.Document(text=c.text, model=config.EMBED_MODEL),
                payload={
                    "chunk_id": c.chunk_id,
                    "source": c.source,
                    "speakers": c.speakers,
                    "ts_start": c.ts_start,
                    "ts_end": c.ts_end,
                    "page_start": c.page_start,
                    "page_end": c.page_end,
                    "index": c.index,
                    "text": c.text,
                },
            )
            for c in chunks
        ],
    )
    return len(chunks)


def search(query: str, limit: int = config.TOP_K, source: str | None = None) -> list[dict]:
    client = get_client()
    query_filter = (
        models.Filter(
            must=[models.FieldCondition(key="source", match=models.MatchValue(value=source))]
        )
        if source
        else None
    )
    hits = client.query_points(
        collection_name=config.COLLECTION,
        query=models.Document(text=query, model=config.EMBED_MODEL),
        limit=limit,
        query_filter=query_filter,
    ).points
    results = []
    for h in hits:
        payload = h.payload or {}
        results.append(
            {
                "chunk_id": payload.get("chunk_id"),
                "source": payload.get("source"),
                "speakers": payload.get("speakers", []),
                "ts_start": payload.get("ts_start"),
                "ts_end": payload.get("ts_end"),
                "page_start": payload.get("page_start"),
                "page_end": payload.get("page_end"),
                "text": payload.get("text", ""),
                "score": round(float(h.score), 4),
            }
        )
    return results


def search_balanced(query: str) -> list[dict]:
    """Top-k per transcript, so one talkative source can't crowd out the other."""
    results: list[dict] = []
    for source in config.SOURCE_NAMES:
        results.extend(search(query, limit=config.PER_SOURCE_K, source=source))
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def collection_stats() -> dict:
    client = get_client()
    if not client.collection_exists(config.COLLECTION):
        return {"indexed": False, "points": 0}
    info = client.get_collection(config.COLLECTION)
    return {"indexed": True, "points": info.points_count}
