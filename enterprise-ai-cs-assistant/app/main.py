"""FastAPI entrypoint."""

import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import settings
from app.core.logging import configure_logging, logger, request_logging_middleware
from app.llm.base import LLMError

configure_logging()

app = FastAPI(title="Enterprise AI Customer Success Assistant")
app.state.settings = settings
app.middleware("http")(request_logging_middleware)
app.include_router(router)


@app.exception_handler(LLMError)
def llm_error_handler(_request: Request, exc: LLMError) -> JSONResponse:
    if not exc.configured:
        return JSONResponse(status_code=503, content={"detail": "LLM not configured"})
    return JSONResponse(status_code=502, content={"detail": "Upstream LLM failed"})


@app.exception_handler(Exception)
def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        json.dumps(
            {
                "event": "unhandled_exception",
                "path": request.url.path,
                "method": request.method,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
            }
        )
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
