"""Chroma persistence adapter. Callers should use ingest/retrieve, not this module."""

from __future__ import annotations

from pathlib import Path

import chromadb

from app.core.config import settings

COLLECTION_NAME = "product_docs"

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def default_persist_path() -> Path:
    path = Path(settings.chroma_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def get_client(persist_path: Path | None = None) -> chromadb.PersistentClient:
    root = Path(persist_path) if persist_path is not None else default_persist_path()
    root.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(root))


def reset_collection(
    persist_path: Path | None = None,
    collection_name: str = COLLECTION_NAME,
):
    client = get_client(persist_path)
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    return client.create_collection(name=collection_name)


def try_get_collection(
    persist_path: Path | None = None,
    collection_name: str = COLLECTION_NAME,
):
    try:
        client = get_client(persist_path)
        return client.get_collection(collection_name)
    except Exception:
        return None
