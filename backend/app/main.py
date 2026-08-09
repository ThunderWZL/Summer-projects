from fastapi import FastAPI

from app.api.errors import case_workflow_exception_handler
from app.api.routers.cases import router as cases_router
from app.api.routers.demo import router as demo_router
from app.api.routers.requirements import router as requirements_router
from app.contracts import SHARED_COMMANDS, SHARED_CONTRACTS
from app.domain.case_workflow import CaseWorkflowError


app = FastAPI(
    title="SitePPE Agent",
    version="0.1.0",
    description="施工现场任务型 PPE 合规调查与整改平台",
)
app.include_router(demo_router)
app.include_router(requirements_router)
app.include_router(cases_router)
app.add_exception_handler(
    CaseWorkflowError,
    case_workflow_exception_handler,
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
