from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect

from .api.routes.admin_model_configs import router as admin_model_configs_router
from .api.routes.auth import router as auth_router
from .api.routes.exports import router as exports_router
from .api.routes.finalize import router as finalize_router
from .api.routes.messages import router as messages_router
from .api.routes.model_configs import router as model_configs_router
from .api.routes.sessions import router as sessions_router
from .core.config import settings
from .core.api_error import ApiError, build_api_error_payload
from .db.models import AgentTurnDecision, AssistantReplyGroup, AssistantReplyVersion
from .db.session import engine
from .services.sessions import SCHEMA_OUTDATED_DETAIL


app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(messages_router)
app.include_router(finalize_router)
app.include_router(exports_router)
app.include_router(admin_model_configs_router)
app.include_router(model_configs_router)


@app.exception_handler(ApiError)
async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
    return exc.to_response()


def get_schema_health(bind) -> dict[str, str | list[str]]:
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    required_tables = (
        AssistantReplyGroup.__tablename__,
        AssistantReplyVersion.__tablename__,
        AgentTurnDecision.__tablename__,
    )
    missing_tables = [table_name for table_name in required_tables if table_name not in existing_tables]
    return {
        "schema": "ready" if not missing_tables else "outdated",
        "missing_tables": missing_tables,
    }


@app.get("/api/health", response_model=None)
def healthcheck():
    schema_health = get_schema_health(engine)
    if schema_health["schema"] == "outdated":
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "schema": "outdated",
                **build_api_error_payload(
                    code="SCHEMA_OUTDATED",
                    message=SCHEMA_OUTDATED_DETAIL,
                    recovery_action={
                        "type": "run_migration",
                        "label": "执行数据库迁移",
                        "target": "cd apps/api && alembic upgrade head",
                    },
                ),
                "missing_tables": schema_health["missing_tables"],
            },
        )
    return {"status": "ok", "schema": "ready"}
