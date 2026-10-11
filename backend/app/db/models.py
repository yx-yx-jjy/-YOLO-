"""ORM 模型 —— 与 deliverables/db-migration/schema.sql **逐字段一致**。

约定（与 schema.sql 完全对齐）：
  · 表名 / 字段名 snake_case；表名一律复数。
  · 时间戳一律本地时间字符串 'YYYY-MM-DD HH:MM:SS'（GMT+8），不用 UTC / ISO8601。
  · DDL（表 / 索引 / CHECK / 触发器）的唯一事实来源是 schema.sql，
    由 app/db/migrations 在启动时执行；**本文件只做映射，不负责建表**。
  · 因此这里声明的列 / 类型 / 可空性 / 唯一约束必须与 schema.sql 严格对齐，
    但不在 ORM 侧重复声明 CHECK 与触发器（避免两处定义漂移）。

== 为什么 ORM 里“重复”声明 UNIQUE / FK / server_default ==
这些约束在 schema.sql 里也有。ORM 侧再声明一遍，是为了让 `metadata` 自洽
（万一有人调用 metadata.create_all 也不会漏约束），并让模型本身可读。
**不允许只改 ORM 不改 schema.sql，反之亦然。**
"""
from __future__ import annotations

from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


_LOCALTIME = text("(datetime('now', 'localtime'))")


class Base(DeclarativeBase):
    pass


class SchemaVersion(Base):
    __tablename__ = "schema_version"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    checksum: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    applied_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_LOCALTIME)


class Camera(Base):
    __tablename__ = "cameras"

    camera_key: Mapped[str] = mapped_column(Text, primary_key=True)  # 'CAM-01'..'CAM-05'
    name: Mapped[str] = mapped_column(Text, nullable=False)
    area: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    heat_radius: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_LOCALTIME)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_LOCALTIME)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("badge_number", name="uq_users_badge_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    real_name: Mapped[str] = mapped_column(Text, nullable=False)
    badge_number: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)  # officer | admin
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    department: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_LOCALTIME)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_LOCALTIME)


class ViolationRecord(Base):
    __tablename__ = "violation_records"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # 'EV-...' / 'EV-AI-...'
    camera_key: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("cameras.camera_key", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=True,
    )
    camera_label: Mapped[str] = mapped_column(Text, nullable=False)  # 原始 camera_id 串
    direction: Mapped[str | None] = mapped_column(Text, nullable=True)
    track_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    violation_type: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False, server_default="helmet")
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    reviewer: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_time: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_remark: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    capture_time: Mapped[str] = mapped_column(Text, nullable=False)  # 无默认，应用显式写
    evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    roi_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    plate_or_vehicle: Mapped[str | None] = mapped_column(Text, nullable=True)
    helmet_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_frames: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_LOCALTIME)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_LOCALTIME)


class ReviewHistory(Base):
    __tablename__ = "review_history"
    __table_args__ = (
        UniqueConstraint("violation_id", "seq", name="uq_review_history_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    violation_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("violation_records.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)  # approve | reject | revoke
    reviewer: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    badge: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    remark: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    event_time: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_LOCALTIME)


class Disposition(Base):
    __tablename__ = "dispositions"

    violation_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("violation_records.id", onupdate="CASCADE", ondelete="RESTRICT"),
        primary_key=True,
    )
    status: Mapped[str | None] = mapped_column(Text, nullable=True)  # NULL = 未进入处置
    method: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    notified_at: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    disposed_at: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    handler: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    remark: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_LOCALTIME)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_LOCALTIME)


class DispositionHistory(Base):
    __tablename__ = "disposition_history"
    __table_args__ = (
        UniqueConstraint("violation_id", "seq", name="uq_disposition_history_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    violation_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("violation_records.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)  # create/notify/dispose/archive/revoke
    operator: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    remark: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    event_time: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_LOCALTIME)


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_time: Mapped[str] = mapped_column(Text, nullable=False)
    operator: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    target_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    prev_hash: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    entry_hash: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_LOCALTIME)


# 索引：与 schema.sql 对齐（schema.sql 里已 `CREATE INDEX IF NOT EXISTS`；
# 此处声明仅用于 metadata 自洽，实际创建以迁移脚本为准）。
Index("idx_violation_records_capture_time", ViolationRecord.capture_time.desc())
Index("idx_violation_records_status_time", ViolationRecord.status, ViolationRecord.capture_time.desc())
Index("idx_violation_records_camera_time", ViolationRecord.camera_key, ViolationRecord.capture_time.desc())
Index("idx_violation_records_category_time", ViolationRecord.category, ViolationRecord.capture_time.desc())
Index("idx_dispositions_status", Disposition.status)
Index("idx_system_logs_time", SystemLog.event_time.desc())
Index("idx_system_logs_action_time", SystemLog.action_type, SystemLog.event_time.desc())


__all__ = [
    "Base",
    "SchemaVersion",
    "Camera",
    "User",
    "ViolationRecord",
    "ReviewHistory",
    "Disposition",
    "DispositionHistory",
    "SystemLog",
]
