"""复核状态机（架构稿 §1.3 链路 B）与批量复核。

状态机：pending → approved / rejected；approved / rejected → pending（撤销）。
非法跃迁（如对 pending 再 revoke、对已 approved 再 approve）返回 409。

**关键写入顺序**（系统架构师硬约束）：复核通过时必须
  1) 先 UPDATE violation_records 置 approved（写 reviewer / review_time）
  2) 再 UPDATE dispositions 置 to_notify
反序会被 schema.sql 的 T2 触发器 ABORT。
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..db.models import DispositionHistory, ReviewHistory
from ..repositories import record_repository as rec_repo
from ..repositories import system_log_repository as log_repo
from ..repositories import user_repository as user_repo
from ..timeutil import now_str
from . import record_view
from .errors import ConflictError, NotFoundError, ServiceError, ValidationError
from .locking import WRITE_LOCK

logger = logging.getLogger("traffic.services.review")

ACTIONS = {"approve", "reject", "revoke"}

CATEGORY_VIOLATION_TYPE = {"helmet": "未按规定佩戴安全头盔"}

DEFAULT_REMARK = {
    "approve": "人工复核无误，违规事实成立已锁定入卷",
    "reject": "经人工复核，属于非违规误报或环境干扰，已剔除",
}


def _resolve_user_id(session: Session, badge: str | None):
    if badge:
        user = user_repo.get_by_badge(session, badge)
        if user:
            return user.id
    return None


def _reset_disposition(session: Session, record_id: str, operator: str, remark: str) -> None:
    """把处置当前态重置为 NULL，并向处置轨迹**追加**一条 revoke（不删历史）。"""
    disposition = rec_repo.get_disposition(session, record_id)
    if disposition is None or disposition.status is None:
        return
    disposition.status = None
    disposition.method = ""
    disposition.notified_at = ""
    disposition.disposed_at = ""
    disposition.handler = ""
    disposition.remark = ""
    disposition.updated_at = now_str()
    session.add(
        DispositionHistory(
            violation_id=record_id,
            seq=rec_repo.next_disposition_seq(session, record_id),
            action="revoke",
            operator=operator,
            remark=remark,
            event_time=now_str(),
        )
    )


def _add_review_history(
    session: Session, record_id: str, action: str, reviewer: str, badge: str, remark: str, event_time: str
) -> None:
    session.add(
        ReviewHistory(
            violation_id=record_id,
            seq=rec_repo.next_review_seq(session, record_id),
            action=action,
            reviewer=reviewer or "",
            badge=badge or "",
            remark=remark or "",
            event_time=event_time,
        )
    )


def apply_review(session: Session, record_id: str, payload: dict) -> dict:
    action = (payload.get("action") or "").strip()
    if action not in ACTIONS:
        raise ValidationError(f"action 非法：{action!r}，应为 {sorted(ACTIONS)}")
    reviewer = (payload.get("reviewer") or "").strip()
    if not reviewer:
        raise ValidationError("复核操作必须携带 reviewer（操作人署名）")
    badge = payload.get("badge") or ""
    remark = (payload.get("remark") or "").strip()
    category_override = payload.get("category_override")

    with WRITE_LOCK:
        record = rec_repo.get_by_id(session, record_id)
        if record is None:
            raise NotFoundError(f"台账记录不存在：{record_id}")

        now = now_str()
        if action == "approve":
            if record.status == "approved":
                raise ConflictError("该记录已确认入卷，如需修改请先撤销复核")
            previous_category = record.category
            final_remark = remark or DEFAULT_REMARK["approve"]
            if category_override and category_override != previous_category:
                # 本系统只做头盔佩戴判定，category 恒为 helmet（软枚举，见 schema.sql:143）。
                # 非法值直接拒收，不能用 CATEGORY_VIOLATION_TYPE.get() 兜底——那会让
                # category 与 violation_type 静默脱钩，写进不可篡改的复核留痕。
                if category_override not in CATEGORY_VIOLATION_TYPE:
                    raise ValidationError(
                        f"不支持的违规类别：{category_override}；"
                        f"当前系统仅支持 {sorted(CATEGORY_VIOLATION_TYPE)}"
                    )
                record.category = category_override
                record.violation_type = CATEGORY_VIOLATION_TYPE[category_override]
                final_remark = f"{final_remark}（复核修正违规类型：{previous_category} → {category_override}）"
            record.status = "approved"
            record.reviewer = reviewer
            record.review_time = now
            record.review_remark = final_remark
            record.updated_at = now
            # 1) 先落地台账 approved，满足 T2 触发器的前置校验
            session.flush()
            # 2) 再推进处置当前态 NULL → to_notify
            disposition = rec_repo.get_disposition(session, record_id)
            if disposition is not None and disposition.status is None:
                disposition.status = "to_notify"
                disposition.updated_at = now
                session.add(
                    DispositionHistory(
                        violation_id=record_id,
                        seq=rec_repo.next_disposition_seq(session, record_id),
                        action="create",
                        operator=reviewer,
                        remark="复核确认入卷，转入处置流程（待告知当事人）",
                        event_time=now,
                    )
                )
            _add_review_history(session, record_id, "approve", reviewer, badge, final_remark, now)
            log_repo.append_log(
                session,
                event_time=now,
                operator=reviewer,
                role="officer",
                action_type="REVIEW_APPROVE",
                details=f"对违规单 {record_id} 执行人工复核：判定违规有效并入库",
                user_id=_resolve_user_id(session, badge),
                target_type="violation",
                target_id=record_id,
            )

        elif action == "reject":
            if record.status == "rejected":
                raise ConflictError("该记录已是误报剔除状态")
            final_remark = remark or DEFAULT_REMARK["reject"]
            record.status = "rejected"
            record.reviewer = reviewer
            record.review_time = now
            record.review_remark = final_remark
            record.updated_at = now
            session.flush()
            _reset_disposition(session, record_id, reviewer, "复核改判为误报，退出处置流程")
            _add_review_history(session, record_id, "reject", reviewer, badge, final_remark, now)
            log_repo.append_log(
                session,
                event_time=now,
                operator=reviewer,
                role="officer",
                action_type="REVIEW_REJECT",
                details=f"对违规单 {record_id} 执行人工复核：判定为误报并剔除",
                user_id=_resolve_user_id(session, badge),
                target_type="violation",
                target_id=record_id,
            )

        else:  # revoke
            if record.status == "pending":
                raise ConflictError("该记录尚未复核，无需撤销")
            previous = "已确认入卷" if record.status == "approved" else "误报已剔除"
            final_remark = remark or f"撤销原判定（{previous}），退回待复核"
            record.status = "pending"
            record.reviewer = None
            record.review_time = None
            record.review_remark = ""
            record.updated_at = now
            session.flush()
            _reset_disposition(session, record_id, reviewer, "撤销复核，处置流程回退")
            _add_review_history(session, record_id, "revoke", reviewer, badge, final_remark, now)
            log_repo.append_log(
                session,
                event_time=now,
                operator=reviewer,
                role="officer",
                action_type="REVIEW_REVOKE",
                details=f"对违规单 {record_id} 执行复核撤销：退回待复核",
                user_id=_resolve_user_id(session, badge),
                target_type="violation",
                target_id=record_id,
            )

        session.commit()
        session.expire_all()
        record = rec_repo.get_by_id(session, record_id)
        return record_view.full_record(session, record)


def batch_review(session: Session, payload: dict) -> dict:
    action = (payload.get("action") or "").strip()
    ids = payload.get("ids") or []
    if not isinstance(ids, list) or not ids:
        raise ValidationError("ids 不能为空")

    reviewer = (payload.get("reviewer") or "").strip()
    badge = payload.get("badge") or ""
    remark = payload.get("remark") or ""

    succeeded: list[str] = []
    failed: list[dict] = []

    if action in ("approve", "reject", "revoke"):
        for record_id in ids:
            try:
                apply_review(
                    session,
                    record_id,
                    {"action": action, "reviewer": reviewer, "badge": badge, "remark": remark},
                )
                succeeded.append(record_id)
            except ServiceError as exc:  # 预期内的业务错误：直接把可读 message 回给调用方
                session.rollback()
                failed.append({"id": record_id, "reason": exc.message})
            except Exception as exc:  # noqa: BLE001 - 单条失败不影响其余
                session.rollback()
                # 未预期异常（如 DB 约束）：不透传原始异常串，只回稳定文案，原始栈写日志
                logger.error("批量复核单条失败 id=%s：%s", record_id, exc, exc_info=True)
                failed.append({"id": record_id, "reason": "处理失败，请稍后重试"})
        return {"succeeded": succeeded, "failed": failed}

    if action == "notify":
        # 前端「批量告知当事人」走 disposition 的 notify
        from . import disposition_service

        for record_id in ids:
            try:
                disposition_service.apply_disposition(
                    session,
                    record_id,
                    {"action": "notify", "operator": reviewer, "remark": remark},
                )
                succeeded.append(record_id)
            except ServiceError as exc:  # 预期内的业务错误（如状态机冲突）
                session.rollback()
                failed.append({"id": record_id, "reason": exc.message})
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                logger.error("批量告知单条失败 id=%s：%s", record_id, exc, exc_info=True)
                failed.append({"id": record_id, "reason": "处理失败，请稍后重试"})
        return {"succeeded": succeeded, "failed": failed}

    raise ValidationError(f"batch-review 的 action 非法：{action!r}")
