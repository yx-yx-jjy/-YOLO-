"""卡口主数据仓储层。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Camera


ORDER = ("CAM-01", "CAM-02", "CAM-03", "CAM-04", "CAM-05")


def list_cameras(session: Session) -> list[Camera]:
    rows = list(session.execute(select(Camera)).scalars())
    # 按固定主键顺序返回，保证前端地图点位顺序稳定
    rows.sort(key=lambda cam: ORDER.index(cam.camera_key) if cam.camera_key in ORDER else 99)
    return rows
