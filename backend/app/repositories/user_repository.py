"""用户仓储层。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import User


def get_by_id(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def get_by_username(session: Session, username: str) -> User | None:
    return session.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()


def get_by_badge(session: Session, badge: str) -> User | None:
    if not badge:
        return None
    return session.execute(select(User).where(User.badge_number == badge)).scalar_one_or_none()


def list_users(session: Session, filters: dict, page: int, page_size: int) -> tuple[list, int]:
    conditions = []
    if filters.get("role") and filters["role"] != "all":
        conditions.append(User.role == filters["role"])
    if filters.get("status") and filters["status"] != "all":
        conditions.append(User.status == filters["status"])

    base = select(User)
    count_base = select(func.count(User.id))
    for condition in conditions:
        base = base.where(condition)
        count_base = count_base.where(condition)

    total = session.execute(count_base).scalar_one()
    base = base.order_by(User.id.asc())
    offset = (page - 1) * page_size
    rows = session.execute(base.offset(offset).limit(page_size)).scalars().all()
    return list(rows), int(total)


def username_exists(session: Session, username: str) -> bool:
    return session.execute(select(func.count(User.id)).where(User.username == username)).scalar_one() > 0


def badge_exists(session: Session, badge: str) -> bool:
    return session.execute(select(func.count(User.id)).where(User.badge_number == badge)).scalar_one() > 0


def create_user(session: Session, **fields) -> User:
    row = User(**fields)
    session.add(row)
    session.flush()
    return row


def all_users(session: Session) -> list[User]:
    return list(session.execute(select(User).order_by(User.id.asc())).scalars())
