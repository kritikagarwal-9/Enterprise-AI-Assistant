"""RAG ingest and retrieval tests. Uses temp dirs, not the repo chroma_db."""

from pathlib import Path

from app.rag.ingest import ingest_docs
from app.rag.retrieve import retrieve


def _write_docs(docs_dir: Path) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "plans.md").write_text(
        "# Plans\n\nCloudBoard offers Starter, Pro, and Enterprise plans.\n",
        encoding="utf-8",
    )
    (docs_dir / "other.md").write_text(
        "# Other\n\nBoards hold tasks and comments.\n",
        encoding="utf-8",
    )


def test_retrieve_plans_question_hits_plans_source(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    persist_path = tmp_path / "chroma"
    _write_docs(docs_dir)
    assert ingest_docs(docs_dir=docs_dir, persist_path=persist_path) > 0

    hits = retrieve("What plans do you offer?", persist_path=persist_path)
    assert hits
    assert all("text" in hit and "source" in hit and "distance" in hit for hit in hits)
    assert any(hit["source"] == "plans.md" for hit in hits)


def test_empty_query_returns_no_hits(tmp_path: Path) -> None:
    persist_path = tmp_path / "chroma"
    assert retrieve("", persist_path=persist_path) == []
    assert retrieve("   ", persist_path=persist_path) == []


def test_retrieve_before_ingest_returns_no_hits(tmp_path: Path) -> None:
    persist_path = tmp_path / "chroma"
    persist_path.mkdir()
    assert retrieve("What plans do you offer?", persist_path=persist_path) == []
