"""FastAPI entrypoint."""

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings

app = FastAPI(title="Enterprise AI Customer Success Assistant")
app.state.settings = settings
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
