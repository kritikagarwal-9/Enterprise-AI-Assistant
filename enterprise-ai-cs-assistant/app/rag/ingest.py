"""Loads docs from data/docs, chunks them, embeds them into Chroma."""

from __future__ import annotations

from pathlib import Path

from app.rag import store as vector_store

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCS_DIR = PROJECT_ROOT / "data" / "docs"
MAX_CHUNK_CHARS = 800


def _group_headings_with_content(paragraphs: list[str]) -> list[str]:
    """Keep a run of Markdown heading-only paragraphs attached to the content
    paragraph that follows them, so a heading like "## 2026.8" never ends up
    as its own chunk disconnected from the text under it.
    """
    groups: list[str] = []
    index = 0
    while index < len(paragraphs):
        paragraph = paragraphs[index]
        if paragraph.startswith("#"):
            group = [paragraph]
            index += 1
            while index < len(paragraphs) and paragraphs[index].startswith("#"):
                group.append(paragraphs[index])
                index += 1
            if index < len(paragraphs):
                group.append(paragraphs[index])
                index += 1
            groups.append("\n".join(group))
        else:
            groups.append(paragraph)
            index += 1
    return groups


def chunk_text(text: str, source: str) -> list[dict[str, str]]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    grouped = _group_headings_with_content(paragraphs)
    chunks: list[dict[str, str]] = []
    for paragraph in grouped:
        for piece in _split_long(paragraph, MAX_CHUNK_CHARS):
            chunks.append({"text": piece, "source": source})
    return chunks


def _split_long(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            pieces.append(remaining.strip())
            break
        window = remaining[:max_chars]
        cut = window.rfind(". ")
        if cut < max_chars // 4:
            cut = max_chars
        else:
            cut = cut + 1
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    return [p for p in pieces if p]


def load_chunks(docs_dir: Path) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for path in sorted(docs_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        chunks.extend(chunk_text(text, source=path.name))
    return chunks


def ingest_docs(
    docs_dir: Path | None = None,
    persist_path: Path | None = None,
    collection_name: str = vector_store.COLLECTION_NAME,
) -> int:
    source_dir = Path(docs_dir) if docs_dir is not None else DEFAULT_DOCS_DIR
    chunks = load_chunks(source_dir)
    collection = vector_store.reset_collection(
        persist_path=persist_path,
        collection_name=collection_name,
    )
    if not chunks:
        return 0
    collection.add(
        ids=[f"{chunk['source']}-{index}" for index, chunk in enumerate(chunks)],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[{"source": chunk["source"]} for chunk in chunks],
    )
    return len(chunks)


if __name__ == "__main__":
    count = ingest_docs()
    print(f"Ingested {count} chunks")
