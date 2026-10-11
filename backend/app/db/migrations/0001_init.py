"""0001_init —— 初始建表（等价于 schema.sql）。

up()  执行 0001_init.sql（= deliverables/db-migration/schema.sql 的逐字副本）。
down() 逆序删除全部对象（仅用于本地回退演练，生产不物理删除台账）。
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine

# 用绝对导入：迁移模块由 runner 以独立模块名动态加载，相对导入会因无父包而失败。
from app.db.migrations.runner import execute_script

SQL_PATH = Path(__file__).with_name("0001_init.sql")

_TABLES = [
    "system_logs",
    "disposition_history",
    "dispositions",
    "review_history",
    "violation_records",
    "users",
    "cameras",
    "schema_version",
]

_TRIGGERS = [
    "trg_record_init_disposition",
    "trg_dispositions_require_approved",
    "trg_dispositions_require_approved_upd",
    "trg_review_history_immutable_upd",
    "trg_review_history_immutable_del",
    "trg_disposition_history_immutable_upd",
    "trg_disposition_history_immutable_del",
    "trg_system_logs_immutable_upd",
    "trg_system_logs_immutable_del",
]

_INDEXES = [
    "idx_violation_records_capture_time",
    "idx_violation_records_status_time",
    "idx_violation_records_camera_time",
    "idx_violation_records_category_time",
    "idx_dispositions_status",
    "idx_system_logs_time",
    "idx_system_logs_action_time",
    "idx_system_logs_prev_hash_unique",
]


def up(engine: Engine) -> None:
    execute_script(engine, SQL_PATH.read_text(encoding="utf-8"))


def down(engine: Engine) -> None:
    statements = [f"DROP TRIGGER IF EXISTS {name}" for name in _TRIGGERS]
    statements += [f"DROP INDEX IF EXISTS {name}" for name in _INDEXES]
    statements += [f"DROP TABLE IF EXISTS {name}" for name in _TABLES]
    execute_script(engine, ";\n".join(statements) + ";")
