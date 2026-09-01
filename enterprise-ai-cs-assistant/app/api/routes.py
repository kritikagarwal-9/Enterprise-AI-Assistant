"""POST /ask endpoint. Checks API key, calls the agent, returns the answer."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.security import require_api_key

router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    customer_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    action: str
    sources: list[str] = []
    ticket_id: str | None = None


@router.post("/ask", response_model=AskResponse, dependencies=[Depends(require_api_key)])
def ask(payload: AskRequest) -> AskResponse:
    # Agent / RAG / tools are wired in later milestones.
    return AskResponse(
        answer="Stub response. The assistant is not implemented yet.",
        action="stub",
    )
