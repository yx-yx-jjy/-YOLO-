"""台账读取视图：把 ORM 记录 + 轨迹拼装成 API Record。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..repositories import record_repository as rec_repo
from .serializers import record_to_api


def full_record(session: Session, record) -> dict:
    return record_to_api(
        record,
        rec_repo.get_review_history(session, record.id),
        rec_repo.get_disposition(session, record.id),
        rec_repo.get_disposition_history(session, record.id),
    )


def records_page(session: Session, rows: list, total: int, page: int, page_size: int) -> dict:
    """列表页批量加载轨迹，避免 N+1。"""
    ids = [row.id for row in rows]
    review_map = rec_repo.review_history_by_ids(session, ids)
    disp_map = rec_repo.dispositions_by_ids(session, ids)
    disp_hist_map = rec_repo.disposition_history_by_ids(session, ids)
    items = [
        record_to_api(row, review_map.get(row.id, []), disp_map.get(row.id), disp_hist_map.get(row.id, []))
        for row in rows
    ]
    pages = (total + page_size - 1) // page_size if page_size else 0
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}
