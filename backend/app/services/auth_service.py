"""登录服务（架构稿 §4.3）。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..repositories import system_log_repository as log_repo
from ..repositories import user_repository as user_repo
from ..security import create_token, verify_password
from ..timeutil import now_str
from .errors import ForbiddenError, UnauthorizedError
from .locking import WRITE_LOCK
from .serializers import user_to_api


def login(session: Session, username: str, password: str, ip: str = "") -> dict:
    username = (username or "").strip()
    if not username or not password:
        raise UnauthorizedError("账号或密码错误")

    user = user_repo.get_by_username(session, username)
    if user is None or not verify_password(password, user.password_hash):
        # 不区分"账号不存在"与"密码错误"，避免账号枚举
        raise UnauthorizedError("账号或密码错误")
    if user.status != "active":
        raise ForbiddenError("账号已被冻结，请联系管理员")

    with WRITE_LOCK:
        now = now_str()
        user.last_login_at = now
        user.updated_at = now
        log_repo.append_log(
            session,
            event_time=now,
            operator=f"{user.real_name} ({user.badge_number})",
            role=user.role,
            action_type="USER_LOGIN",
            details="登录非机动车违法检测系统后台",
            user_id=user.id,
            target_type="user",
            target_id=str(user.id),
            ip=ip,
        )
        session.commit()
        session.expire_all()
        user = user_repo.get_by_username(session, username)

    token = create_token(user.id, user.username, user.role)
    return {"token": token, "user": user_to_api(user)}
