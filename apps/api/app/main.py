from fastapi import FastAPI

from .api.routes.auth import router as auth_router
from .api.routes.exports import router as exports_router
from .api.routes.messages import router as messages_router
from .api.routes.sessions import router as sessions_router
from .core.config import settings


app = FastAPI(title=settings.app_name)
app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(messages_router)
app.include_router(exports_router)


@app.get("/api/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
