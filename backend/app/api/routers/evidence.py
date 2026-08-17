from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.api.deps import get_evidence_store_port
from app.modules.video_analysis.evidence_store import FileEvidenceStore

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get(
    "/rectification/{case_id}/{evidence_id}",
    response_class=Response,
)
async def rectification_evidence_image(
    case_id: str,
    evidence_id: str,
    store: FileEvidenceStore = Depends(get_evidence_store_port),
) -> Response:
    resolved = store.resolve_rectification_image(case_id, evidence_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="rectification image not found")
    path, media_type = resolved
    return Response(
        path.read_bytes(),
        media_type=media_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/{session_id}/{timestamp_ms}.jpg", response_class=Response)
async def evidence_image(
    session_id: str,
    timestamp_ms: int,
    store: FileEvidenceStore = Depends(get_evidence_store_port),
) -> Response:
    path = store.resolve_jpeg(session_id, timestamp_ms)
    if path is None:
        raise HTTPException(status_code=404, detail="evidence image not found")
    return Response(path.read_bytes(), media_type="image/jpeg")
