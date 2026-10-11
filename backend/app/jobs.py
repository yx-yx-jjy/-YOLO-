from __future__ import annotations

import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .config import settings
from .inference import engine


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        # A single worker avoids concurrent access to one YOLO model and GPU OOM.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="yolo-job")

    def create(self, source: Path, media_type: str, original_name: str) -> dict:
        job_id = uuid.uuid4().hex
        artifact_dir = settings.artifact_dir / job_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        job = {
            "id": job_id,
            "status": "queued",
            "progress": 0,
            "stage": "等待推理",
            "media_type": media_type,
            "file_name": original_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
        self._executor.submit(self._run, job_id, source, media_type, artifact_dir)
        return dict(job)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def _update(self, job_id: str, **changes) -> None:
        with self._lock:
            self._jobs[job_id].update(changes)

    def _run(self, job_id: str, source: Path, media_type: str, artifact_dir: Path) -> None:
        self._update(job_id, status="running", stage="正在加载 YOLO 模型")

        def progress(value: int, stage: str) -> None:
            self._update(job_id, progress=value, stage=stage)

        try:
            if media_type == "image":
                result = engine.analyze_image(source, artifact_dir, progress)
            else:
                result = engine.analyze_video(source, artifact_dir, progress)
            self._update(job_id, status="completed", progress=100, stage="分析完成", result=result)
            # 离线推理确认事件并入同一台账（入写队列，非阻塞；失败不影响任务状态）
            try:
                from .services.offline_ingest import ingest_job_events

                ingest_job_events(self.get(job_id))
            except Exception:
                traceback.print_exc()
        except Exception as exc:
            self._update(
                job_id,
                status="failed",
                stage="分析失败",
                error={"message": str(exc), "type": type(exc).__name__},
            )
            traceback.print_exc()


jobs = JobManager()

