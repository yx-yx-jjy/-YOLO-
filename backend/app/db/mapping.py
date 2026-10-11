"""DB ↔ API 字段映射（严格对齐 02-数据库设计.md §3.5）。

只做"搬运"，不含业务规则：
  · parse_camera_label：原始 camera_id 串 → 卡口外键 + 方向后缀（前缀最长匹配）
  · record_to_columns：API Record dict → violation_records 列 dict（details 拆分为提升列 + details_json）
"""
from __future__ import annotations

import json
from typing import Any

# 卡口主键（与 schema.sql 的 cameras 初始数据一致）。用于把原始串解析成外键，
# 解析规则 = 前端 cameraKey() 的 startsWith，取作为 label 前缀的最长匹配 key。
KNOWN_CAMERA_KEYS = ("CAM-01", "CAM-02", "CAM-03", "CAM-04", "CAM-05")

# details 里"提升为真实列"的稳定字段（02-设计 §8-C 的边界原则）
_PROMOTED_DETAIL_KEYS = (
    "plate_or_vehicle",
    "helmet_status",
    "consecutive_frames",
    "source_file",
    "ai_disclaimer",
)


def parse_camera_label(label: str | None) -> tuple[str | None, str | None]:
    """返回 (camera_key, direction)。解析不出时分别为 (None, None)。"""
    if not label:
        return None, None
    matched = None
    for key in KNOWN_CAMERA_KEYS:
        if label.startswith(key) and (matched is None or len(key) > len(matched)):
            matched = key
    if matched is None:
        return None, None
    rest = label[len(matched):]
    direction = None
    if rest.startswith("-"):
        direction = rest[1:].strip() or None
    return matched, direction


def _as_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def record_to_columns(record: dict) -> dict:
    """把一条内存记录（API Record 形态）转换成 violation_records 的列字典。"""
    label = record.get("camera_id") or record.get("camera_label") or ""
    camera_key, direction = parse_camera_label(label)

    details = record.get("details") or {}
    residual = {key: value for key, value in details.items() if key not in _PROMOTED_DETAIL_KEYS}
    details_json = json.dumps(residual, ensure_ascii=False) if residual else None

    consecutive = details.get("consecutive_frames")
    if consecutive is None:
        consecutive = record.get("consecutive_frames")
    consecutive = _as_int_or_none(consecutive)

    return {
        "id": record["id"],
        "camera_key": camera_key,
        "camera_label": label,
        "direction": direction,
        "track_id": _as_str_or_none(record.get("track_id")),
        "violation_type": record.get("violation_type") or "非机动车交通违法",
        "category": record.get("category") or "helmet",
        "confidence": float(record.get("confidence") or 0.0),
        "status": record.get("status") or "pending",
        "reviewer": record.get("reviewer"),
        "review_time": record.get("review_time"),
        "review_remark": record.get("review_remark") or "",
        "capture_time": record["capture_time"],
        "evidence_url": record.get("evidence_url"),
        "roi_url": record.get("roi_url"),
        "plate_or_vehicle": details.get("plate_or_vehicle"),
        "helmet_status": details.get("helmet_status"),
        "consecutive_frames": consecutive,
        "source_file": details.get("source_file"),
        "ai_disclaimer": details.get("ai_disclaimer"),
        "details_json": details_json,
    }


def details_from_columns(row) -> dict:
    """把提升列 + details_json 读时拼回 details 对象。"""
    details: dict = {}
    residual = {}
    if getattr(row, "details_json", None):
        try:
            residual = json.loads(row.details_json)
        except (TypeError, ValueError):
            residual = {}
    if isinstance(residual, dict):
        details.update(residual)
    # 【D4 修正】提升列**恒输出**（无值为 null），与契约 §4.1 的 details 示例对齐
    # （示例恒含 source_file / ai_disclaimer），避免"键缺失"误导调用方。
    for key in _PROMOTED_DETAIL_KEYS:
        details[key] = getattr(row, key, None)
    return details


def derive_source(record_id: str) -> str:
    """台账来源标识（schema 无专用列，按 id 前缀派生，见数据建模"来源标识"）。

    · 'EV-AI-'  → offline_upload（离线上传推理线索）
    · 'EV-SNAP-'→ snapshot（人工实时截帧）
    · 其它 'EV-' → camera（卡口实时自动抓拍）
    """
    if record_id.startswith("EV-AI-"):
        return "offline_upload"
    if record_id.startswith("EV-SNAP-"):
        return "snapshot"
    return "camera"
