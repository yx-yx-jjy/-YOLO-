"""处置状态机（复核入卷之后的"后半程"）。

状态机：to_notify → notified → disposed → archived。
只有 status='approved' 的记录才允许进入处置（schema.sql 的 T2 触发器在 DB 层强制）。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import Disposition, DispositionHistory
from ..repositories import record_repository as rec_repo
from ..repositories import system_log_repository as log_repo
from ..timeutil import now_str
from . import record_view
from .errors import ConflictError, NotFoundError, ValidationError
from .locking import WRITE_LOCK

ACTIONS = {"notify", "dispose", "archive"}

DEFAULT_REMARK = {
    "notify": "已告知当事人违法事实、处理依据与办理地点",
    "dispose": "处理结果已执行完毕",
    "archive": "处理结果已执行完毕，证据材料归档入卷",
}

_LOG_ACTION = {
    "notify": ("DISPOSITION_NOTIFY", "告知当事人"),
    "dispose": ("DISPOSITION_DISPOSE", "作出处理"),
    "archive": ("DISPOSITION_ARCHIVE", "结案归档"),
}


def _add_history(session: Session, record_id: str, action: str, operator: str, remark: str, event_time: str) -> None:
    session.add(
        DispositionHistory(
            violation_id=record_id,
            seq=rec_repo.next_disposition_seq(session, record_id),
            action=action,
            operator=operator or "",
            remark=remark or "",
            event_time=event_time,
        )
    )


def apply_disposition(session: Session, record_id: str, payload: dict) -> dict:
    action = (payload.get("action") or "").strip()
    if action not in ACTIONS:
        raise ValidationError(f"action 非法：{action!r}，应为 {sorted(ACTIONS)}")
    operator = (payload.get("operator") or "").strip()
    if not operator:
        raise ValidationError("处置操作必须携带 operator（承办人）")
    method = (payload.get("method") or "").strip()
    remark = (payload.get("remark") or "").strip()

    with WRITE_LOCK:
        record = rec_repo.get_by_id(session, record_id)
        if record is None:
            raise NotFoundError(f"台账记录不存在：{record_id}")
        if record.status != "approved":
            raise ConflictError("只有『已确认入卷』的记录才能进入处置流程")

        disposition = rec_repo.get_disposition(session, record_id)
        if disposition is None:
            # 正常情况下 T1 触发器会建行；这里兜底显式建一行（status=NULL）
            disposition = Disposition(violation_id=record_id)
            session.add(disposition)
            session.flush()

        now = now_str()
        current = disposition.status if disposition else None

        if action == "notify":
            if current != "to_notify":
                raise ConflictError(f"当前处置状态为 {current!r}，不能执行『告知』（应处于待告知）")
            disposition.status = "notified"
            disposition.notified_at = now
            disposition.handler = operator
            disposition.remark = remark or DEFAULT_REMARK["notify"]
            disposition.updated_at = now
            _add_history(session, record_id, "notify", operator, disposition.remark, now)

        elif action == "dispose":
            if current not in ("to_notify", "notified"):
                raise ConflictError(f"当前处置状态为 {current!r}，不能执行『处理』")
            if not disposition.notified_at:
                # 之前没告知的自动补一条轨迹，状态链不留空档
                disposition.notified_at = now
                _add_history(session, record_id, "notify", operator, DEFAULT_REMARK["notify"], now)
            disposition.status = "disposed"
            disposition.method = method or disposition.method or ""
            disposition.disposed_at = now
            disposition.handler = operator
            disposition.remark = remark or DEFAULT_REMARK["dispose"]
            disposition.updated_at = now
            _add_history(session, record_id, "dispose", operator, disposition.remark, now)

        else:  # archive
            if current == "archived":
                raise ConflictError("该记录已归档")
            if current is None:
                raise ConflictError("该记录尚未进入处置流程，不能归档")
            # 状态机：to_notify → notified → disposed → archived，归档必须已完成「处理」。
            # 【D1 修正】此前未做前置校验，从 to_notify 直接归档会触发 dispositions 的
            # CHECK（archived 要求 notified_at 与 disposed_at 均非空）抛出 IntegrityError，
            # 被兜底中间件误判成 503。这里显式判前置状态 → 409（与"重复 approve"同一条路径）。
            if current != "disposed":
                raise ConflictError(
                    f"当前处置状态为 {current!r}，不能归档（须先完成『处理』，即 status=disposed）"
                )
            disposition.status = "archived"
            disposition.handler = operator
            disposition.remark = remark or disposition.remark or DEFAULT_REMARK["archive"]
            disposition.updated_at = now
            _add_history(session, record_id, "archive", operator, "证据材料与处理结果已归档入卷", now)

        log_action, label = _LOG_ACTION[action]
        log_repo.append_log(
            session,
            event_time=now,
            operator=operator,
            role="officer",
            action_type=log_action,
            details=f"对违规单 {record_id} 执行处置动作：{label}",
            target_type="violation",
            target_id=record_id,
        )

        session.commit()
        session.expire_all()
        record = rec_repo.get_by_id(session, record_id)
        return record_view.full_record(session, record)
