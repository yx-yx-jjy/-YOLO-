"""汇总统计 REST（架构稿 §4.2）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db.engine import get_session
from ..services import stats_service
from ..services.errors import ValidationError

router = APIRouter(prefix="/api/stats", tags=["stats"])

_VALID_BUCKET = {"hour", "day"}
_VALID_RANGE = {"24h", "7d", "30d"}


@router.get("/overview")
def overview(date: str | None = None, session: Session = Depends(get_session)) -> dict:
    return stats_service.overview(session, date)


@router.get("/timeseries")
def timeseries(
    bucket: str = Query("hour"),
    range: str = Query("24h"),
    camera_id: str = Query("ALL"),
    session: Session = Depends(get_session),
) -> dict:
    if bucket not in _VALID_BUCKET:
        raise ValidationError(f"bucket 非法：{bucket!r}，应为 {sorted(_VALID_BUCKET)}")
    if range not in _VALID_RANGE:
        raise ValidationError(f"range 非法：{range!r}，应为 {sorted(_VALID_RANGE)}")
    return stats_service.timeseries(session, bucket=bucket, range_key=range, camera_id=camera_id)


@router.get("/by-camera")
def by_camera(range: str = Query("24h"), session: Session = Depends(get_session)) -> dict:
    if range not in _VALID_RANGE:
        raise ValidationError(f"range 非法：{range!r}，应为 {sorted(_VALID_RANGE)}")
    return stats_service.by_camera(session, range_key=range)


@router.get("/forecast")
def forecast(camera_id: str = Query("ALL"), session: Session = Depends(get_session)) -> dict:
    return stats_service.forecast(session, camera_id=camera_id)
