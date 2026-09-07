"""POST /ask endpoint. Checks API key, then delegates to the orchestrator."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.agent.orchestrator import handle_question
from app.auth.security import require_api_key
from app.llm.base import LLMClient
from app.llm.factory import get_llm_client

router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    customer_id: str | None = None

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value


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
    result = handle_question(
        question=payload.question,
        llm=llm,
        customer_id=payload.customer_id,
    )
    return AskResponse(
        answer=result.answer,
        action=result.action,
        sources=result.sources,
        ticket_id=result.ticket_id,
    )
