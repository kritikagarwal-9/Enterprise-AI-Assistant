"""POST /ask endpoint. Checks API key, then delegates to the orchestrator."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.agent.orchestrator import handle_question
from app.auth.security import AuthContext, require_api_key
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


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    auth: AuthContext = Depends(require_api_key),
    llm: LLMClient = Depends(get_llm_client),
) -> AskResponse:
    customer_id = payload.customer_id
    if auth.scope == "customer":
        if customer_id is None:
            customer_id = auth.customer_id
        elif customer_id != auth.customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for this customer_id",
            )

    result = handle_question(
        question=payload.question,
        llm=llm,
        customer_id=customer_id,
    )
    return AskResponse(
        answer=result.answer,
        action=result.action,
        sources=result.sources,
        ticket_id=result.ticket_id,
    )
