"""RAG ingest and retrieval tests. Uses temp dirs, not the repo chroma_db."""

from pathlib import Path

import pytest

from app.rag import ingest as ingest_module
from app.rag import store as store_module
from app.rag.ingest import chunk_text, ingest_docs
from app.rag.retrieve import retrieve
from app.rag.store import try_get_collection


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


def test_chunk_text_keeps_leading_title_and_subheading_with_their_bullets() -> None:
    """Mirrors release-notes.md's exact shape: a leading top-level title
    directly followed by a "##" subheading, then that subheading's bullets,
    then a second "##" subheading with its own bullets. A naive single-
    lookahead heading merge would merge the title into the first subheading
    and leave the first subheading's bullets orphaned -- this must not
    happen.
    """
    text = (
        "# Release notes\n\n"
        "## 2026.8\n\n"
        "- Pro plans can export CSV reports from the reporting dashboard.\n"
        "- Starter plans now include two saved board templates.\n\n"
        "## 2026.7\n\n"
        "- Fixed a bug where seat invites failed for past_due accounts "
        "until the invoice was paid."
    )
    chunks = chunk_text(text, source="release-notes.md")
    texts = [chunk["text"] for chunk in chunks]

    chunk_2026_8 = next((t for t in texts if "2026.8" in t), None)
    chunk_2026_7 = next((t for t in texts if "2026.7" in t), None)

    assert chunk_2026_8 is not None
    assert chunk_2026_7 is not None
    assert chunk_2026_8 != chunk_2026_7

    assert "CSV reports" in chunk_2026_8
    assert "board templates" in chunk_2026_8
    assert "seat invites" not in chunk_2026_8
    assert "2026.7" not in chunk_2026_8

    assert "seat invites" in chunk_2026_7
    assert "CSV reports" not in chunk_2026_7
    assert "board templates" not in chunk_2026_7
    assert "2026.8" not in chunk_2026_7


def test_try_get_collection_returns_none_when_get_client_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _boom(persist_path=None):
        raise RuntimeError("corrupted chroma store")

    monkeypatch.setattr(store_module, "get_client", _boom)
    assert try_get_collection(persist_path=tmp_path / "chroma") is None
    assert retrieve("What plans do you offer?", persist_path=tmp_path / "chroma") == []
