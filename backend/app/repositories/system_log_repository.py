"""系统日志仓储层（哈希链，只追加）。

哈希链（schema.sql）：
    prev_hash  = 上一条日志的 entry_hash（创世为 ''）
    entry_hash = sha256(prev_hash + 本条内容)

并发约束（02-设计 §3.6 / 系统架构师要求）：prev_hash 依赖上一条 entry_hash，
而写日志的请求来自线程池，**必须串行追加**。做法见 services 里的 _WRITE_LOCK：
读 prev_hash → 计算 → INSERT → commit 全程持锁。DB 侧另有
idx_system_logs_prev_hash_unique（部分唯一索引）兜底：若仍分叉会直接报错。
"""
from __future__ import annotations

import hashlib

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import SystemLog


def _canonical(
    prev_hash: str,
    event_time: str,
    operator: str,
    role: str,
    action_type: str,
    details: str,
    target_id: str | None,
    ip: str,
) -> str:
    return "|".join([
        prev_hash,
        event_time,
        operator,
        role,
        action_type,
        details,
        target_id or "",
        ip,
    ])


def compute_entry_hash(prev_hash: str, **fields) -> str:
    return hashlib.sha256(_canonical(prev_hash, **fields).encode("utf-8")).hexdigest()


def last_entry_hash(session: Session) -> str:
    # 先 flush，确保同一事务内先前追加的日志可见（sessionmaker autoflush=False）
    session.flush()
    value = session.execute(
        select(SystemLog.entry_hash).order_by(SystemLog.id.desc()).limit(1)
    ).scalar()
    return value or ""


def append_log(
    session: Session,
    *,
    event_time: str,
    operator: str,
    role: str,
    action_type: str,
    details: str,
    user_id: int | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    ip: str = "",
) -> SystemLog:
    prev_hash = last_entry_hash(session)
    entry_hash = compute_entry_hash(
        prev_hash,
        event_time=event_time,
        operator=operator,
        role=role,
        action_type=action_type,
        details=details,
        target_id=target_id,
        ip=ip,
    )
    row = SystemLog(
        event_time=event_time,
        operator=operator,
        user_id=user_id,
        role=role,
        action_type=action_type,
        details=details,
        target_type=target_type,
        target_id=target_id,
        ip=ip,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    session.add(row)
    session.flush()
    return row


def list_logs(session: Session, filters: dict, page: int, page_size: int) -> tuple[list, int]:
    conditions = []
    if filters.get("action_type") and filters["action_type"] != "all":
        conditions.append(SystemLog.action_type == filters["action_type"])
    if filters.get("operator"):
        conditions.append(SystemLog.operator.like(f"%{filters['operator']}%"))
    if filters.get("start_time"):
        conditions.append(SystemLog.event_time >= filters["start_time"])
    if filters.get("end_time"):
        conditions.append(SystemLog.event_time <= filters["end_time"])

    base = select(SystemLog)
    count_base = select(func.count(SystemLog.id))
    for condition in conditions:
        base = base.where(condition)
        count_base = count_base.where(condition)

    total = session.execute(count_base).scalar_one()
    base = base.order_by(SystemLog.event_time.desc(), SystemLog.id.desc())
    offset = (page - 1) * page_size
    rows = session.execute(base.offset(offset).limit(page_size)).scalars().all()
    return list(rows), int(total)
