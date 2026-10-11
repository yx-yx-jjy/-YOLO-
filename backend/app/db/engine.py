"""SQLAlchemy engine / 会话工厂 / 启动自检。

职责：
  · 创建 engine（SQLite 单文件），在每条连接上设置 WAL / busy_timeout / foreign_keys
  · 启动时自动执行未应用的迁移
  · 启动自检：PRAGMA quick_check + 写探针 → 决定 db_state.ready
  · 提供请求级会话依赖与后台线程会话上下文
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings
from .migrations.runner import run_migrations
from .state import DbUnavailableError, db_state

logger = logging.getLogger("traffic.db.engine")

_engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None

_HINT = "请检查 backend/storage/traffic.db 是否被其它程序打开、文件是否损坏，或目录写权限"


def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    try:
        # 读不阻塞写（台账页轮询读 vs 实时抓拍写同时发生）
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        # SQLite 外键默认关闭，必须每连接开启
        cursor.execute("PRAGMA foreign_keys=ON")
        # database is locked 时最长重试 5s，而不是立刻抛出
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


def _build_engine() -> Engine:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{settings.db_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 5},
        future=True,
    )
    event.listen(engine, "connect", _configure_sqlite)
    return engine


def _write_probe(engine: Engine) -> None:
    """写权限探针：读-only / 无权限时这里会抛错，启动自检据此判定不可用。"""
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS _health_probe (x INTEGER)")
        conn.exec_driver_sql("DROP TABLE IF EXISTS _health_probe")


def _quick_check(engine: Engine) -> None:
    with engine.connect() as conn:
        row = conn.exec_driver_sql("PRAGMA quick_check").fetchone()
    result = (row[0] if row else "unknown")
    if str(result).lower() != "ok":
        raise RuntimeError(f"PRAGMA quick_check 异常：{result}")


def init_db() -> None:
    """启动时调用。任何失败都只置 db_state=unavailable，**不抛穿**（后端仍要能启动）。"""
    global _engine, SessionLocal
    try:
        _engine = _build_engine()
        SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)
    except Exception as exc:  # noqa: BLE001 - 启动不能因 DB 挂掉
        db_state.ready = False
        db_state.reason = "engine_init_failed"
        # message 面向客户端：只给稳定文案，原始异常串只写日志（避免泄露内部实现）
        db_state.message = "数据库引擎初始化失败"
        logger.error("数据库引擎初始化失败：%s", exc, exc_info=True)
        return

    try:
        applied = run_migrations(_engine)
        if applied:
            logger.info("已应用迁移版本：%s", applied)
        _quick_check(_engine)
        _write_probe(_engine)
    except Exception as exc:  # noqa: BLE001
        db_state.ready = False
        db_state.reason = "db_unavailable"
        # message 面向客户端：只给稳定文案（原始 sqlite/驱动串只写日志）
        db_state.message = "台账数据库不可用"
        logger.error("启动自检失败，db_state=unavailable：%s", exc, exc_info=True)
        return

    db_state.ready = True
    db_state.reason = None
    db_state.message = None
    logger.info("数据库就绪：%s", settings.db_path)


def get_engine() -> Engine:
    if _engine is None:
        raise DbUnavailableError(db_state.message or "数据库尚未初始化", hint=_HINT)
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI 依赖：DB 不可用时直接 503，绝不返回 200 + 空数组。"""
    if not db_state.ready:
        raise DbUnavailableError(db_state.message or "台账数据库不可用", hint=_HINT)
    if SessionLocal is None:
        raise DbUnavailableError("数据库会话工厂未初始化", hint=_HINT)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """后台线程（持久化线程 / 种子脚本）用：自带 commit / rollback。"""
    if SessionLocal is None:
        raise DbUnavailableError("数据库会话工厂未初始化", hint=_HINT)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def health() -> dict:
    return {
        "ready": db_state.ready,
        "reason": db_state.reason,
        "message": db_state.message,
    }
