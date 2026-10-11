"""演示补数据：为「近 N 小时无违规记录」的卡口补一批台账。

⚠️ 与 seed_ledger.py 的关系
    seed_ledger.py 是 demoDataset.js 的**位精确移植**，参与 reconcile_seed.py 对账，
    其数据分布不可改动。本脚本**不参与对账**，是一条独立的"演示补数"通道：
    用途是让大屏 / 研判页的 5 个卡口在**时间窗口口径**下都有数据可展示，
    因为近期的实时抓拍可能只覆盖了其中 3 个卡口。

⚠️ 数据性质
    本脚本写入的是**合成演示数据**（非真实抓拍），仅用于界面演示，
    不得作为真实统计或论文实测数据引用。

用法（在 backend 目录、用 backend/.venv）：
    python scripts/seed_demo_fill.py --dry-run          # 只看计划，不写库
    python scripts/seed_demo_fill.py                    # 按默认计划补数据
    python scripts/seed_demo_fill.py --plan CAM-04=240,CAM-05=150
    python scripts/seed_demo_fill.py --hours 24 --now "2026-10-10 10:00:00"
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for _p in (BACKEND_DIR, SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from sqlalchemy import func, select  # noqa: E402

import seed_ledger as sl  # noqa: E402  复用常量与随机源，保证字段风格一致
from app.db import engine as db_engine  # noqa: E402
from app.db.mapping import record_to_columns  # noqa: E402
from app.db.models import ReviewHistory, ViolationRecord  # noqa: E402
from app.db.state import db_state  # noqa: E402
from app.repositories import system_log_repository as log_repo  # noqa: E402
from app.timeutil import format_time, parse_time  # noqa: E402

# 补数使用的 id 流水段：seed_ledger 每天从 1 起、边界样本用 9001~9004，
# 这里取 7000 段避开，且记录来源仍按 "EV-<日期>-<4位十进制>" 识别为演示记录。
SEQ_BASE = 7000

# 默认计划：把 24h 窗口内为 0 的两个卡口补到"低于 CAM-01 但清晰可见"的量级
DEFAULT_PLAN = {"CAM-04": 240, "CAM-05": 150}


def parse_plan(text: str | None) -> dict[str, int]:
    if not text:
        return dict(DEFAULT_PLAN)
    plan: dict[str, int] = {}
    for chunk in text.split(","):
        if not chunk.strip():
            continue
        cam, _, num = chunk.partition("=")
        plan[cam.strip()] = int(num)
    return plan


def window_counts(session, hours: int, now: datetime) -> dict[str, int]:
    """各卡口在 [now-hours, now] 内的记录数（与大屏 /stats/by-camera 口径一致）。"""
    since = format_time(now - timedelta(hours=hours))
    rows = session.execute(
        select(ViolationRecord.camera_key, func.count(ViolationRecord.id))
        .where(ViolationRecord.capture_time >= since)
        .group_by(ViolationRecord.camera_key)
    ).all()
    out: dict[str, int] = {}
    for key, n in rows:
        if not key:
            continue
        out[key[:6]] = out.get(key[:6], 0) + n
    return out


def build_fill(plan: dict[str, int], now: datetime, hours: int, seed: int) -> list[dict]:
    _rand, pick, rand_int, _rf, _ph, pick_conf = sl.make_generators(seed)
    name_of = {c["id"]: c["name"] for c in sl.CAMERAS}
    span = max(10, hours * 60 - 10)
    records: list[dict] = []

    for cam_id, count in plan.items():
        if cam_id not in name_of:
            print(f"[warn] 计划中的卡口 {cam_id} 不在 CAMERAS 里，已跳过")
            continue
        for _ in range(count):
            captured = now - timedelta(minutes=rand_int(5, span))
            roll = _rand()
            status = "pending" if roll < 0.45 else ("approved" if roll < 0.90 else "rejected")
            reviewed = status != "pending"
            review_time = captured + timedelta(minutes=rand_int(4, 90))
            if review_time > now:
                review_time = now

            record = {
                "camera_id": f"{cam_id}-{pick(sl.DIRECTIONS)}",
                "track_id": rand_int(20, 980),
                "violation_type": "未按规定佩戴安全头盔",
                "category": "helmet",
                "confidence": pick_conf(),
                "status": status,
                "reviewer": pick(sl.REVIEWERS) if reviewed else None,
                "review_time": format_time(review_time) if reviewed else None,
                "review_remark": (
                    pick(sl.REMARK_APPROVE if status == "approved" else sl.REMARK_REJECT)
                    if reviewed else ""
                ),
                "capture_time": format_time(captured),
            }
            record["details"] = {
                "helmet_status": "not_wearing",
                "consecutive_frames": rand_int(3, 12),
                "plate_or_vehicle": pick(sl.VEHICLE_POOL),
            }
            record["_date"] = captured.date()
            records.append(record)
    return records


def allocate_ids(session, records: list[dict]) -> None:
    """按 capture 日期分配 7000 段的唯一流水号（避开已有 id）。"""
    dates = {r["_date"] for r in records}
    used: set[str] = set()
    for d in dates:
        prefix = f"EV-{d.year:04d}{d.month:02d}{d.day:02d}-"
        for (rid,) in session.execute(
            select(ViolationRecord.id).where(ViolationRecord.id.like(prefix + "%"))
        ):
            used.add(rid)
    counters = {d: SEQ_BASE for d in dates}
    for r in records:
        d = r["_date"]
        while True:
            counters[d] += 1
            rid = sl.stamp_id(d, counters[d])
            if rid not in used:
                used.add(rid)
                r["id"] = rid
                break


def insert_records(session, records: list[dict]) -> None:
    for record in records:
        session.add(ViolationRecord(**record_to_columns(record)))
        session.flush()  # 触发 T1：自动补一行 dispositions(status=NULL)
        if record["status"] != "pending" and record.get("reviewer"):
            session.add(ReviewHistory(
                violation_id=record["id"],
                seq=1,
                action="approve" if record["status"] == "approved" else "reject",
                reviewer=record["reviewer"],
                badge="",
                remark=record.get("review_remark") or "",
                event_time=record["review_time"] or record["capture_time"],
            ))
    session.commit()


def insert_logs(session, records: list[dict]) -> int:
    """仅为新增记录的复核动作追加系统日志（含哈希链），不重复写登录/导出日志。"""
    entries = []
    for record in records:
        if record["status"] == "pending" or not record.get("reviewer"):
            continue
        entries.append({
            "event_time": record["review_time"] or record["capture_time"],
            "operator": record["reviewer"],
            "role": "officer",
            "action_type": "REVIEW_APPROVE" if record["status"] == "approved" else "REVIEW_REJECT",
            "details": (
                f"对违规单 {record['id']} 执行人工复核："
                + ("判定违规有效并入库" if record["status"] == "approved" else "判定为误报并剔除")
            ),
            "user_id": sl._user_id_for_badge(session, sl._review_badge(record["reviewer"])),
            "target_type": "violation",
            "target_id": record["id"],
            "ip": "192.168.10.42",
        })
    entries.sort(key=lambda item: (item["event_time"], item["action_type"]))
    for entry in entries:
        log_repo.append_log(session, **entry)
    session.commit()
    return len(entries)


def main() -> int:
    ap = argparse.ArgumentParser(description="为近期无数据的卡口补演示台账")
    ap.add_argument("--plan", default=None, help="形如 CAM-04=240,CAM-05=150；默认 " + str(DEFAULT_PLAN))
    ap.add_argument("--hours", type=int, default=24, help="时间窗口小时数，默认 24（对齐大屏口径）")
    ap.add_argument("--now", default=None, help="固定生成时刻 'YYYY-MM-DD HH:MM:SS'")
    ap.add_argument("--seed", type=int, default=20261010, help="随机种子（默认 20261010）")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不写库")
    args = ap.parse_args()

    db_engine.init_db()
    if not db_state.ready:
        print(f"[error] 数据库不可用：{db_state.reason} / {db_state.message}")
        return 1

    now = parse_time(args.now) if args.now else datetime.now()
    if now is None:
        print(f"[error] --now 格式应为 'YYYY-MM-DD HH:MM:SS'，收到：{args.now!r}")
        return 1

    with db_engine.session_scope() as session:
        counts = window_counts(session, args.hours, now)

    print(f"[info] now = {format_time(now)}，窗口 = 近 {args.hours} 小时")
    print(f"[info] 窗口内各卡口：{ {c['id']: counts.get(c['id'], 0) for c in sl.CAMERAS} }")

    plan = parse_plan(args.plan)
    fill = {cam: n for cam, n in plan.items() if counts.get(cam, 0) == 0}
    skipped = {cam: n for cam, n in plan.items() if cam not in fill}
    if skipped:
        print(f"[skip] 这些卡口窗口内已有数据，不补：{ {c: counts.get(c, 0) for c in skipped} }")
    if not fill:
        print("[done] 无需补数据。")
        return 0
    print(f"[plan] 将补：{fill}（合计 {sum(fill.values())} 条合成演示数据）")

    if args.dry_run:
        print("[dry-run] 未写库。")
        return 0

    records = build_fill(fill, now, args.hours, args.seed)

    with db_engine.session_scope() as session:
        allocate_ids(session, records)
        insert_records(session, records)
    with db_engine.session_scope() as session:
        log_count = insert_logs(session, records)

    with db_engine.session_scope() as session:
        after = window_counts(session, args.hours, now)
        total = session.execute(select(func.count(ViolationRecord.id))).scalar_one()

    print("\n===== 演示补数据完成 =====")
    print(f"新增台账      : {len(records)}（已复核日志 {log_count} 条）")
    print(f"窗口内各卡口  : { {c['id']: after.get(c['id'], 0) for c in sl.CAMERAS} }")
    print(f"台账总数      : {total}")
    print("⚠️ 以上为合成演示数据，勿作真实统计引用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
