"""管理 REST：用户、系统日志、卡口主数据（架构稿 §4.3-4.5）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ..db.engine import get_session
from ..deps import require_auth
from ..repositories import camera_repository as camera_repo
from ..repositories import system_log_repository as log_repo
from ..schemas import CreateUserPayload, StatusPayload
from ..services import user_service
from ..services.serializers import camera_to_api, log_to_api

router = APIRouter(prefix="/api", tags=["admin"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    role: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    return user_service.list_users(
        session, {"role": role, "status": status}, page, page_size
    )


@router.post("/users", status_code=201, dependencies=[Depends(require_auth)])
def create_user(
    payload: CreateUserPayload, request: Request, session: Session = Depends(get_session)
) -> dict:
    return user_service.create_user(session, payload.model_dump(), ip=_client_ip(request))


@router.patch("/users/{user_id}/status", dependencies=[Depends(require_auth)])
def set_user_status(
    user_id: int, payload: StatusPayload, request: Request, session: Session = Depends(get_session)
) -> dict:
    return user_service.set_status(session, user_id, payload.model_dump(), ip=_client_ip(request))


@router.post("/users/{user_id}/reset-password", dependencies=[Depends(require_auth)])
def reset_password(
    user_id: int, request: Request, session: Session = Depends(get_session)
) -> dict:
    return user_service.reset_password(session, user_id, ip=_client_ip(request))


@router.get("/system-logs")
def list_system_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    action_type: str | None = None,
    operator: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    rows, total = log_repo.list_logs(
        session,
        {
            "action_type": action_type,
            "operator": operator,
            "start_time": start_time,
            "end_time": end_time,
        },
        page,
        page_size,
    )
    pages = (total + page_size - 1) // page_size if page_size else 0
    return {
        "items": [log_to_api(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.get("/cameras")
def list_cameras(session: Session = Depends(get_session)) -> dict:
    return {"items": [camera_to_api(cam) for cam in camera_repo.list_cameras(session)]}
