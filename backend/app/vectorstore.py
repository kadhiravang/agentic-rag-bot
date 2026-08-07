"""Qdrant (embedded, on-disk) + FastEmbed vector store wrapper.

Uses qdrant-client's local inference: models.Document values are embedded
locally with FastEmbed at upsert/query time.

Scoping: every point carries a session_id payload field and is only ever
retrievable by that exact session. Sessions are fully isolated - there is no
shared/global scope. A session's corpus is exactly the files that have been
uploaded into it (see main.py).
"""

import uuid
from collections import defaultdict

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


def ensure_collection() -> None:
    client = get_client()
    if not client.collection_exists(config.COLLECTION):
        reset_collection()


def index_chunks(chunks: list[Chunk], session_id: str) -> int:
    if not chunks:
        return 0
    ensure_collection()
    client = get_client()
    client.upsert(
        collection_name=config.COLLECTION,
        points=[
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{session_id}::{c.chunk_id}")),
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
                    "session_id": session_id,
                },
            )
            for c in chunks
        ],
    )
    return len(chunks)


def _scope_filter(session_id: str) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key="session_id", match=models.MatchValue(value=session_id))]
    )


def search(query: str, limit: int, session_id: str) -> list[dict]:
    client = get_client()
    if not client.collection_exists(config.COLLECTION):
        return []
    hits = client.query_points(
        collection_name=config.COLLECTION,
        query=models.Document(text=query, model=config.EMBED_MODEL),
        limit=limit,
        query_filter=_scope_filter(session_id),
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


def search_balanced(query: str, session_id: str) -> list[dict]:
    """Retrieve broadly then cap how many chunks any single source document can
    contribute, so one talkative or oversampled file can't crowd out the rest."""
    candidates = search(query, limit=config.TOP_K * 3, session_id=session_id)
    by_source: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        by_source[c["source"]].append(c)

    result: list[dict] = []
    progressed = True
    while len(result) < config.TOP_K and progressed:
        progressed = False
        for source, bucket in by_source.items():
            if len(result) >= config.TOP_K:
                break
            taken = sum(1 for r in result if r["source"] == source)
            if taken < config.PER_SOURCE_K and bucket:
                result.append(bucket.pop(0))
                progressed = True
    result.sort(key=lambda r: r["score"], reverse=True)
    return result


def delete_session_data(session_id: str) -> None:
    """Purge every point belonging to one session (called when the session is deleted)."""
    client = get_client()
    if not client.collection_exists(config.COLLECTION):
        return
    client.delete(
        collection_name=config.COLLECTION,
        points_selector=models.FilterSelector(filter=_scope_filter(session_id)),
    )


def collection_stats() -> dict:
    client = get_client()
    if not client.collection_exists(config.COLLECTION):
        return {"indexed": False, "points": 0}
    info = client.get_collection(config.COLLECTION)
    return {"indexed": True, "points": info.points_count}
