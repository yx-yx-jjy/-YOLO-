"""台账仓储层：只封装 CRUD 与查询，不含业务规则（业务规则在 services）。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db.mapping import parse_camera_label
from ..db.models import Disposition, DispositionHistory, ReviewHistory, ViolationRecord


def insert_record(session: Session, columns: dict) -> ViolationRecord:
    row = ViolationRecord(**columns)
    session.add(row)
    session.flush()
    return row


def get_by_id(session: Session, record_id: str) -> ViolationRecord | None:
    return session.get(ViolationRecord, record_id)


def _filters(conditions: list, filters: dict) -> tuple[list, bool]:
    need_disposition_join = False
    status = filters.get("status")
    if status and status != "all":
        conditions.append(ViolationRecord.status == status)

    camera_id = filters.get("camera_id")
    if camera_id and camera_id != "all":
        key, _ = parse_camera_label(camera_id)
        conditions.append(ViolationRecord.camera_key == (key or camera_id))

    category = filters.get("category")
    if category and category != "all":
        conditions.append(ViolationRecord.category == category)

    if filters.get("start_time"):
        conditions.append(ViolationRecord.capture_time >= filters["start_time"])
    if filters.get("end_time"):
        conditions.append(ViolationRecord.capture_time <= filters["end_time"])
    if filters.get("min_confidence") is not None:
        conditions.append(ViolationRecord.confidence >= filters["min_confidence"])
    if filters.get("max_confidence") is not None:
        conditions.append(ViolationRecord.confidence <= filters["max_confidence"])

    keyword = filters.get("keyword")
    if keyword:
        like = f"%{keyword}%"
        conditions.append(
            or_(
                ViolationRecord.id.like(like),
                ViolationRecord.camera_label.like(like),
                ViolationRecord.plate_or_vehicle.like(like),
                ViolationRecord.reviewer.like(like),
            )
        )

    disposition_status = filters.get("disposition_status")
    if disposition_status and disposition_status != "all":
        need_disposition_join = True
        conditions.append(Disposition.status == disposition_status)

    return conditions, need_disposition_join


def list_records(session: Session, filters: dict, page: int, page_size: int) -> tuple[list, int]:
    conditions, join_needed = _filters([], filters)

    base = select(ViolationRecord)
    count_base = select(func.count(ViolationRecord.id))
    if join_needed:
        base = base.join(Disposition, Disposition.violation_id == ViolationRecord.id)
        count_base = count_base.join(Disposition, Disposition.violation_id == ViolationRecord.id)

    for condition in conditions:
        base = base.where(condition)
        count_base = count_base.where(condition)

    total = session.execute(count_base).scalar_one()

    sort = filters.get("sort") or "capture_time_desc"
    if sort == "capture_time_asc":
        base = base.order_by(ViolationRecord.capture_time.asc(), ViolationRecord.id.asc())
    elif sort == "confidence_desc":
        base = base.order_by(ViolationRecord.confidence.desc(), ViolationRecord.capture_time.desc())
    elif sort == "confidence_asc":
        base = base.order_by(ViolationRecord.confidence.asc(), ViolationRecord.capture_time.desc())
    else:
        base = base.order_by(ViolationRecord.capture_time.desc(), ViolationRecord.id.desc())

    offset = (page - 1) * page_size
    rows = session.execute(base.offset(offset).limit(page_size)).scalars().all()
    return list(rows), int(total)


def get_review_history(session: Session, record_id: str) -> list[ReviewHistory]:
    return list(
        session.execute(
            select(ReviewHistory)
            .where(ReviewHistory.violation_id == record_id)
            .order_by(ReviewHistory.seq.asc())
        ).scalars()
    )


def review_history_by_ids(session: Session, ids: list[str]) -> dict[str, list[ReviewHistory]]:
    if not ids:
        return {}
    rows = session.execute(
        select(ReviewHistory)
        .where(ReviewHistory.violation_id.in_(ids))
        .order_by(ReviewHistory.seq.asc())
    ).scalars()
    grouped: dict[str, list[ReviewHistory]] = {rid: [] for rid in ids}
    for row in rows:
        grouped.setdefault(row.violation_id, []).append(row)
    return grouped


def get_disposition(session: Session, record_id: str) -> Disposition | None:
    return session.get(Disposition, record_id)


def dispositions_by_ids(session: Session, ids: list[str]) -> dict[str, Disposition]:
    if not ids:
        return {}
    rows = session.execute(select(Disposition).where(Disposition.violation_id.in_(ids))).scalars()
    return {row.violation_id: row for row in rows}


def get_disposition_history(session: Session, record_id: str) -> list[DispositionHistory]:
    return list(
        session.execute(
            select(DispositionHistory)
            .where(DispositionHistory.violation_id == record_id)
            .order_by(DispositionHistory.seq.asc())
        ).scalars()
    )


def disposition_history_by_ids(session: Session, ids: list[str]) -> dict[str, list[DispositionHistory]]:
    if not ids:
        return {}
    rows = session.execute(
        select(DispositionHistory)
        .where(DispositionHistory.violation_id.in_(ids))
        .order_by(DispositionHistory.seq.asc())
    ).scalars()
    grouped: dict[str, list[DispositionHistory]] = {rid: [] for rid in ids}
    for row in rows:
        grouped.setdefault(row.violation_id, []).append(row)
    return grouped


def next_review_seq(session: Session, record_id: str) -> int:
    value = session.execute(
        select(func.max(ReviewHistory.seq)).where(ReviewHistory.violation_id == record_id)
    ).scalar()
    return int(value or 0) + 1


def next_disposition_seq(session: Session, record_id: str) -> int:
    value = session.execute(
        select(func.max(DispositionHistory.seq)).where(DispositionHistory.violation_id == record_id)
    ).scalar()
    return int(value or 0) + 1
