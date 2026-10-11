"""轻量迁移执行器（架构稿 §7.1）。

- 版本表：schema_version（version INTEGER PK, name, checksum, applied_at）
- 迁移脚本：本目录下 `NNNN_*.py`，每个实现 `up(engine)` / `down(engine)`
- 按序执行未应用的 `up()`；执行后登记 (version, name, checksum)
- 不复引入 Alembic（对单人毕设属过度设计，见架构稿 §2）

注意：`0001_init.py` 直接执行 `0001_init.sql`（= deliverables/db-migration/schema.sql
的逐字副本，DDL 唯一事实来源）。schema.sql 内含 `INSERT OR IGNORE INTO schema_version
VALUES (1, '0001_init.sql')`，故本执行器登记版本时用 `INSERT OR IGNORE` 防止主键冲突。
"""
from __future__ import annotations

import hashlib
import importlib.util
import logging
from pathlib import Path
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("traffic.db.migrations")

MIGRATIONS_DIR = Path(__file__).resolve().parent

_CREATE_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    checksum    TEXT NOT NULL DEFAULT '',
    applied_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
)
"""


def _discover() -> list[tuple[int, Path]]:
    items: list[tuple[int, Path]] = []
    for path in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.py")):
        items.append((int(path.name[:4]), path))
    return items


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(f"migration_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载迁移脚本：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def applied_versions(engine: Engine) -> set[int]:
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT version FROM schema_version").fetchall()
    return {int(row[0]) for row in rows}


def execute_script(engine: Engine, sql: str) -> None:
    """执行整段 SQL 脚本（含多语句 + 触发器 BEGIN…END 里的分号）。

    用原生 DBAPI 的 executescript：它按 SQLite 规则解析语句，
    不会像朴素 split(';') 那样把触发器体拆断。
    """
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.executescript(sql)
        raw.commit()
    finally:
        raw.close()


def _bootstrap_version_table(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(_CREATE_VERSION_TABLE)


def _record(engine: Engine, version: int, name: str, checksum: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO schema_version (version, name, checksum) "
                "VALUES (:v, :n, :c)"
            ),
            {"v": version, "n": name, "c": checksum},
        )


def run_migrations(engine: Engine) -> list[int]:
    """执行所有未应用的迁移，返回本次实际应用的版本号列表。"""
    _bootstrap_version_table(engine)
    done = applied_versions(engine)
    applied: list[int] = []
    for version, path in _discover():
        if version in done:
            continue
        module = _load_module(path)
        up: Callable[[Engine], None] | None = getattr(module, "up", None)
        if up is None:
            raise RuntimeError(f"迁移脚本缺少 up(engine)：{path.name}")
        logger.info("applying migration %s", path.name)
        up(engine)
        _record(engine, version, path.name, _checksum(path))
        applied.append(version)
    return applied
