"""Public RAG functions. Vector store details stay in app.rag.store."""

from app.rag.ingest import ingest_docs
from app.rag.retrieve import retrieve

__all__ = ["ingest_docs", "retrieve"]
