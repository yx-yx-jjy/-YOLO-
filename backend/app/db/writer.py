"""有界写队列 + 单持久化线程（架构稿 §3，write-behind）。

铁律：
  · 生产线程（GPU 关键路径）只 `put_nowait`，**绝不 block、绝不 sleep**。
  · 队列满 → 丢最新 + dropped_count++ + WARNING 日志。
  · 持久化线程持有**自己的** SQLAlchemy Session（不跨线程共享），单事件单事务。
  · 存证图写失败 → 保留记录，evidence_url / roi_url 置 NULL（不新增列）。
  · 写失败捕获异常、记 last_error，**线程不退出**，继续处理后续任务。
"""
from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable

from ..config import settings
from ..media_utils import safe_imwrite
from ..repositories import record_repository as rec_repo
from . import engine as db_engine
from .mapping import record_to_columns

logger = logging.getLogger("traffic.db.writer")


@dataclass
class PersistTask:
    """一个待持久化事件。

    frame 按**引用**传递即可：camera.annotate_frame / _build_violation_evidence 内部
    都会 `frame.copy()`，入队后该帧不会被原地修改（见架构稿 §3.3(2) 的隐性约定，
    改动帧对象的代码必须保持这一前提）。
    """
    record: dict                       # API Record 形态（含 id / capture_time / details ...）
    kind: str = "realtime"             # 'realtime' | 'offline'
    frame: Any | None = None
    violation: dict | None = None
    build_evidence: Callable[[Any, dict], tuple[Any, Any]] | None = None


class _Sentinel:
    pass


_SENTINEL = _Sentinel()


class WritePipeline:
    def __init__(self) -> None:
        self._queue: queue.Queue = queue.Queue(maxsize=settings.write_queue_maxsize)
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.dropped = 0
        self.committed = 0
        self.failed = 0
        self.last_error: str | None = None

    # ---- 生命周期 ----
    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run, name="db-persist-writer", daemon=True
            )
            self._thread.start()
            logger.info("持久化线程已启动（队列上限 %s）", self._queue.maxsize)

    def stop(self, timeout: float = 5.0) -> int:
        """向队列发哨兵并等待线程收工。返回未处理完的遗留任务数。"""
        thread = self._thread
        if thread is None:
            return 0
        try:
            self._queue.put_nowait(_SENTINEL)
        except queue.Full:
            # 队列满时也要能停下：直接放哨兵会失败，退化为等待，由进程退出兜底
            try:
                self._queue.put(_SENTINEL, timeout=timeout)
            except queue.Full:
                logger.warning("队列已满，无法投递关闭哨兵")
        thread.join(timeout=timeout)
        leftover = self._queue.qsize()
        if leftover:
            logger.warning("持久化线程关闭超时，剩余 %s 个任务未写入", leftover)
        self._thread = None
        return leftover

    # ---- 生产侧（非阻塞） ----
    def submit(self, task: PersistTask) -> bool:
        try:
            self._queue.put_nowait(task)
            return True
        except queue.Full:
            self.dropped += 1
            if self.dropped <= 5 or self.dropped % 100 == 0:
                logger.warning(
                    "写队列已满，丢弃最新事件（累计丢弃 %s 条）；实时帧循环不受影响",
                    self.dropped,
                )
            return False

    # ---- 状态 ----
    def stats(self) -> dict:
        result = {
            "queued": self._queue.qsize(),
            "dropped": self.dropped,
            "committed": self.committed,
        }
        if self.last_error:
            result["last_error"] = self.last_error
        return result

    # ---- 消费侧 ----
    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if isinstance(item, _Sentinel):
                    return
                self._process(item)
            except Exception as exc:  # noqa: BLE001 - 线程绝不因单条失败退出
                self.failed += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.error("持久化任务失败：%s", exc)
            finally:
                self._queue.task_done()

    def _build_evidence_files(self, task: PersistTask) -> None:
        """证据图落盘成功才回填 url；失败则保持 None（= 无图信号）。"""
        if task.frame is None or task.build_evidence is None:
            return
        event_id = task.record["id"]
        artifact_dir = settings.artifact_dir / event_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        try:
            evidence_frame, roi_frame = task.build_evidence(task.frame, task.violation)
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"evidence_build_failed: {exc}"
            logger.error("构建存证图失败 event=%s：%s", event_id, exc)
            return
        if safe_imwrite(artifact_dir / "evidence.jpg", evidence_frame, 92):
            task.record["evidence_url"] = f"/artifacts/{event_id}/evidence.jpg"
        else:
            task.record["evidence_url"] = None
        if safe_imwrite(artifact_dir / "roi.jpg", roi_frame, 94):
            task.record["roi_url"] = f"/artifacts/{event_id}/roi.jpg"
        else:
            task.record["roi_url"] = None

    def _process(self, task: PersistTask) -> None:
        # 1) 先把图落盘（可能较慢），再写元数据 —— "图在则记录在"
        self._build_evidence_files(task)
        # 2) 单事件单事务写元数据
        columns = record_to_columns(task.record)
        with db_engine.session_scope() as session:
            existing = rec_repo.get_by_id(session, columns["id"])
            if existing is not None:
                # 幂等：同 id 已存在则跳过（重复投递 / 重放）
                return
            rec_repo.insert_record(session, columns)
        self.committed += 1


write_pipeline = WritePipeline()
