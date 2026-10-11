"""公众服务端演示账号与车辆绑定种子。

答辩用途：让「群众端」能真的登录、真的只看到自己名下记录，
而不是全站最新 3 条（那是假关联，页面上写着"您名下"却谁登录都一样）。

**演示数据必须落在真实数据上**：绑定车牌选自已存在的台账记录，
这样群众端看到的每一条都能在执法端台账里找到同一条，评审可对照核验。

用法：
    python -m scripts.seed_citizen
    python -m scripts.seed_citizen --reset   # 先清掉既有演示账号再重建
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.engine import init_db, session_scope  # noqa: E402
from app.security import hash_password  # noqa: E402
from sqlalchemy import text  # noqa: E402

# 演示账号（密码与执法端演示账号同规则：仅用于本机答辩演示）
DEMO_CITIZENS = [
    {
        "username": "citizen_demo",
        "password": "123456",
        "real_name": "陈先生",
        "badge_number": "—",
        "department": "社会车辆",
        # 该车牌在库里有 72 条已送达 + 5 条待告知，状态分布丰富，便于演示不同卡片形态
        "plates": ["鄂A·E8821"],
    },
    {
        "username": "citizen_zhao",
        "password": "123456",
        "real_name": "赵女士",
        "badge_number": "—",
        "department": "社会车辆",
        "plates": ["鄂A·D3097", "鄂A·F2210"],
    },
]


def seed(reset: bool = False) -> int:
    init_db()
    created = 0
    with session_scope() as session:
        if reset:
            session.execute(
                text("DELETE FROM citizen_vehicles WHERE user_id IN "
                     "(SELECT id FROM users WHERE role = 'citizen')")
            )
            session.execute(text("DELETE FROM users WHERE role = 'citizen'"))

        for demo in DEMO_CITIZENS:
            row = session.execute(
                text("SELECT id FROM users WHERE username = :u"), {"u": demo["username"]}
            ).fetchone()
            if row:
                user_id = row[0]
            else:
                session.execute(
                    text(
                        """
                        INSERT INTO users
                            (username, real_name, badge_number, role, status,
                             department, password_hash)
                        VALUES (:u, :rn, :bn, 'citizen', 'active', :dept, :pw)
                        """
                    ),
                    {
                        "u": demo["username"],
                        "rn": demo["real_name"],
                        "bn": demo["badge_number"],
                        "dept": demo["department"],
                        "pw": hash_password(demo["password"]),
                    },
                )
                user_id = session.execute(
                    text("SELECT id FROM users WHERE username = :u"), {"u": demo["username"]}
                ).fetchone()[0]
                created += 1

            for plate in demo["plates"]:
                exists = session.execute(
                    text(
                        "SELECT 1 FROM citizen_vehicles "
                        "WHERE user_id = :uid AND plate_no = :p"
                    ),
                    {"uid": user_id, "p": plate},
                ).fetchone()
                if exists:
                    continue
                session.execute(
                    text(
                        """
                        INSERT INTO citizen_vehicles (user_id, plate_no, plate_kind, remark)
                        VALUES (:uid, :p, '电动自行车', :r)
                        """
                    ),
                    {"uid": user_id, "p": plate, "r": "演示数据绑定"},
                )

    return created


def verify() -> list[tuple]:
    """打印每个演示账号能看到的记录数与状态分布，用于人工核对。"""
    init_db()
    out: list[tuple] = []
    with session_scope() as session:
        for demo in DEMO_CITIZENS:
            uid = session.execute(
                text("SELECT id FROM users WHERE username = :u"), {"u": demo["username"]}
            ).fetchone()
            if not uid:
                out.append((demo["username"], "账号不存在"))
                continue
            rows = session.execute(
                text(
                    """
                    SELECT d.status, COUNT(*)
                    FROM violation_records vr
                    LEFT JOIN dispositions d ON d.violation_id = vr.id
                    WHERE UPPER(vr.plate_no) IN (
                        SELECT UPPER(plate_no) FROM citizen_vehicles WHERE user_id = :uid
                    )
                    AND vr.status = 'approved'
                    GROUP BY d.status
                    """
                ),
                {"uid": uid[0]},
            ).fetchall()
            out.append((demo["username"], {r[0] or "无处置单": r[1] for r in rows}))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="公众服务端演示数据种子")
    ap.add_argument("--reset", action="store_true", help="先删除既有演示账号")
    ap.add_argument("--verify", action="store_true", help="只核对不写入")
    args = ap.parse_args()

    if args.verify:
        for name, info in verify():
            print(f"{name}: {info}")
    else:
        n = seed(reset=args.reset)
        print(f"已创建 {n} 个演示账号" if n else "演示账号已存在，未新增")
        for name, info in verify():
            print(f"  {name}: {info}")
        print("\n登录凭据：citizen_demo / 123456（鄂A·E8821，77 条记录）")
        print("          citizen_zhao / 123456（鄂A·D3097 + 鄂A·F2210）")