"""POST /ask endpoint. Checks API key, calls the LLM, returns the answer."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.security import require_api_key
from app.llm.base import LLMClient
from app.llm.factory import get_llm_client

router = APIRouter()

SYSTEM_PROMPT = (
    "You are an internal Customer Success assistant for CloudBoard, a B2B SaaS "
    "project-management product. Be concise and professional. Do not invent "
    "account data, refunds, contract terms, or tool results. This turn has no "
    "retrieved documents and no account lookup."
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    customer_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    action: str
    sources: list[str] = []
    ticket_id: str | None = None


@router.post("/ask", response_model=AskResponse, dependencies=[Depends(require_api_key)])
def ask(
    payload: AskRequest,
    llm: LLMClient = Depends(get_llm_client),
) -> AskResponse:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": payload.question},
    ]
    answer = llm.complete(messages)
    return AskResponse(answer=answer, action="answer")
