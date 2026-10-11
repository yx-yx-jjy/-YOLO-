"""离线推理线索并入同一台账（架构稿 §3.3(5) / R3 决策）。

离线上传分析完成后，把确认事件入**同一条写队列**，标 id 前缀 'EV-AI-'
（mapping.derive_source 据此识别为 offline_upload），复用同一持久化线程。
"""
from __future__ import annotations

import logging

from ..db.writer import PersistTask, write_pipeline
from ..timeutil import now_str

logger = logging.getLogger("traffic.services.offline_ingest")


def ingest_job_events(job: dict) -> int:
    result = job.get("result") or {}
    events = result.get("events") or []
    if not events:
        return 0

    source_file = job.get("file_name") or "upload"
    job_id = str(job.get("id") or "job")
    annotated_url = result.get("annotated_url")

    count = 0
    for index, event in enumerate(events):
        record = {
            "id": f"EV-AI-{job_id[:6]}-{index}",
            "camera_id": f"离线上传 · {source_file}",
            "track_id": str(event.get("vehicle_track_id") or "-"),
            "violation_type": event.get("title") or "非机动车交通违法",
            "category": "helmet",
            "confidence": float(event.get("confidence") or 0.0),
            "status": "pending",
            "reviewer": None,
            "review_time": None,
            "review_remark": "",
            "capture_time": now_str(),
            "evidence_url": event.get("evidence_url") or annotated_url,
            "roi_url": event.get("roi_url"),
            "details": {
                "consecutive_frames": event.get("consecutive_frames") or 1,
                "timestamp_seconds": event.get("timestamp_seconds"),
                "vehicle_bbox": event.get("vehicle_bbox"),
                "rider_bbox": event.get("evidence_bbox"),
                "head_bbox": event.get("head_bbox"),
                "source_file": source_file,
                "ai_disclaimer": "AI 疑似违规线索，须经人工复核",
            },
        }
        write_pipeline.submit(PersistTask(record=record, kind="offline"))
        count += 1
    logger.info("离线任务 %s 产生 %s 条线索，已入写队列", job_id, count)
    return count
