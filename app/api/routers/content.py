from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import authenticate, get_session
from app.modules.content.service import edit_content, import_web, review
from app.schemas import ContentEdit, JobRead, Review, WebImport

router = APIRouter()
protected = [Depends(authenticate)]


@router.post(
    "/api/import/web",
    response_model=JobRead,
    status_code=201,
    dependencies=protected,
    name="import_web",
)
def endpoint_import_web(payload: WebImport, session=Depends(get_session)):
    return import_web(payload=payload, session=session)


@router.put(
    "/api/jobs/{job_id}/content",
    response_model=JobRead,
    dependencies=protected,
    name="edit_content",
)
def endpoint_edit_content(job_id: UUID, payload: ContentEdit, session=Depends(get_session)):
    return edit_content(job_id=job_id, payload=payload, session=session)


@router.post(
    "/api/jobs/{job_id}/review", response_model=JobRead, dependencies=protected, name="review"
)
def endpoint_review(job_id: UUID, payload: Review, session=Depends(get_session)):
    return review(job_id=job_id, payload=payload, session=session)
