"""台账 REST（架构稿 §4.1）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db.engine import get_session
from ..deps import require_auth
from ..repositories import record_repository as rec_repo
from ..schemas import BatchReviewPayload, DispositionPayload, ReviewPayload
from ..services import disposition_service, record_view, review_service
from ..services.errors import NotFoundError, ValidationError

router = APIRouter(prefix="/api/ledger", tags=["ledger"])

_VALID_SORT = {"capture_time_desc", "capture_time_asc", "confidence_desc", "confidence_asc"}
_VALID_STATUS = {"all", "pending", "approved", "rejected"}
_VALID_DISPOSITION = {"all", "to_notify", "notified", "disposed", "archived"}


@router.get("/records")
def list_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: str = Query("all"),
    camera_id: str | None = None,
    category: str | None = None,
    disposition_status: str = Query("all"),
    start_time: str | None = None,
    end_time: str | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    keyword: str | None = None,
    sort: str = Query("capture_time_desc"),
    session: Session = Depends(get_session),
) -> dict:
    if status not in _VALID_STATUS:
        raise ValidationError(f"status 非法：{status!r}，应为 {sorted(_VALID_STATUS)}")
    if disposition_status not in _VALID_DISPOSITION:
        raise ValidationError(f"disposition_status 非法：{disposition_status!r}")
    if sort not in _VALID_SORT:
        raise ValidationError(f"sort 非法：{sort!r}，应为 {sorted(_VALID_SORT)}")
    if min_confidence is not None and not (0 <= min_confidence <= 1):
        raise ValidationError("min_confidence 必须在 0-1 之间")
    if max_confidence is not None and not (0 <= max_confidence <= 1):
        raise ValidationError("max_confidence 必须在 0-1 之间")

    filters = {
        "status": status,
        "camera_id": camera_id,
        "category": category,
        "disposition_status": disposition_status,
        "start_time": start_time,
        "end_time": end_time,
        "min_confidence": min_confidence,
        "max_confidence": max_confidence,
        "keyword": keyword,
        "sort": sort,
    }
    rows, total = rec_repo.list_records(session, filters, page, page_size)
    return record_view.records_page(session, rows, total, page, page_size)


@router.get("/records/{record_id}")
def get_record(record_id: str, session: Session = Depends(get_session)) -> dict:
    record = rec_repo.get_by_id(session, record_id)
    if record is None:
        raise NotFoundError(f"台账记录不存在：{record_id}")
    return record_view.full_record(session, record)


@router.post("/records/{record_id}/review", dependencies=[Depends(require_auth)])
def review_record(
    record_id: str, payload: ReviewPayload, session: Session = Depends(get_session)
) -> dict:
    return review_service.apply_review(session, record_id, payload.model_dump())


@router.post("/records/{record_id}/disposition", dependencies=[Depends(require_auth)])
def dispose_record(
    record_id: str, payload: DispositionPayload, session: Session = Depends(get_session)
) -> dict:
    return disposition_service.apply_disposition(session, record_id, payload.model_dump())


@router.post("/records/batch-review", dependencies=[Depends(require_auth)])
def batch_review(payload: BatchReviewPayload, session: Session = Depends(get_session)) -> dict:
    return review_service.batch_review(session, payload.model_dump())
