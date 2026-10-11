"""统一时间处理：全系统一律**本地时间（GMT+8）**字符串 'YYYY-MM-DD HH:MM:SS'。

schema.sql 里所有时间列都有 GLOB 约束，会直接拒绝 UTC / ISO8601（'T'/'Z'）。
故本模块是全后端唯一的时间入口，禁止在别处 `datetime.utcnow()` / `isoformat()`。
"""
from __future__ import annotations

from datetime import datetime, timedelta

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def local_now() -> datetime:
    """本地 naive datetime（= 机器时区，本机为 GMT+8）。"""
    return datetime.now()


def format_time(value: datetime) -> str:
    return value.strftime(TIME_FORMAT)


def now_str() -> str:
    return format_time(local_now())


def parse_time(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.strptime(text.strip(), TIME_FORMAT)
    except ValueError:
        return None


def day_key(value: datetime | None = None) -> str:
    return (value or local_now()).strftime("%Y-%m-%d")


def add_hours(value: datetime, hours: float) -> datetime:
    return value + timedelta(hours=hours)
