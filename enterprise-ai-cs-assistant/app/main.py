"""FastAPI entrypoint."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import settings
from app.llm.base import LLMError

app = FastAPI(title="Enterprise AI Customer Success Assistant")
app.state.settings = settings
app.include_router(router)


@app.exception_handler(LLMError)
def llm_error_handler(_request: Request, exc: LLMError) -> JSONResponse:
    if not exc.configured:
        return JSONResponse(status_code=503, content={"detail": "LLM not configured"})
    return JSONResponse(status_code=502, content={"detail": "Upstream LLM failed"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
