from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BACKEND_DIR / path


@dataclass(frozen=True)
class Settings:
    weights_path: Path = _resolve_path(os.getenv("YOLO_WEIGHTS", "models/best.pt"))
    context_weights_path: Path = _resolve_path(os.getenv("YOLO_CONTEXT_WEIGHTS", "yolo11s.pt"))
    device: str = os.getenv("YOLO_DEVICE", "0")
    # Small headgear and partly occluded two-wheelers have very different score
    # distributions. Separate thresholds prevent a weak vehicle detection from
    # breaking an otherwise valid rider/headgear association.
    helmet_confidence: float = float(os.getenv("YOLO_HELMET_CONFIDENCE", "0.20"))
    context_confidence: float = float(os.getenv("YOLO_CONTEXT_CONFIDENCE", "0.20"))
    roi_helmet_confidence: float = float(os.getenv("YOLO_ROI_HELMET_CONFIDENCE", "0.08"))
    roi_image_size: int = int(os.getenv("YOLO_ROI_IMAGE_SIZE", "640"))
    image_size: int = int(os.getenv("YOLO_IMAGE_SIZE", "960"))
    camera_helmet_confidence: float = float(os.getenv("CAMERA_HELMET_CONFIDENCE", "0.20"))
    camera_context_confidence: float = float(os.getenv("CAMERA_CONTEXT_CONFIDENCE", "0.20"))
    camera_image_size: int = int(os.getenv("CAMERA_YOLO_IMAGE_SIZE", "960"))
    camera_context_image_size: int = int(os.getenv("CAMERA_CONTEXT_IMAGE_SIZE", "640"))
    camera_infer_every: int = max(1, int(os.getenv("CAMERA_INFER_EVERY", "3")))
    camera_idle_seconds: float = float(os.getenv("CAMERA_IDLE_SECONDS", "5"))
    camera_max_fps: float = float(os.getenv("CAMERA_MAX_FPS", "25"))
    video_sample_fps: float = float(os.getenv("VIDEO_SAMPLE_FPS", "5"))
    video_confirm_frames: int = int(os.getenv("VIDEO_CONFIRM_FRAMES", "3"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_MB", "500")) * 1024 * 1024
    upload_dir: Path = BACKEND_DIR / "storage" / "uploads"
    artifact_dir: Path = BACKEND_DIR / "storage" / "artifacts"
    # 数据库持久化层：SQLite 单文件（详见 deliverables/db-migration/schema.sql）
    db_path: Path = _resolve_path(os.getenv("TRAFFIC_DB", "storage/traffic.db"))
    backups_dir: Path = BACKEND_DIR / "storage" / "backups"
    # 写队列容量：只有数据库长时间病态时才会被填满（见架构稿 §3.3）
    write_queue_maxsize: int = int(os.getenv("WRITE_QUEUE_MAXSIZE", "2000"))
    # 轻量签名令牌的密钥（毕设内网演示级；生产应来自环境变量）
    auth_secret: str = os.getenv("AUTH_SECRET", "traffic-db-demo-secret-2026")
    auth_token_ttl_seconds: int = int(os.getenv("AUTH_TOKEN_TTL", str(12 * 3600)))


settings = Settings()
