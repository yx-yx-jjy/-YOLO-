"""汇总统计服务（架构稿 §4.2）。

口径严格对齐前端现有派生逻辑，集中在本模块，杜绝"多处各写一个数"。

关于 overview：§4.2 的映射表把 ScreenDashboard 的 `reviewPanel.*` 映射到 `overview`，
而 `reviewPanel` 是**全量台账**口径（total = 全部记录数）。因此 overview 的
total/status/low_confidence/review_rate 为**全量**口径；同时提供 `today_total`
供大屏"今日"口径使用；`date` 字段回显请求日期（默认今天）。这是把"契约 §4.2 的
date 参数"与"映射表的全量口径"两者调和后的实现，若后续要求 date 严格生效，
只需把聚合条件换成 capture_time LIKE date% 即可。
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from ..db.models import Disposition, ViolationRecord
from ..repositories.camera_repository import list_cameras
from ..repositories.record_repository import _filters  # 仅复用筛选语义（camera_key 解析）
from ..timeutil import day_key, format_time, local_now, now_str

# 「低置信度」的阈值，必须与前端 frontend/src/utils/confidence.js 的
# CONFIDENCE_CUTOFF.mid 保持一致（全站唯一口径）。
#
# ⚠️ 为什么不是常见的 0.70：本项目的「判定可信度」取的是**证据链中最弱环节**的
# 检测置信度（app/rules.py 的 min()），而瓶颈是小目标 —— 头部在 1920 宽的卡口画面
# 里往往只有几十像素，检测置信度天然偏低。实测 861 条真实抓拍：P25=0.43、
# 中位数 0.52、P75=0.63、最高仅 0.71。若沿用 0.70，会把 90% 的记录都算成
# 低置信度，这个指标就失去区分意义。这里按真实分布的四分位点标定为 0.43。
LOW_CONFIDENCE_THRESHOLD = 0.43
_RANGE_DAYS = {"24h": 1, "7d": 7, "30d": 30}


def _cutoff(range_key: str) -> str:
    days = _RANGE_DAYS.get(range_key, 7)
    return format_time(local_now() - timedelta(days=days))


def _camera_key(camera_id: str | None) -> str | None:
    if not camera_id or camera_id == "ALL":
        return None
    conditions, _ = _filters([], {"camera_id": camera_id})
    if conditions:
        # conditions[0] 形如 ViolationRecord.camera_key == key；取其右值
        try:
            return conditions[0].right.value
        except Exception:  # noqa: BLE001
            return camera_id
    return camera_id


def overview(session: Session, date: str | None = None) -> dict:
    target_date = date or day_key()

    total = session.execute(select(func.count(ViolationRecord.id))).scalar_one()

    status_rows = session.execute(
        select(ViolationRecord.status, func.count(ViolationRecord.id)).group_by(ViolationRecord.status)
    ).all()
    status_map = {row[0]: int(row[1]) for row in status_rows}
    status = {
        "pending": status_map.get("pending", 0),
        "approved": status_map.get("approved", 0),
        "rejected": status_map.get("rejected", 0),
    }

    disp_rows = session.execute(
        select(Disposition.status, func.count(Disposition.violation_id))
        .where(Disposition.status.is_not(None))
        .group_by(Disposition.status)
    ).all()
    disp_map = {row[0]: int(row[1]) for row in disp_rows}
    disposition = {
        "to_notify": disp_map.get("to_notify", 0),
        "notified": disp_map.get("notified", 0),
        "disposed": disp_map.get("disposed", 0),
        "archived": disp_map.get("archived", 0),
    }
    disposed_done = disposition["disposed"] + disposition["archived"]

    low_conf = session.execute(
        select(func.count(ViolationRecord.id)).where(ViolationRecord.confidence < LOW_CONFIDENCE_THRESHOLD)
    ).scalar_one()
    avg_conf = session.execute(select(func.avg(ViolationRecord.confidence))).scalar()

    today_total = session.execute(
        select(func.count(ViolationRecord.id)).where(
            ViolationRecord.capture_time.like(f"{target_date}%")
        )
    ).scalar_one()

    reviewed = status["approved"] + status["rejected"]
    return {
        "date": target_date,
        "total": int(total),
        "today_total": int(today_total),
        "status": status,
        "disposition": disposition,
        "review_rate": round(reviewed / total * 100) if total else 0,
        "disposition_rate": round(disposed_done / status["approved"] * 100) if status["approved"] else 0,
        "low_confidence": int(low_conf),
        "avg_confidence": round((avg_conf or 0) * 100),
        "generated_at": now_str(),
    }


def timeseries(session: Session, bucket: str = "hour", range_key: str = "24h", camera_id: str = "ALL") -> dict:
    if bucket not in ("hour", "day"):
        bucket = "hour"
    key = _camera_key(camera_id)
    cutoff = _cutoff(range_key)

    if bucket == "hour":
        expr = func.substr(ViolationRecord.capture_time, 12, 2)
        stmt = select(expr, func.count(ViolationRecord.id)).where(ViolationRecord.capture_time >= cutoff)
        if key:
            stmt = stmt.where(ViolationRecord.camera_key == key)
        rows = session.execute(stmt.group_by(expr)).all()
        counts = {f"{row[0]}:00": int(row[1]) for row in rows if row[0]}
        keys = [f"{h:02d}:00" for h in range(24)]
        series_name = "未佩戴头盔"
        return {
            "bucket": "hour",
            "keys": keys,
            "series": [{"name": series_name, "data": [counts.get(k, 0) for k in keys]}],
        }

    # bucket == day
    days = _RANGE_DAYS.get(range_key, 7)
    expr = func.substr(ViolationRecord.capture_time, 1, 10)
    stmt = select(expr, func.count(ViolationRecord.id)).where(ViolationRecord.capture_time >= cutoff)
    if key:
        stmt = stmt.where(ViolationRecord.camera_key == key)
    rows = session.execute(stmt.group_by(expr)).all()
    counts = {row[0]: int(row[1]) for row in rows if row[0]}

    keys: list[str] = []
    values: list[int] = []
    now = local_now()
    for offset in range(days - 1, -1, -1):
        day = now - timedelta(days=offset)
        keys.append(day.strftime("%m-%d"))
        values.append(counts.get(day.strftime("%Y-%m-%d"), 0))
    return {
        "bucket": "day",
        "keys": keys,
        "series": [{"name": "未佩戴头盔", "data": values}],
    }


def by_camera(session: Session, range_key: str = "24h") -> dict:
    cutoff = _cutoff(range_key)
    rows = session.execute(
        select(
            ViolationRecord.camera_key,
            func.count(ViolationRecord.id),
            func.sum(
                func.iif(ViolationRecord.helmet_status == "not_wearing", 1, 0)
            ),
            func.avg(ViolationRecord.confidence),
            func.max(ViolationRecord.capture_time),
        )
        .where(ViolationRecord.capture_time >= cutoff)
        .where(ViolationRecord.camera_key.is_not(None))
        .group_by(ViolationRecord.camera_key)
    ).all()

    names = {cam.camera_key: cam.name for cam in list_cameras(session)}
    items = []
    for camera_key, total, no_helmet, avg_conf, last_time in rows:
        items.append({
            "camera_id": camera_key,
            "name": names.get(camera_key, camera_key),
            "total": int(total or 0),
            "no_helmet": int(no_helmet or 0),
            "avg_confidence": round((avg_conf or 0) * 100),
            "last_capture_time": last_time,
        })
    items.sort(key=lambda item: item["total"], reverse=True)
    return {"items": items}


def forecast(session: Session, camera_id: str = "ALL") -> dict:
    """研判页口径：近 5 小时真实值 + 近 7 天"同一时刻"均值外推（架构稿 §4.2）。"""
    key = _camera_key(camera_id)
    stmt: Select = select(ViolationRecord.capture_time)
    if key:
        stmt = stmt.where(ViolationRecord.camera_key == key)
    times = [row[0] for row in session.execute(stmt).all()]

    now = local_now()
    today = day_key(now)

    def hour_of(text: str) -> int | None:
        try:
            return int(text[11:13])
        except (ValueError, IndexError):
            return None

    history_keys: list[str] = []
    history_values: list[int] = []
    for offset in range(4, -1, -1):
        hour = (now.hour - offset + 24) % 24
        history_keys.append(f"{hour:02d}:00")
        history_values.append(
            sum(1 for text in times if text[:10] == today and hour_of(text) == hour)
        )

    forecast_keys: list[str] = []
    forecast_values: list[int] = []
    for step in range(1, 4):
        hour = (now.hour + step) % 24
        forecast_keys.append(f"{hour:02d}:00（预）")
        week_total = sum(1 for text in times if hour_of(text) == hour)
        forecast_values.append(round(week_total / 7))

    return {
        "history": {"keys": history_keys, "values": history_values},
        "forecast": {"keys": forecast_keys, "values": forecast_values},
    }
