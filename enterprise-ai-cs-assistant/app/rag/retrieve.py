"""Given a question, retrieves the closest chunks and their source doc names."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from app.rag import store as vector_store


class RetrievedChunk(TypedDict):
    text: str
    source: str
    distance: float


def retrieve(
    question: str,
    n_results: int = 4,
    persist_path: Path | None = None,
    collection_name: str = vector_store.COLLECTION_NAME,
) -> list[RetrievedChunk]:
    if not question or not question.strip():
        return []

    collection = vector_store.try_get_collection(
        persist_path=persist_path,
        collection_name=collection_name,
    )
    if collection is None or collection.count() == 0:
        return []

    k = min(n_results, collection.count())
    raw = collection.query(query_texts=[question.strip()], n_results=k)
    documents = (raw.get("documents") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]

    results: list[RetrievedChunk] = []
    for text, metadata, distance in zip(documents, metadatas, distances):
        source = ""
        if isinstance(metadata, dict):
            source = str(metadata.get("source") or "")
        results.append(
            {
                "text": text or "",
                "source": source,
                "distance": float(distance) if distance is not None else 0.0,
            }
        )
    return results
