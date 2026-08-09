from fastapi import APIRouter, Query

from app.api.schemas import RequirementSearchResponse


router = APIRouter(prefix="/api/v1/requirements", tags=["requirements"])


@router.get("/search", response_model=RequirementSearchResponse)
def search_requirements(
    q: str = Query(min_length=1),
    top_k: int = Query(default=5, ge=1, le=20),
) -> RequirementSearchResponse:
    return RequirementSearchResponse(query=q, top_k=top_k, citations=[])
