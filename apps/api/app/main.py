from fastapi import FastAPI

from .core.config import settings


app = FastAPI(title=settings.app_name)


@app.get("/api/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
