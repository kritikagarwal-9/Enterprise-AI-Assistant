"""POST /ask endpoint. Checks API key, retrieves docs, calls the LLM."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.security import require_api_key
from app.llm.base import LLMClient
from app.llm.factory import get_llm_client
from app.rag.retrieve import retrieve

router = APIRouter()

SYSTEM_PROMPT = (
    "You are an internal Customer Success assistant for CloudBoard, a B2B SaaS "
    "project-management product. Be concise and professional. Answer only from "
    "the retrieved CloudBoard documents supplied in the user message. If those "
    "documents do not contain the answer, say you do not know. Do not invent "
    "product facts, account data, refunds, contract terms, or tool results."
)

NO_CONTEXT_INSTRUCTION = (
    "No retrieved documents were found. Do not invent product facts. "
    "Say you do not have documentation for this question."
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    customer_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    action: str
    sources: list[str] = []
    ticket_id: str | None = None


def _user_message(question: str, hits: list[dict]) -> str:
    if not hits:
        return f"Question: {question}\n\n{NO_CONTEXT_INSTRUCTION}"
    blocks = []
    for index, hit in enumerate(hits, start=1):
        source = str(hit.get("source") or "unknown")
        text = str(hit.get("text") or "")
        blocks.append(f"[{index}] Source: {source}\n{text}")
    context = "\n\n".join(blocks)
    return (
        f"Question: {question}\n\n"
        f"Retrieved CloudBoard documents:\n\n{context}"
    )


def _unique_sources(hits: list[dict]) -> list[str]:
    seen: list[str] = []
    for hit in hits:
        name = str(hit.get("source") or "").strip()
        if name and name not in seen:
            seen.append(name)
    return seen


@router.post("/ask", response_model=AskResponse, dependencies=[Depends(require_api_key)])
def ask(
    payload: AskRequest,
    llm: LLMClient = Depends(get_llm_client),
) -> AskResponse:
    hits = retrieve(payload.question)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _user_message(payload.question, hits)},
    ]
    answer = llm.complete(messages)
    return AskResponse(answer=answer, action="answer", sources=_unique_sources(hits))
