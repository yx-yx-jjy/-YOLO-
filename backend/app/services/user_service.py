"""用户管理服务（新增账号 / 冻结解冻 / 重置密码）。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..repositories import system_log_repository as log_repo
from ..repositories import user_repository as user_repo
from ..security import hash_password
from ..timeutil import now_str
from .errors import ConflictError, NotFoundError, ValidationError
from .locking import WRITE_LOCK
from .serializers import user_to_api

INITIAL_PASSWORD = "123456"
VALID_ROLES = {"officer", "admin"}
VALID_STATUS = {"active", "disabled"}


def list_users(session: Session, filters: dict, page: int, page_size: int) -> dict:
    rows, total = user_repo.list_users(session, filters, page, page_size)
    pages = (total + page_size - 1) // page_size if page_size else 0
    return {
        "items": [user_to_api(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


def create_user(session: Session, payload: dict, ip: str = "") -> dict:
    username = (payload.get("username") or "").strip()
    real_name = (payload.get("real_name") or "").strip()
    badge = (payload.get("badge_number") or "").strip()
    role = (payload.get("role") or "officer").strip()
    department = (payload.get("department") or "").strip()
    password = payload.get("password") or INITIAL_PASSWORD

    if not username or not real_name or not badge:
        raise ValidationError("username / real_name / badge_number 均为必填")
    if role not in VALID_ROLES:
        raise ValidationError(f"role 非法：{role!r}，应为 {sorted(VALID_ROLES)}")
    if user_repo.username_exists(session, username):
        raise ConflictError(f"登录用户名已存在：{username}")
    if user_repo.badge_exists(session, badge):
        raise ConflictError(f"警号已存在：{badge}")

    with WRITE_LOCK:
        user = user_repo.create_user(
            session,
            username=username,
            real_name=real_name,
            badge_number=badge,
            role=role,
            status="active",
            department=department,
            password_hash=hash_password(password),
        )
        log_repo.append_log(
            session,
            event_time=now_str(),
            operator="系统管理员",
            role="admin",
            action_type="USER_CREATE",
            details=f"新增执法账号：{real_name} ({badge})，角色 {role}",
            target_type="user",
            target_id=str(user.id),
            ip=ip,
        )
        session.commit()
        session.expire_all()
        user = user_repo.get_by_id(session, user.id)
    return user_to_api(user)


def set_status(session: Session, user_id: int, payload: dict, ip: str = "") -> dict:
    target = payload.get("status")
    if not target and payload.get("action"):
        action = str(payload["action"]).lower()
        target = {"freeze": "disabled", "unfreeze": "active"}.get(action)
    if target not in VALID_STATUS:
        raise ValidationError("status 非法，应为 active / disabled（或 action: freeze / unfreeze）")

    with WRITE_LOCK:
        user = user_repo.get_by_id(session, user_id)
        if user is None:
            raise NotFoundError(f"用户不存在：{user_id}")
        user.status = target
        user.updated_at = now_str()
        log_repo.append_log(
            session,
            event_time=now_str(),
            operator="系统管理员",
            role="admin",
            action_type="USER_STATUS_CHANGE",
            details=f"{'冻结' if target == 'disabled' else '解冻'}账号：{user.real_name} ({user.badge_number})",
            target_type="user",
            target_id=str(user.id),
            ip=ip,
        )
        session.commit()
        session.expire_all()
        user = user_repo.get_by_id(session, user_id)
    return user_to_api(user)


def reset_password(session: Session, user_id: int, ip: str = "") -> dict:
    with WRITE_LOCK:
        user = user_repo.get_by_id(session, user_id)
        if user is None:
            raise NotFoundError(f"用户不存在：{user_id}")
        user.password_hash = hash_password(INITIAL_PASSWORD)
        user.updated_at = now_str()
        log_repo.append_log(
            session,
            event_time=now_str(),
            operator="系统管理员",
            role="admin",
            action_type="USER_RESET_PASSWORD",
            details=f"重置密码为初始密码：{user.real_name} ({user.badge_number})",
            target_type="user",
            target_id=str(user.id),
            ip=ip,
        )
        session.commit()
    return {"id": user_id, "username": user.username, "message": f"已重置为初始密码 {INITIAL_PASSWORD}"}
