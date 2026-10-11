"""一次性数据导入：把 existing 7 天演示台账灌入 SQLite（架构稿 §7.2）。

忠实移植 deliverables/db-migration/reference/demoDataset.js 的生成算法
（原 frontend/src/mock/demoDataset.js，已退役迁出 src）：
  · mulberry32(20260930)（已与 Node 位精确对齐）
  · HOUR_WEIGHTS / PREV_DAY_COUNTS / TODAY_TARGET=190 / DAYS=7
  · VEHICLE_POOL / REVIEWERS / REMARK_APPROVE / REMARK_REJECT / 置信度三档
  · buildEdgeCases 的 4 条边界样本（26/53/78/112 分钟前）
  · 处置状态机用**独立种子** mulberry32(20261002)，计划时间轴与 now 比较决定停在哪一步
另灌入 3 个用户、5 条卡口（schema.sql 已内置，不重复插）、并**按台账复核动作真实生成**
系统日志（含哈希链）。

**与 demoDataset.js 的唯一有意偏差（缺陷修正）**：demoDataset.js 只过滤「今日未来抓拍」，
未约束复核时间；今日记录若抓拍时刻贴近 now，其 review_time 会落到未来。本脚本在**取完整份
记录的随机数之后、生成处置时间轴之前**，把 review_time **clamp 到 now**（见 main() 内注释），
不消耗任何随机数，故其余字段、整份分布与 JS 逐条一致。

用法（在 backend 目录、用 backend/.venv）：
    python scripts/seed_ledger.py            # 幂等：表已有数据则跳过
    python scripts/seed_ledger.py --force    # 先 drop+recreate 全部表再重灌（不删库文件）
    python scripts/seed_ledger.py --reset    # 删除 traffic.db 后重建再灌
"""
from __future__ import annotations

import argparse
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import engine as db_engine  # noqa: E402
from app.db.mapping import record_to_columns  # noqa: E402
from app.db.models import (  # noqa: E402
    Disposition,
    DispositionHistory,
    ReviewHistory,
    SystemLog,
    User,
    ViolationRecord,
)
from app.db.state import db_state  # noqa: E402
from app.repositories import system_log_repository as log_repo  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.timeutil import format_time, parse_time  # noqa: E402

# ── demoDataset.js 常量（逐字移植） ──────────────────────────────────────
SEED = 20260930
DAYS = 7
TODAY_TARGET = 190
PREV_DAY_COUNTS = [92, 104, 86, 118, 96, 132]
HOUR_WEIGHTS = [
    1, 0.6, 0.4, 0.3, 0.4, 1.2, 4, 9, 12, 6, 4, 4,
    5, 4, 3.5, 4, 7, 11, 9, 6, 4, 3, 2.5, 1.5,
]
DIRECTIONS = ["东向非机动车道", "西向非机动车道", "南向非机动车道", "北向非机动车道"]
REVIEWERS = [
    "张警官 (警号: 08412)",
    "李警官 (警号: 08419)",
    "王警官 (警号: 08427)",
]
VEHICLE_POOL = [
    "白色雅迪电瓶车 [无牌照]",
    "深蓝轻便电摩 [鄂A·E8821]",
    "绿色外卖配送电动车",
    "红色电动三轮/踏板车",
    "灰色九号智能电动车",
    "黑色小牛电动踏板车 [鄂A·D3097]",
    "银灰电动自行车 [号牌污损不可辨识]",
    "蓝色共享助力车",
    "黄色闪送配送电动车 [鄂A·F2210]",
]
REMARK_APPROVE = [
    "驾驶人头部完全裸露，未佩戴任何护具，复核无误",
    "骑行人员未佩戴头盔事实清楚，确认入卷",
    "头部区域清晰，未检测到安全头盔，确认入卷",
    "连续多帧取证完整，违规事实成立",
]
REMARK_REJECT = [
    "误报剔除：佩戴防风毛线帽/遮阳帽，头部已有防护",
    "雨夜反光导致头部特征丢失，判定为非违规",
    "头部被随车货物遮挡，无法确认，剔除",
    "遮挡严重，无法确认头部特征，剔除",
]
CAMERAS = [
    {"id": "CAM-03", "name": "建设大道-香港路口"},
    {"id": "CAM-01", "name": "珞喻路-光谷广场口"},
    {"id": "CAM-02", "name": "解放大道-新华路口"},
    {"id": "CAM-04", "name": "武珞路-中南路口"},
    {"id": "CAM-05", "name": "钟家村-鹦鹉大道口"},
]

DISPOSITION_SEED = 20261002
DISPOSITION_METHODS = [
    {"method": "罚款处罚", "remark": "按《道路交通安全法》相关条款处以罚款，处罚决定书已送达当事人"},
    {"method": "警告处罚", "remark": "首次违规且情节轻微，予以警告并现场教育纠正"},
    {"method": "安全教育学习", "remark": "责令参加交通安全教育学习，已完成签到与结业登记"},
    {"method": "现场拦查处置", "remark": "已通知路面警力拦查，当场纠正违法行为并登记"},
]
DISPOSITION_HANDLERS = [
    "张建国 (警号: 08412)",
    "李文博 (警号: 08419)",
    "王海涛 (警号: 08427)",
]
DISPOSITION_DEFAULT = {
    "status": None,
    "method": "",
    "notified_at": "",
    "disposed_at": "",
    "handler": "",
    "remark": "",
    "history": [],
}

SEED_USERS = [
    # id, username, real_name, badge, role, department, last_login, password
    (1, "officer_zhang", "张建国 (警官)", "08412", "officer", "交警支队一大队执勤一中队", "2026-09-29 19:40:12", "123456"),
    (2, "officer_li", "李志强 (警官)", "08419", "officer", "交警支队一大队违章处理科", "2026-09-29 18:22:45", "123456"),
    (3, "admin_super", "刘主任 (系统管理员)", "ADMIN-01", "admin", "交管科技信息指挥中心", "2026-09-29 20:01:05", "admin888"),
]


def mulberry32(seed: int):
    a = seed & 0xFFFFFFFF

    def imul(x: int, y: int) -> int:
        return ((x & 0xFFFFFFFF) * (y & 0xFFFFFFFF)) & 0xFFFFFFFF

    def rng() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = a
        t = imul(t ^ (t >> 15), t | 1)
        t = (t ^ ((t + imul(t ^ (t >> 7), t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rng


def _to_fixed2(value: float) -> float:
    # 近似 JS Number(x.toFixed(2))：四舍五入到 2 位小数
    return math.floor(value * 100 + 0.5) / 100


def make_generators(seed: int):
    rng = mulberry32(seed)

    def rand() -> float:
        return rng()

    def pick(items):
        return items[int(rand() * len(items))]

    def rand_int(min_v: int, max_v: int) -> int:
        return min_v + int(rand() * (max_v - min_v + 1))

    def rand_float(min_v: float, max_v: float) -> float:
        return min_v + rand() * (max_v - min_v)

    def pick_hour() -> int:
        total = sum(HOUR_WEIGHTS)
        point = rand() * total
        for hour, weight in enumerate(HOUR_WEIGHTS):
            point -= weight
            if point <= 0:
                return hour
        return len(HOUR_WEIGHTS) - 1

    def pick_confidence() -> float:
        roll = rand()
        if roll < 0.12:
            return _to_fixed2(rand_float(0.36, 0.69))
        if roll < 0.42:
            return _to_fixed2(rand_float(0.70, 0.89))
        return _to_fixed2(rand_float(0.90, 0.99))

    return rand, pick, rand_int, rand_float, pick_hour, pick_confidence


def stamp_id(day: date, seq: int) -> str:
    return f"EV-{day.year:04d}{day.month:02d}{day.day:02d}-{seq:04d}"


def build_records(now: datetime) -> list[dict]:
    _rand, pick, rand_int, _rand_float, pick_hour, pick_confidence = make_generators(SEED)
    output: list[dict] = []

    for offset in range(DAYS - 1, -1, -1):
        is_today = offset == 0
        target = TODAY_TARGET if is_today else PREV_DAY_COUNTS[DAYS - 1 - offset]
        base = date(now.year, now.month, now.day) - timedelta(days=offset)
        seq = 1

        for _ in range(target):
            hour = pick_hour()
            minute = rand_int(0, 59)
            second = rand_int(0, 59)
            captured = datetime(base.year, base.month, base.day, hour, minute, second)

            cam = CAMERAS[int(_rand() * len(CAMERAS))]
            confidence = pick_confidence()

            status_roll = _rand()
            if is_today:
                status = "pending" if status_roll < 0.55 else ("approved" if status_roll < 0.90 else "rejected")
            else:
                status = "pending" if status_roll < 0.06 else ("approved" if status_roll < 0.90 else "rejected")
            reviewed = status != "pending"
            review_time = captured + timedelta(minutes=rand_int(4, 90))

            # 注意：字典字面量按插入顺序求值，务必与 demoDataset.js 的属性顺序一致，
            # 否则随机数消耗错位，整份台账字段全乱。
            record = {
                "id": stamp_id(base, seq),
                "camera_id": f"{cam['id']}-{pick(DIRECTIONS)}",
                "track_id": rand_int(20, 980),
                "violation_type": "未按规定佩戴安全头盔",
                "category": "helmet",
                "confidence": confidence,
                "status": status,
                "reviewer": pick(REVIEWERS) if reviewed else None,
                "review_time": format_time(review_time) if reviewed else None,
                "review_remark": (
                    pick(REMARK_APPROVE if status == "approved" else REMARK_REJECT) if reviewed else ""
                ),
                "capture_time": format_time(captured),
            }
            # details 与 JS 的 buildDetails() 顺序一致：consecutive_frames → plate_or_vehicle
            record["details"] = {
                "helmet_status": "not_wearing",
                "consecutive_frames": rand_int(3, 12),
                "plate_or_vehicle": pick(VEHICLE_POOL),
            }

            if is_today and captured > now:
                # 必须等整条记录建完再过滤（随机数已消耗），与 JS 注释一致
                continue
            output.append(record)
            seq += 1

    return output


def build_edge_cases(now: datetime) -> list[dict]:
    def back(minutes: int) -> str:
        return format_time(now - timedelta(minutes=minutes))

    def id_of(minutes: int, seq: int) -> str:
        return stamp_id((now - timedelta(minutes=minutes)).date(), seq)

    return [
        {
            "id": id_of(26, 9001), "camera_id": "CAM-04-南向非机动车道", "track_id": 411,
            "violation_type": "未按规定佩戴安全头盔", "category": "helmet", "confidence": 0.38,
            "status": "pending", "reviewer": None, "review_time": None, "review_remark": "",
            "capture_time": back(26),
            "details": {"helmet_status": "not_wearing", "consecutive_frames": 3,
                        "plate_or_vehicle": "银灰电动自行车 [号牌污损不可辨识]"},
        },
        {
            "id": id_of(53, 9002), "camera_id": "CAM-02-北向非机动车道", "track_id": 377,
            "violation_type": "未按规定佩戴安全头盔", "category": "helmet", "confidence": 0.52,
            "status": "rejected", "reviewer": "张警官 (警号: 08412)", "review_time": back(41),
            "review_remark": "雨夜反光导致头部特征丢失，判定为非违规", "capture_time": back(53),
            "details": {"helmet_status": "not_wearing", "consecutive_frames": 4,
                        "plate_or_vehicle": "绿色外卖配送电动车"},
        },
        {
            "id": id_of(78, 9003), "camera_id": "CAM-03-东向非机动车道", "track_id": 502,
            "violation_type": "未按规定佩戴安全头盔", "category": "helmet", "confidence": 0.93,
            "status": "approved", "reviewer": "李警官 (警号: 08419)", "review_time": back(70),
            "review_remark": "头部区域清晰，未佩戴安全头盔，确认入卷", "capture_time": back(78),
            "details": {"helmet_status": "not_wearing", "consecutive_frames": 11,
                        "plate_or_vehicle": "红色电动三轮/踏板车"},
        },
        {
            "id": id_of(112, 9004), "camera_id": "CAM-05-西向非机动车道", "track_id": 268,
            "violation_type": "未按规定佩戴安全头盔", "category": "helmet", "confidence": 0.64,
            "status": "pending", "reviewer": None, "review_time": None, "review_remark": "",
            "capture_time": back(112),
            "details": {"helmet_status": "not_wearing", "consecutive_frames": 5,
                        "plate_or_vehicle": "遮挡严重 · 无法辨识车身特征"},
        },
    ]


def build_dispositions(records: list[dict], now: datetime) -> None:
    """按 **独立种子** 的处置随机源，顺序与 records（已按 capture_time 倒序）一致。"""
    _rand, pick, _ri, _rf, _ph, _pc = make_generators(DISPOSITION_SEED)

    for record in records:
        if record["status"] != "approved":
            record["disposition"] = {**DISPOSITION_DEFAULT, "history": []}
            continue

        reviewed = parse_time(record["review_time"]) or parse_time(record["capture_time"])
        notify_plan = reviewed + timedelta(hours=0.5 + _rand() * 18)
        dispose_plan = notify_plan + timedelta(hours=1 + _rand() * 6)
        archive_plan = dispose_plan + timedelta(hours=12 + _rand() * 72)

        stage = "to_notify"
        if now >= archive_plan:
            stage = "archived"
        elif now >= dispose_plan:
            stage = "disposed"
        elif now >= notify_plan:
            stage = "notified"

        item = DISPOSITION_METHODS[int(_rand() * len(DISPOSITION_METHODS))]
        handler = DISPOSITION_HANDLERS[int(_rand() * len(DISPOSITION_HANDLERS))]

        has_notified = stage != "to_notify"
        has_disposed = stage in ("disposed", "archived")
        notified_text = format_time(notify_plan)
        disposed_text = format_time(dispose_plan)

        history = []
        if has_notified:
            history.append({
                "action": "notify",
                "operator": record["reviewer"] or handler,
                "remark": f"已告知当事人违法事实、处理依据与办理地点（{record['camera_id']}）",
                "time": notified_text,
            })
        if has_disposed:
            history.append({"action": "dispose", "operator": handler, "remark": item["remark"], "time": disposed_text})
        if stage == "archived":
            history.append({
                "action": "archive", "operator": handler,
                "remark": "处理结果已执行完毕，证据材料归档入卷", "time": format_time(archive_plan),
            })

        record["disposition"] = {
            "status": stage,
            "method": item["method"] if has_disposed else "",
            "notified_at": notified_text if has_notified else "",
            "disposed_at": disposed_text if has_disposed else "",
            "handler": handler if has_notified else "",
            "remark": item["remark"] if has_disposed else ("已告知当事人，等待处理结果" if has_notified else ""),
            "history": history,
        }


def _review_badge(reviewer: str | None) -> str:
    for badge in ("08412", "08419", "08427"):
        if reviewer and badge in reviewer:
            return badge
    return ""


def _user_id_for_badge(session, badge: str):
    if not badge:
        return None
    row = session.execute(select(User.id).where(User.badge_number == badge)).scalar()
    return row


def seed_records(session, records: list[dict]) -> None:
    for record in records:
        columns = record_to_columns(record)
        session.add(ViolationRecord(**columns))
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

        disposition = record.get("disposition") or {**DISPOSITION_DEFAULT, "history": []}
        if disposition.get("status"):
            row = session.get(Disposition, record["id"])
            row.status = disposition["status"]
            row.method = disposition.get("method") or ""
            row.notified_at = disposition.get("notified_at") or ""
            row.disposed_at = disposition.get("disposed_at") or ""
            row.handler = disposition.get("handler") or ""
            row.remark = disposition.get("remark") or ""
            for seq, event in enumerate(disposition.get("history") or [], start=1):
                session.add(DispositionHistory(
                    violation_id=record["id"],
                    seq=seq,
                    action=event["action"],
                    operator=event.get("operator") or "",
                    remark=event.get("remark") or "",
                    event_time=event["time"],
                ))

    session.commit()


def seed_users(session) -> None:
    for uid, username, real_name, badge, role, department, last_login, password in SEED_USERS:
        session.add(User(
            id=uid,
            username=username,
            real_name=real_name,
            badge_number=badge,
            role=role,
            status="active",
            department=department,
            password_hash=hash_password(password),
            last_login_at=last_login,
        ))
    session.commit()


def seed_logs(session, records: list[dict]) -> int:
    """按台账复核动作真实生成日志，并计算哈希链（升序追加）。"""
    entries: list[dict] = []

    for record in records:
        if record["status"] == "pending" or not record.get("reviewer"):
            continue
        badge = _review_badge(record["reviewer"])
        entries.append({
            "event_time": record["review_time"] or record["capture_time"],
            "operator": record["reviewer"],
            "role": "officer",
            "action_type": "REVIEW_APPROVE" if record["status"] == "approved" else "REVIEW_REJECT",
            "details": (
                f"对违规单 {record['id']} 执行人工复核："
                + ("判定违规有效并入库" if record["status"] == "approved" else "判定为误报并剔除")
            ),
            "user_id": _user_id_for_badge(session, badge),
            "target_type": "violation",
            "target_id": record["id"],
            "ip": "192.168.10.42",
        })

    for uid, username, real_name, badge, role, department, last_login, _password in SEED_USERS:
        entries.append({
            "event_time": last_login,
            "operator": f"{real_name} ({badge})",
            "role": role,
            "action_type": "USER_LOGIN",
            "details": "登录非机动车违法检测系统后台",
            "user_id": uid,
            "target_type": "user",
            "target_id": str(uid),
            "ip": "192.168.10.1" if role == "admin" else "192.168.10.42",
        })

    entries.append({
        "event_time": format_time(datetime.now() - timedelta(hours=1)),
        "operator": "刘主任 (ADMIN-01)",
        "role": "admin",
        "action_type": "DATA_EXPORT",
        "details": f"批量导出台账取证总报表 (共计 {len(records)} 条记录)",
        "user_id": 3,
        "target_type": "violation",
        "target_id": "",
        "ip": "192.168.10.1",
    })

    entries.sort(key=lambda item: (item["event_time"], item["action_type"]))
    for entry in entries:
        log_repo.append_log(
            session,
            event_time=entry["event_time"],
            operator=entry["operator"],
            role=entry["role"],
            action_type=entry["action_type"],
            details=entry["details"],
            user_id=entry["user_id"],
            target_type=entry["target_type"],
            target_id=entry["target_id"],
            ip=entry["ip"],
        )
    session.commit()
    return len(entries)


def _count_records(session) -> int:
    return int(session.execute(select(func.count(ViolationRecord.id))).scalar_one())


def _wipe(engine) -> None:
    """drop 全部对象后再重建（用于 --force）：复用 0001 迁移的 down()/up()。"""
    import app.db.migrations.runner as runner

    module_path = Path(__file__).resolve().parents[1] / "app" / "db" / "migrations" / "0001_init.py"
    migration = runner._load_module(module_path)
    migration.down(engine)
    migration.up(engine)


def main() -> int:
    parser = argparse.ArgumentParser(description="灌入 7 天演示台账 + 用户 + 卡口 + 系统日志")
    parser.add_argument("--force", action="store_true", help="drop+recreate 全部表后重灌（不删库文件）")
    parser.add_argument("--reset", action="store_true", help="删除 traffic.db 后重建再灌")
    parser.add_argument(
        "--now",
        default=None,
        help="固定生成时刻（'YYYY-MM-DD HH:MM:SS'，本地时间）；默认当前时刻。"
             "用于与 JS 参考实现对账，保证两侧 now 完全一致。",
    )
    args = parser.parse_args()

    if args.reset:
        reset_ok = True
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(settings.db_path) + suffix)
            if p.exists():
                try:
                    p.unlink()
                except OSError as exc:
                    reset_ok = False
                    print(
                        f"[reset] 直接删除 {p.name} 被运行环境拦截"
                        f"（{exc.__class__.__name__}）；退化为原地 drop+recreate，等效重灌。"
                    )
                    break
        if reset_ok:
            print(f"[reset] 已删除 {settings.db_path}")
            args.force = False  # 库已空，无需再 wipe
        else:
            args.force = True  # 文件删不掉，改用原地 drop+recreate

    db_engine.init_db()
    if not db_state.ready:
        print(f"[error] 数据库不可用：{db_state.reason} / {db_state.message}")
        return 1

    engine = db_engine.get_engine()

    if args.force:
        print("[force] drop + recreate 全部表")
        _wipe(engine)

    with db_engine.session_scope() as session:
        existing = _count_records(session)
        if existing > 0:
            print(f"[skip] violation_records 已有 {existing} 条数据；如需重灌请用 --force 或 --reset")
            return 0
    # session_scope 已提交；下面重新开短会话

    now = parse_time(args.now) if args.now else datetime.now()
    if now is None:
        print(f"[error] --now 格式应为 'YYYY-MM-DD HH:MM:SS'，收到：{args.now!r}")
        return 1
    print(f"[seed] 生成时刻 now = {format_time(now)}")
    records = build_records(now) + build_edge_cases(now)
    records.sort(key=lambda r: r["capture_time"], reverse=True)

    # 【缺陷修正】demoDataset.js 的 buildRecords 只过滤了 captured > now，
    # 未约束 reviewTime；今日临近抓拍时刻的已复核记录，其"复核时间"会落到未来
    # （实测最多超前约 1.5h）。此处把 review_time 夹到 now。
    #
    # 硬约束：只能放在"取完所有随机数之后、读取 review_time 生成处置时间轴之前"。
    # 本循环不消耗任何随机数，故除 review_time（及其派生的 disposition 时间轴）
    # 外，总条数 / 状态分布 / 按卡口分布与修正前完全一致。
    clamped = 0
    for record in records:
        review_dt = parse_time(record["review_time"])
        if review_dt is not None and review_dt > now:
            record["review_time"] = format_time(now)
            clamped += 1
    if clamped:
        print(f"[fix] 复核时间超前修正：{clamped} 条 review_time 被夹到 now = {format_time(now)}")

    build_dispositions(records, now)

    with db_engine.session_scope() as session:
        seed_users(session)

    with db_engine.session_scope() as session:
        seed_records(session, records)

    with db_engine.session_scope() as session:
        log_count = seed_logs(session, records)

    # ── 统计报告 ──
    with db_engine.session_scope() as session:
        total = _count_records(session)
        status_rows = session.execute(
            select(ViolationRecord.status, func.count(ViolationRecord.id)).group_by(ViolationRecord.status)
        ).all()
        disp_rows = session.execute(
            select(Disposition.status, func.count(Disposition.violation_id))
            .where(Disposition.status.is_not(None))
            .group_by(Disposition.status)
        ).all()
        cam_rows = session.execute(
            select(ViolationRecord.camera_key, func.count(ViolationRecord.id))
            .where(ViolationRecord.camera_key.is_not(None))
            .group_by(ViolationRecord.camera_key)
        ).all()
        users = session.execute(select(func.count(User.id))).scalar_one()
        logs = session.execute(select(func.count(SystemLog.id))).scalar_one()
        review_rows = session.execute(select(func.count(ReviewHistory.id))).scalar_one()
        disp_hist_rows = session.execute(select(func.count(DispositionHistory.id))).scalar_one()

    print("\n===== 种子数据导入完成 =====")
    print(f"violation_records : {total}")
    print(f"  状态分布        : {dict(status_rows)}")
    print(f"  处置分布        : {dict(disp_rows)}")
    print(f"  按卡口分布      : {dict(cam_rows)}")
    print(f"review_history    : {review_rows}")
    print(f"disposition_history: {disp_hist_rows}")
    print(f"users             : {users}")
    print(f"system_logs       : {logs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
