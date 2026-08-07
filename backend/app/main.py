from fastapi import FastAPI

from app.contracts import SHARED_COMMANDS, SHARED_CONTRACTS


app = FastAPI(
    title="SitePPE Agent",
    version="0.1.0",
    description="施工现场任务型 PPE 合规调查与整改平台",
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
