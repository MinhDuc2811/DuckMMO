"""Protected learning library routes; application services own persistence."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import authenticate, get_session
from app.contracts.ielts import (
    BriefInput,
    ImportInput,
    ItemInput,
    ItemReview,
    ItemUpdate,
    TopicInput,
)
from app.modules.ielts import library

router = APIRouter(prefix="/api/ielts", dependencies=[Depends(authenticate)])


@router.get("/topics")
def topics(session=Depends(get_session)):
    return library.list_topics(session=session)


@router.post("/topics", status_code=201)
def create_topic(payload: TopicInput, session=Depends(get_session)):
    return library.create_topic(payload, session=session)


# Register concrete resource paths so OpenAPI describes the four independent collections.
def collection(kind):
    def listing(
        q: str = Query(default="", max_length=200),
        topic_id: UUID | None = None,
        status: Literal["draft", "reviewed"] | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        session=Depends(get_session),
    ):
        return library.list_items(kind, q, topic_id, status, limit, offset, session=session)

    def create(payload: ItemInput, session=Depends(get_session)):
        return library.create_item(kind, payload, session=session)

    router.add_api_route(f"/{kind}", listing, methods=["GET"], name=f"list_{kind}")
    router.add_api_route(
        f"/{kind}", create, methods=["POST"], status_code=201, name=f"create_{kind}"
    )


for kind in library.TYPES:
    collection(kind)


@router.get("/items/{item_id}")
def item(item_id: UUID, session=Depends(get_session)):
    return library.read_item(item_id, session=session)


@router.post("/items/{item_id}/review")
def review(item_id: UUID, payload: ItemReview, session=Depends(get_session)):
    return library.review_item(item_id, payload, session=session)


@router.post("/items/{item_id}/brief")
def brief(item_id: UUID, payload: BriefInput, session=Depends(get_session)):
    return library.prepare_brief(item_id, payload, session=session)


@router.post("/imports/preview")
def preview(payload: ImportInput, session=Depends(get_session)):
    return library.preview_import(payload, session=session)


@router.post("/imports", status_code=201)
def import_batch(payload: ImportInput, session=Depends(get_session)):
    return library.import_items(payload, session=session)


@router.put("/items/{item_id}")
def update(item_id: UUID, payload: ItemUpdate, session=Depends(get_session)):
    return library.update_item(item_id, payload, session=session)


@router.get("/items/{item_id}/revisions")
def revisions(item_id: UUID, session=Depends(get_session)):
    return library.revisions(item_id, session=session)
