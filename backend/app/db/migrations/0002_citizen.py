"""0002_citizen —— 公众服务端：车辆绑定、举报线索、车牌独立列。

背景
----
群众端要回答「我有没有事」，必须能确定「哪条记录是我的」，这就需要一条
从 **登录用户 → 绑定车牌 → 违法记录** 的可追溯链路。本迁移补齐三块：

1. `violation_records.plate_no`
   车牌原先只存在于 `details_json` 里，值形如「武汉路口抓拍电动车 [鄂A-TDR8]」，
   不是干净的车牌号，无法建索引关联。这里抽出独立列并回填，
   今后 `details_json` 里删掉重复的 `plate_or_vehicle` 也不影响关联。

2. `citizen_vehicles`
   车主与车牌的多对多绑定（一辆车可能多个登记人，一个市民可能有多个号牌）。
   **不把车牌写死在 users 表上**，否则换车、改车牌都要动用户主键语义。

3. `public_reports`
   公众举报线索。**独立于 violation_records**——
   举报只进线索池，未经执法人员核验绝不进入正式台账，两者混表等于给举报单发处罚权。

约束
----
公众举报可能含路人面部/车牌/未成年人影像，因此该表不做物理删除之外的联动，
`reporter_id` 不对当事人暴露，只在后台供执法研判使用。
"""
from __future__ import annotations

from sqlalchemy.engine import Engine

# 回填用：从 details_json 里把车牌抠出来。
# 观察到的实际值形如 '武汉路口抓拍电动车 [鄂A-TDR8]'，取方括号内部分。
# 没有方括号（种子数据多为 '蓝色共享助力车' 这类特征描述）时留空，不臆造车牌。
# 回填：从独立的 plate_or_vehicle 列里把方括号内的车牌抠出来。
# 观察到的实际值形如'黄色闪送配送电动车 [鄂A·F2210]' / '白色雅迪电瓶车 [无牌照]'。
# **排除无法作为关联依据的占位值**（无牌照 / 号牌污损不可辨识 / 无牌）——
# 这些不是有效车牌，挂上也是假关联，不如留空让该记录不匹配任何车主。
_BACKFILL_SQL = """
UPDATE violation_records
SET plate_no = UPPER(TRIM(
        SUBSTR(
            plate_or_vehicle,
            INSTR(plate_or_vehicle, '[') + 1,
            INSTR(plate_or_vehicle, ']')
            - INSTR(plate_or_vehicle, '[') - 1
        )
    ))
WHERE plate_no IS NULL
  AND plate_or_vehicle LIKE '%[%]%'
  AND INSTR(plate_or_vehicle, '[') > 0
  AND INSTR(plate_or_vehicle, ']') > INSTR(plate_or_vehicle, '[')
  AND plate_or_vehicle NOT LIKE '%无牌照%'
  AND plate_or_vehicle NOT LIKE '%无牌%'
  AND plate_or_vehicle NOT LIKE '%不可辨识%'
  AND plate_or_vehicle NOT LIKE '%污损%';
"""

_INDEXES = [
    "idx_violation_records_plate_time",
    "idx_citizen_vehicles_user",
    "idx_citizen_vehicles_plate",
    "idx_public_reports_status_time",
    "idx_public_reports_reporter",
]

_TABLES = [
    "public_reports",
    "citizen_vehicles",
]


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


# users.role 上有 CHECK (role IN ('officer','admin'))，SQLite 不支持 ALTER 改 CHECK，
# 只能重建表。users 仅 3 行、全库只有 system_logs 一处外键引用它
# （ON DELETE RESTRICT），重建代价极低，且能让群众账号复用同一套登录/令牌逻辑。
_USERS_REBUILD = """
PRAGMA foreign_keys = OFF;
CREATE TABLE users_new (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    real_name     TEXT    NOT NULL,
    badge_number  TEXT    NOT NULL,
    role          TEXT    NOT NULL
                  CHECK (role IN ('officer', 'admin', 'citizen')),
    status        TEXT    NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'disabled')),
    department    TEXT    NOT NULL DEFAULT '',
    password_hash TEXT,
    last_login_at TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
INSERT INTO users_new
    (id, username, real_name, badge_number, role, status, department,
     password_hash, last_login_at, created_at, updated_at)
SELECT id, username, real_name, badge_number, role, status, department,
       password_hash, last_login_at, created_at, updated_at
FROM users;
DROP TABLE users;
ALTER TABLE users_new RENAME TO users;
PRAGMA foreign_keys = ON;
"""


def up(engine: Engine) -> None:
    # 0) users.role 放开 citizen（重建表；幂等：已是三值则跳过）
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name='users'").fetchall()
        current_sql = rows[0][0] if rows else ""
        if "'citizen'" not in current_sql:
            for stmt in [s.strip() for s in _USERS_REBUILD.split(";") if s.strip()]:
                conn.exec_driver_sql(stmt)

    # 1) violation_records 增车牌列（幂等：已存在则跳过）
    #    开发期迁移可能中断重跑，ADD COLUMN 不支持 IF NOT EXISTS，只能先查列。
    with engine.begin() as conn:
        if not _column_exists(conn, "violation_records", "plate_no"):
            conn.exec_driver_sql("ALTER TABLE violation_records ADD COLUMN plate_no TEXT")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_violation_records_plate_time "
            "ON violation_records (plate_no, capture_time DESC)"
        )
    # 2) 从 plate_or_vehicle 回填历史车牌（幂等：只填空值）
    with engine.begin() as conn:
        conn.exec_driver_sql(_BACKFILL_SQL)

    # 4) 车辆绑定表 + 公众举报表
    # 注意：exec_driver_sql 只接受**单条**语句，多语句必须逐条 exec。
    citizen_vehicles_ddl = """
CREATE TABLE IF NOT EXISTS citizen_vehicles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    plate_no    TEXT    NOT NULL,
    plate_kind  TEXT    NOT NULL DEFAULT '电动自行车',
    binding_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    remark      TEXT    NOT NULL DEFAULT '',
    UNIQUE (user_id, plate_no),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
)
"""
    public_reports_ddl = """
CREATE TABLE IF NOT EXISTS public_reports (
    id            TEXT PRIMARY KEY,
    reporter_id   INTEGER,
    report_type   TEXT    NOT NULL DEFAULT 'helmet',
    occurred_at   TEXT    NOT NULL,
    camera_id     TEXT    NOT NULL DEFAULT '',
    location_text TEXT    NOT NULL DEFAULT '',
    description   TEXT    NOT NULL DEFAULT '',
    image_path    TEXT,
    -- submitted 待人工核查 / adopted 已采信 / rejected 不予采信
    -- / need_more 需补充材料 / transferred 已转立案线索
    status        TEXT    NOT NULL DEFAULT 'submitted',
    review_note   TEXT    NOT NULL DEFAULT '',
    reviewer      TEXT    NOT NULL DEFAULT '',
    reviewed_at   TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (reporter_id) REFERENCES users (id) ON DELETE SET NULL
)
"""
    with engine.begin() as conn:
        conn.exec_driver_sql(citizen_vehicles_ddl)
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_citizen_vehicles_user "
            "ON citizen_vehicles (user_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_citizen_vehicles_plate "
            "ON citizen_vehicles (plate_no)"
        )
        conn.exec_driver_sql(public_reports_ddl)
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_public_reports_status_time "
            "ON public_reports (status, created_at DESC)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_public_reports_reporter "
            "ON public_reports (reporter_id)"
        )


def down(engine: Engine) -> None:
    statements = [f"DROP INDEX IF EXISTS {name}" for name in _INDEXES]
    statements += [f"DROP TABLE IF EXISTS {name}" for name in _TABLES]
    statements.append("ALTER TABLE violation_records DROP COLUMN plate_no")
    with engine.begin() as conn:
        for sql in statements:
            conn.exec_driver_sql(sql)