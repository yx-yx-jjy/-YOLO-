"""ORM 对象 → API 契约对象的序列化（严格对齐架构稿 §4 的字段名）。"""
from __future__ import annotations

from ..db.mapping import details_from_columns, derive_source


EMPTY_DISPOSITION = {
    "status": None,
    "method": "",
    "notified_at": "",
    "disposed_at": "",
    "handler": "",
    "remark": "",
    "history": [],
}


def review_history_to_api(rows) -> list[dict]:
    return [
        {
            "action": row.action,
            "reviewer": row.reviewer,
            "badge": row.badge,
            "remark": row.remark,
            "time": row.event_time,  # event_time → time（前端契约）
        }
        for row in rows
    ]


def disposition_to_api(row, history_rows) -> dict:
    if row is None:
        return {**EMPTY_DISPOSITION, "history": []}
    return {
        "status": row.status,
        "method": row.method or "",
        "notified_at": row.notified_at or "",
        "disposed_at": row.disposed_at or "",
        "handler": row.handler or "",
        "remark": row.remark or "",
        "history": [
            {
                "action": item.action,
                "operator": item.operator,
                "remark": item.remark,
                "time": item.event_time,
            }
            for item in history_rows
        ],
    }


def record_to_api(record_row, review_rows=None, disposition_row=None, disp_history_rows=None) -> dict:
    return {
        "id": record_row.id,
        "camera_id": record_row.camera_label,  # 原始串，前端 cameraKey() 前缀解析
        "camera_key": record_row.camera_key,
        "track_id": record_row.track_id,
        "violation_type": record_row.violation_type,
        "category": record_row.category,
        "confidence": record_row.confidence,
        "status": record_row.status,
        "reviewer": record_row.reviewer,
        "review_time": record_row.review_time,
        "review_remark": record_row.review_remark or "",
        "capture_time": record_row.capture_time,
        "evidence_url": record_row.evidence_url,
        "roi_url": record_row.roi_url,
        "source": derive_source(record_row.id),
        "details": details_from_columns(record_row),
        "review_history": review_history_to_api(review_rows or []),
        "disposition": disposition_to_api(disposition_row, disp_history_rows or []),
    }


def user_to_api(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "badge_number": user.badge_number,
        "role": user.role,
        "status": user.status,
        "department": user.department or "",
        # 注意：DB 列是 last_login_at，前端读的是 last_login（做映射）
        "last_login": user.last_login_at,
    }


def log_to_api(log) -> dict:
    return {
        "id": log.id,
        "time": log.event_time,  # DB 列 event_time → 前端 log.time
        "operator": log.operator,
        "role": log.role,
        "action_type": log.action_type,
        "details": log.details,
        "ip": log.ip,
        # 额外字段（前端"哈希已存证"据此展示真实链值），不影响旧契约
        "target_type": log.target_type,
        "target_id": log.target_id,
        "entry_hash": log.entry_hash,
        "prev_hash": log.prev_hash,
    }


def camera_to_api(cam) -> dict:
    return {
        "id": cam.camera_key,
        "name": cam.name,
        "area": cam.area,
        "coords": [cam.latitude, cam.longitude],  # [lat, lng]，WGS84
        "heat_radius": cam.heat_radius,
        "active": bool(cam.is_active),
    }
