from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api.errors import (
    case_workflow_exception_handler,
    request_validation_exception_handler,
)
from app.api.routers.cases import router as cases_router
from app.api.routers.demo import router as demo_router
from app.api.routers.evidence import router as evidence_router
from app.api.routers.requirements import router as requirements_router
from app.api.routers.sessions import router as sessions_router
from app.api.ws import router as websocket_router
from app.api.deps import (
    initialize_database_runtime,
    shutdown_database_runtime,
)
from app.contracts import SHARED_COMMANDS, SHARED_CONTRACTS
from app.domain.case_workflow import CaseWorkflowError


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database_runtime()
    try:
        yield
    finally:
        shutdown_database_runtime()


app = FastAPI(
    title="SitePPE Agent",
    version="0.1.0",
    description="施工现场任务型 PPE 合规调查与整改平台",
    lifespan=lifespan,
)
app.include_router(demo_router)
app.include_router(requirements_router)
app.include_router(cases_router)
app.include_router(sessions_router)
app.include_router(evidence_router)
app.include_router(websocket_router)
app.add_exception_handler(
    CaseWorkflowError,
    case_workflow_exception_handler,
)
app.add_exception_handler(
    RequestValidationError,
    request_validation_exception_handler,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/contracts/schema")
async def contract_schema() -> dict[str, object]:
    return {
        model.__name__: model.model_json_schema()
        for model in SHARED_CONTRACTS + SHARED_COMMANDS
    }
