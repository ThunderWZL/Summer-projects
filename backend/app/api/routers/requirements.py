from fastapi import APIRouter, Depends, Query

from app.api.schemas import RequirementSearchResponse
from app.api.deps import get_requirement_retriever
from app.domain.requirements_rag import RequirementQuery
from app.modules.requirements_rag.service import RequirementsRagService


router = APIRouter(prefix="/api/v1/requirements", tags=["requirements"])


@router.get("/search", response_model=RequirementSearchResponse)
def search_requirements(
    q: str = Query(min_length=1),
    top_k: int | None = Query(default=None, ge=1, le=20),
    retriever: RequirementsRagService = Depends(get_requirement_retriever),
) -> RequirementSearchResponse:
    resolved_top_k = top_k or retriever.default_top_k
    citations = retriever.search(RequirementQuery(q=q, top_k=resolved_top_k))
    return RequirementSearchResponse(query=q, top_k=resolved_top_k, citations=citations)
