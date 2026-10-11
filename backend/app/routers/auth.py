"""认证 REST：登录（架构稿 §4.3）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db.engine import get_session
from ..schemas import LoginPayload
from ..services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.post("/login")
def login(
    payload: LoginPayload, request: Request, session: Session = Depends(get_session)
) -> dict:
    return auth_service.login(
        session, payload.username, payload.password, ip=_client_ip(request)
    )
