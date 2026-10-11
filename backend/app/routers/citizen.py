"""公众服务端接口：我的记录、我的车辆、线索上报。

与执法后台的关系（刻意划清）
--------------------------
· **读**：只返回当前登录市民**绑定车牌**名下、且已通过人工复核入卷的记录。
  未复核的算法线索一律不返回——线索不是违法事实，不能让群众看到。
· **写**：举报只进 `public_reports` 线索池，**不写violation_records**，
  未经执法人员核验绝不进入正式台账。举报单没有处罚权，这是产品红线。
"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db.engine import get_session
from ..deps import require_auth
from ..services.errors import ConflictError, ForbiddenError, ValidationError
from ..services.serializers import record_to_api

router = APIRouter(prefix="/api/citizen", tags=["citizen"])

_PAGE_SIZE_MAX = 50


def _require_citizen(claims: dict) -> int:
    """群众端只允许 role=citizen 访问。

    注意：执法人员登录后**不能**用这个接口查自己的记录——
    台账是执法侧的完整视图，个人记录是「只看自己名下」的受限视图，
    两者语义不同，混用会让权限边界说不清。
    """
    if claims.get("role") != "citizen":
        raise ForbiddenError("该接口仅面向普通市民开放", hint="请使用群众端演示账号登录")
    return int(claims["user_id"])


def _my_plates(session: Session, user_id: int) -> list[str]:
    rows = session.execute(
        text("SELECT plate_no FROM citizen_vehicles WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchall()
    return [r[0] for r in rows]


@router.get("/my-records")
def my_records(
    request: Request,
    claims: dict = Depends(require_auth),
    session: Session = Depends(get_session),
) -> dict:
    """当前市民绑定车牌名下的违法记录（只读）。

    返回 { plates, total, items }。
    items 复用台账的 record_to_api，保证「群众看到的」与「民警看到的」字段口径一致，
    不会出现同一件事两种说法。
    """
    user_id = _require_citizen(claims)
    plates = _my_plates(session, user_id)

    if not plates:
        # 没绑车牌不是错误，是正常状态——可能本人名下没有登记在册的非机动车
        return {"plates": [], "total": 0, "items": []}

    placeholders = ", ".join(f":p{i}" for i in range(len(plates)))
    params: dict = {f"p{i}": p for i, p in enumerate(plates)}
    params["limit"] = _PAGE_SIZE_MAX

    rows = session.execute(
        text(
            f"""
            SELECT vr.*,
                   d.status        AS d_status,
                   d.method        AS d_method,
                   d.notified_at   AS d_notified_at,
                   d.disposed_at   AS d_disposed_at,
                   d.handler       AS d_handler,
                   d.remark        AS d_remark
            FROM violation_records vr
            LEFT JOIN dispositions d ON d.violation_id = vr.id
            WHERE UPPER(vr.plate_no) IN ({placeholders})
              AND vr.status = 'approved'
            ORDER BY vr.capture_time DESC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()

    items = []
    for row in rows:
        record = _row_to_api(row)
        if record:
            items.append(record)

    return {"plates": plates, "total": len(items), "items": items}


@router.get("/my-vehicles")
def my_vehicles(
    claims: dict = Depends(require_auth),
    session: Session = Depends(get_session),
) -> dict:
    """当前市民绑定的号牌。"""
    user_id = _require_citizen(claims)
    rows = session.execute(
        text(
            "SELECT plate_no, plate_kind, binding_at FROM citizen_vehicles "
            "WHERE user_id = :uid ORDER BY binding_at DESC"
        ),
        {"uid": user_id},
    ).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.post("/reports")
def submit_report(
    payload: dict,
    request: Request,
    claims: dict = Depends(require_auth),
    session: Session = Depends(get_session),
) -> dict:
    """公众线索上报。只写 public_reports，**不触碰台账**。

    单人单日上限 10 条，防止刷举报把执法人员队列淹掉。
    """
    user_id = _require_citizen(claims)

    location = str(payload.get("location") or "").strip()
    occurred_at = str(payload.get("occurred_at") or "").strip()
    report_type = str(payload.get("report_type") or "helmet").strip()
    description = str(payload.get("description") or "").strip()[:500]

    if not location:
        raise ValidationError("请填写发生地点")
    if not occurred_at:
        raise ValidationError("请填写发生时间")

    today = datetime.now().strftime("%Y-%m-%d")
    used = session.execute(
        text(
            "SELECT COUNT(*) FROM public_reports "
            "WHERE reporter_id = :uid AND created_at LIKE :day"
        ),
        {"uid": user_id, "day": f"{today}%"},
    ).scalar_one()
    if used >= 10:
        raise ConflictError("今日上报已达上限，请明日再试", hint="如有紧急情况可直接拨打 122")

    report_id = f"RPT-{datetime.now():%Y%m%d}-{user_id}{used:02d}"
    session.execute(
        text(
            """
            INSERT INTO public_reports
                (id, reporter_id, report_type, occurred_at, camera_id,
                 location_text, description, status, created_at)
            VALUES
                (:id, :uid, :rtype, :occurred, '', :loc, :desc, 'submitted',
                 datetime('now','localtime'))
            """
        ),
        {
            "id": report_id,
            "uid": user_id,
            "rtype": report_type,
            "occurred": occurred_at,
            "loc": location,
            "desc": description,
        },
    )
    session.commit()

    return {
        "id": report_id,
        "status": "submitted",
        "message": "已提交，交警将尽快核查",
    }


@router.get("/my-reports")
def my_reports(
    claims: dict = Depends(require_auth),
    session: Session = Depends(get_session),
) -> dict:
    """当前市民提交过的线索及其核查状态。"""
    user_id = _require_citizen(claims)
    rows = session.execute(
        text(
            """
            SELECT id, report_type, occurred_at, location_text, description,
                   status, review_note, created_at
            FROM public_reports
            WHERE reporter_id = :uid
            ORDER BY created_at DESC
            LIMIT 50
            """
        ),
        {"uid": user_id},
    ).mappings().all()
    return {"items": [dict(r) for r in rows]}


def _row_to_api(row) -> dict | None:
    """复用台账序列化，保证两端字段口径一致。

    与 serializers.record_to_api 的差别：这里的 disposition 是 JOIN 出来的，
    所以在这里补齐，避免改动执法侧的既有序列化行为。
    """

    class _Rec:
        pass

    rec = _Rec()
    for k in row.keys():
        if k.startswith("d_"):
            continue
        setattr(rec, k, row[k])

    data = record_to_api(rec)
    d_status = row["d_status"]
    data["disposition"] = {
        "status": d_status,
        "method": row["d_method"] or "",
        "notified_at": row["d_notified_at"] or "",
        "disposed_at": row["d_disposed_at"] or "",
        "handler": row["d_handler"] or "",
        "remark": row["d_remark"] or "",
        "history": [],
    }
    # 群众端不需要内部复核轨迹
    data.pop("review_history", None)
    return data