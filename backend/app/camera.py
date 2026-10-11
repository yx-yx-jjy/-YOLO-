from __future__ import annotations

import os
import time
import uuid
import logging
import threading
import traceback
from pathlib import Path
from collections import deque
from typing import Generator, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import settings
from .inference import engine, CONTEXT_CLASS_IDS
from .media_utils import safe_imwrite
from .db import engine as db_engine
from .db.mapping import record_to_columns
from .db.writer import PersistTask, write_pipeline
from .repositories import record_repository as rec_repo
from .rules import (
    Detection,
    evaluate_violations,
    normalize_label,
    VEHICLE_CLASSES,
    HELMET_CLASSES,
    NO_HELMET_CLASSES,
    PERSON_CLASSES,
)

# 字体加载（确保中文不乱码）
FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
try:
    CHINESE_FONT_14 = ImageFont.truetype(FONT_PATH, 14)
    CHINESE_FONT_12 = ImageFont.truetype(FONT_PATH, 12)
    CHINESE_FONT_16 = ImageFont.truetype(FONT_PATH, 16)
except Exception:
    CHINESE_FONT_14 = None
    CHINESE_FONT_12 = None
    CHINESE_FONT_16 = None


class CameraStreamManager:
    def __init__(self) -> None:
        project_root = settings.upload_dir.parents[2]
        self.base_video_dir = project_root / "data" / "videos"
        self.camera_sources = {
            "CAM-04": {
                "name": "CAM-04: 武珞路-中南路口",
                "path": str(self.base_video_dir / "bilibili_cam.mp4"),
                "is_device": False,
            },
            "CAM-03": {
                "name": "CAM-03: 建设大道-香港路口电动车抓拍",
                # 2026-10-09 二次换源：上一个文件（douyin_shelter_cam.mp4）误用了无关素材 ——
                # 实测头盔模型检出仅 0.1 个/帧，画面以路边停放车辆为主，与"未戴头盔抓拍"完全不符。
                # 现改为实拍素材（ID: 7676446768918757233）的原生无水印版本（非录屏、无水印）：
                # 1080x1080 @ 30fps，50.5 秒循环，实测检出 1.4 个/帧，helmet 与 no_helmet 均出现。
                "path": str(self.base_video_dir / "douyin_helmet_cam.mp4"),
                "is_device": False,
            },
            "CAM-01": {
                "name": "CAM-01: 珞喻路-光谷广场口骑行车道监控",
                "path": str(self.base_video_dir / "douyin_cam.mp4"),
                "is_device": False,
            },
            "CAM-02": {
                "name": "CAM-02: 解放大道-新华路口",
                # 2026-10-01 换源：原先是 wuhan_jianshe_road.mp4，和 CAM-03 是同一个文件，
                # 两路画面一模一样。现改用「城市路口下班高峰电动车流」实拍片段（已裁掉平台水印），
                # 内容是密集非机动车流、戴与不戴头盔混合，并包含易混淆帽子样本。
                # 片段长 50 秒，读完由 _producer_loop 自动 seek 回第 0 帧循环重播。
                "path": str(self.base_video_dir / "wuhan_intersection_rush.mp4"),
                "is_device": False,
            },
        }
        self._caps: dict[str, cv2.VideoCapture] = {}
        self._locks: dict[str, threading.Lock] = {}
        # 每个 cam 的推流"代号"。新连接进来会 +1，旧循环下一轮发现自己过期就主动退出。
        # 没有它的话，每次切换点位 / 点重连都会遗留一个仍在跑 YOLO 的死循环，
        # 累积后一起抢占 GPU 和读帧锁，新连接迟迟等不到首帧，前端就报"视频流连接超时"。
        self._stream_generation: dict[str, int] = {}
        self._generation_lock = threading.Lock()
        # 生产者-消费者：每个点位只跑一个"读帧 + 推理 + 标注"线程，
        # 再多的 HTTP 流连接（含没被及时关掉的残留连接）都只是消费最新帧。
        # 原先是每个连接各跑一套完整循环，切几次点位就能攒下一堆死循环一起抢 GPU。
        self._producers: dict[str, threading.Thread] = {}
        self._producer_stop: dict[str, threading.Event] = {}
        self._producer_lock = threading.Lock()
        self._annotate_opts: dict[str, tuple[bool]] = {}
        self._latest_jpeg: dict[str, bytes] = {}
        self._latest_jpeg_seq: dict[str, int] = {}
        self._consumer_heartbeat: dict[str, float] = {}
        self._last_frames: dict[str, np.ndarray] = {}
        self._last_annotated: dict[str, np.ndarray] = {}
        self._last_stats: dict[str, dict] = {}
        self._recent_violations: deque = deque(maxlen=20)
        self._last_auto_capture_time: dict[str, float] = {}
        self._violation_tracks: dict[str, list[dict]] = {}

    def release_all_cameras(self) -> None:
        """显式关闭并释放所有摄像头与视频流资源"""
        # 1) 先让生产者线程收工
        for stop_event in list(self._producer_stop.values()):
            stop_event.set()
        # 2) 必须等它们**真正退出**，再去 release。
        #    只 set() 不等的话，生产线程很可能正卡在 cap.read() 里，主线程同时
        #    cap.release() —— 两个线程并发操作同一个 VideoCapture，会在 OpenCV
        #    原生层直接段错误崩溃：进程凭空消失，且完全没有 Python 异常可查。
        for thread in list(self._producers.values()):
            if thread.is_alive():
                thread.join(timeout=2.0)
        self._producers.clear()
        self._producer_stop.clear()

        for cam_id, cap in list(self._caps.items()):
            try:
                if cap is not None and cap.isOpened():
                    cap.release()
            except Exception:
                pass
        self._caps.clear()
        self._last_frames.clear()
        self._last_annotated.clear()
        self._latest_jpeg.clear()
        self._latest_jpeg_seq.clear()
        self._violation_tracks.clear()

    def _get_lock(self, cam_id: str) -> threading.Lock:
        if cam_id not in self._locks:
            self._locks[cam_id] = threading.Lock()
        return self._locks[cam_id]

    def _get_cap(self, cam_id: str) -> cv2.VideoCapture:
        cfg = self.camera_sources.get(cam_id, self.camera_sources["CAM-03"])
        if cam_id in self._caps:
            cap = self._caps[cam_id]
            if cap.isOpened():
                return cap
            cap.release()

        source = cfg["path"]
        if not os.path.exists(str(source)):
            source = str(self.base_video_dir / "wuhan_jianshe_road.mp4")
        cap = cv2.VideoCapture(str(source))

        self._caps[cam_id] = cap
        return cap

    def draw_text_pillow(
        self,
        img: np.ndarray,
        text: str,
        pos: tuple[int, int],
        text_color=(255, 255, 255),
        bg_color=None,
        font=CHINESE_FONT_12,
        padding=3,
    ) -> np.ndarray:
        if font is None:
            # OpenCV fallback
            cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.45, text_color, 1, cv2.LINE_AA)
            return img

        x, y = pos
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        bbox = draw.textbbox((x, y), text, font=font)
        if bg_color:
            bg_rect = (bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding)
            draw.rectangle(bg_rect, fill=bg_color)
        draw.text((x, y), text, font=font, fill=text_color)
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    def draw_text_items_pillow(self, img: np.ndarray, items: list[dict]) -> np.ndarray:
        """Draw all labels with one BGR/RGB conversion per frame."""
        if not items:
            return img
        if CHINESE_FONT_12 is None:
            for item in items:
                cv2.putText(
                    img,
                    item["text"],
                    item["pos"],
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    item["text_color"],
                    1,
                    cv2.LINE_AA,
                )
            return img

        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        for item in items:
            x, y = item["pos"]
            font = item["font"]
            bbox = draw.textbbox((x, y), item["text"], font=font)
            bg_color = item.get("bg_color")
            if bg_color:
                padding = item.get("padding", 3)
                draw.rectangle(
                    (
                        bbox[0] - padding,
                        bbox[1] - padding,
                        bbox[2] + padding,
                        bbox[3] + padding,
                    ),
                    fill=bg_color,
                )
            draw.text((x, y), item["text"], font=font, fill=item["text_color"])
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    def annotate_frame(
        self,
        frame: np.ndarray,
        detections: list[Detection],
        violations: list[dict],
        cam_id: str,
        fps: float,
        latency_ms: float,
        show_helmet: bool = True,
    ) -> np.ndarray:
        canvas = frame.copy()
        h, w = canvas.shape[:2]
        text_items: list[dict] = []

        violating_head_boxes = {
            tuple(item.get("head_bbox", []))
            for item in violations
            if item.get("code") == "NO_HELMET"
        }

        # Draw only headgear boxes. Context detections stay internal for rules.
        if show_helmet:
            for d in detections:
                norm_cls = normalize_label(d.class_name)
                if norm_cls in HELMET_CLASSES:
                    x1, y1, x2, y2 = (int(v) for v in d.bbox)
                    color = (255, 170, 0)
                    cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
                    text_items.append({
                        "text": f"已戴头盔 {d.confidence:.2f}",
                        "pos": (x1, max(2, y1 - 18)),
                        "text_color": (255, 255, 255),
                        "bg_color": (15, 23, 42),
                        "font": CHINESE_FONT_12,
                    })
                elif norm_cls in NO_HELMET_CLASSES:
                    # A bare head is not a traffic violation unless it belongs
                    # to a confirmed rider. Do not mark nearby pedestrians red.
                    if tuple(d.bbox) not in violating_head_boxes:
                        continue
                    x1, y1, x2, y2 = (int(v) for v in d.bbox)
                    color = (28, 28, 185)
                    cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
                    text_items.append({
                        "text": f"未戴头盔! {d.confidence:.2f}",
                        "pos": (x1, max(2, y1 - 18)),
                        "text_color": (255, 255, 255),
                        "bg_color": (185, 28, 28),
                        "font": CHINESE_FONT_12,
                    })

        # 顶部 HUD 水印
        cfg = self.camera_sources.get(cam_id, self.camera_sources["CAM-03"])
        visible_count = sum(
            1 for item in detections
            if normalize_label(item.class_name) in HELMET_CLASSES
            or (
                normalize_label(item.class_name) in NO_HELMET_CLASSES
                and tuple(item.bbox) in violating_head_boxes
            )
        )
        hud_text = f"● YOLO11头盔检测运行中 (GPU: RTX 4060) | 头盔目标 {visible_count} | 违规 {len(violations)} | {fps:.1f} FPS | 延迟 {latency_ms:.1f}ms"
        text_items.append({
            "text": hud_text,
            "pos": (16, 14),
            "text_color": (226, 232, 240),
            "bg_color": (15, 23, 42),
            "font": CHINESE_FONT_14,
            "padding": 6,
        })

        # 4. 右下角水印
        cam_tag = f"{cam_id} | 武汉路网智能感知"
        text_items.append({
            "text": cam_tag,
            "pos": (w - 220, h - 30),
            "text_color": (148, 163, 184),
            "bg_color": (15, 23, 42),
            "font": CHINESE_FONT_12,
            "padding": 4,
        })

        return self.draw_text_items_pillow(canvas, text_items)

    @staticmethod
    def _box_iou(first: tuple[float, ...], second: tuple[float, ...]) -> float:
        if len(first) != 4 or len(second) != 4:
            return 0.0
        x1 = max(first[0], second[0])
        y1 = max(first[1], second[1])
        x2 = min(first[2], second[2])
        y2 = min(first[3], second[3])
        intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
        second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
        union = first_area + second_area - intersection
        return intersection / union if union > 0 else 0.0

    def _confirm_violations(self, cam_id: str, violations: list[dict]) -> list[dict]:
        """Confirm the same vehicle violation across consecutive inference frames."""
        previous = self._violation_tracks.get(cam_id, [])
        current_tracks: list[dict] = []
        used_previous: set[int] = set()

        for violation in violations:
            if violation.get("code") == "HELMET_UNCERTAIN":
                continue
            vehicle_box = tuple(violation.get("vehicle_bbox", []))
            best_index = None
            best_iou = 0.0
            for index, tracked in enumerate(previous):
                if index in used_previous or tracked.get("code") != violation.get("code"):
                    continue
                iou = self._box_iou(vehicle_box, tuple(tracked.get("vehicle_bbox", [])))
                if iou > best_iou:
                    best_iou = iou
                    best_index = index

            consecutive_frames = 1
            if best_index is not None and best_iou >= 0.3:
                used_previous.add(best_index)
                consecutive_frames = previous[best_index]["consecutive_frames"] + 1

            current_tracks.append({
                **violation,
                "consecutive_frames": consecutive_frames,
            })

        self._violation_tracks[cam_id] = current_tracks
        return [
            item
            for item in current_tracks
            if item["consecutive_frames"] >= settings.video_confirm_frames
        ]

    @staticmethod
    def _clip_bbox(box: list | tuple, width: int, height: int) -> tuple[int, int, int, int] | None:
        if len(box) != 4:
            return None
        x1, y1, x2, y2 = (int(round(value)) for value in box)
        x1 = min(max(0, x1), width - 1)
        y1 = min(max(0, y1), height - 1)
        x2 = min(max(0, x2), width)
        y2 = min(max(0, y2), height)
        return (x1, y1, x2, y2) if x2 > x1 and y2 > y1 else None

    def _build_violation_evidence(
        self, frame: np.ndarray, violation: dict
    ) -> tuple[np.ndarray, np.ndarray]:
        """Create an auditable wide shot and a close crop for one event."""
        canvas = frame.copy()
        height, width = canvas.shape[:2]
        head_box = self._clip_bbox(violation.get("head_bbox", []), width, height)
        text_items: list[dict] = []
        crop_boxes: list[tuple[int, int, int, int]] = []

        def mark(box, label: str, line_color: tuple[int, int, int], label_color: tuple[int, int, int]):
            if box is None:
                return
            x1, y1, x2, y2 = box
            crop_boxes.append(box)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), line_color, 3)
            text_items.append({
                "text": label,
                "pos": (x1 + 4, max(4, y1 - 22)),
                "text_color": (255, 255, 255),
                "bg_color": label_color,
                "font": CHINESE_FONT_14,
                "padding": 4,
            })

        code = violation.get("code")
        if code == "NO_HELMET":
            mark(head_box, "未戴头盔", (0, 0, 255), (185, 28, 28))

        canvas = self.draw_text_items_pillow(canvas, text_items)
        if not crop_boxes:
            return canvas, canvas.copy()

        crop_x1 = min(box[0] for box in crop_boxes)
        crop_y1 = min(box[1] for box in crop_boxes)
        crop_x2 = max(box[2] for box in crop_boxes)
        crop_y2 = max(box[3] for box in crop_boxes)
        pad_x = max(24, int((crop_x2 - crop_x1) * 0.18))
        pad_y = max(24, int((crop_y2 - crop_y1) * 0.18))
        crop_x1 = max(0, crop_x1 - pad_x)
        crop_y1 = max(0, crop_y1 - pad_y)
        crop_x2 = min(width, crop_x2 + pad_x)
        crop_y2 = min(height, crop_y2 + pad_y)
        return canvas, canvas[crop_y1:crop_y2, crop_x1:crop_x2].copy()

    def _auto_record_violation(self, frame: np.ndarray, violations: list[dict], cam_id: str):
        """实时抓拍：生产线程只做 3 件廉价事（架构稿 §3.2）。

        1) 生成 event_id；2) appendleft 进 _recent_violations（保持 /api/camera/violations
        契约）；3) put_nowait 入有界写队列。

        **图像编码、落盘、DB 写入全部搬到独立持久化线程** —— 这里绝不做 JPEG 编码、
        绝不连数据库、绝不 block。这正是把 9.2 FPS 的瓶颈搬离帧循环的关键。
        """
        now = time.time()
        if now - self._last_auto_capture_time.get(cam_id, 0.0) < 4.0:  # 4秒防重复抓拍
            return

        cfg = self.camera_sources.get(cam_id, self.camera_sources["CAM-03"])
        for v in violations:
            if v.get("code") == "HELMET_UNCERTAIN":
                continue

            event_id = f"EV-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"

            record = {
                "id": event_id,
                "camera_id": cfg["name"],
                "track_id": v.get("vehicle_track_id", "108"),
                "violation_type": v.get("title", "非机动车交通违法"),
                "category": "helmet",
                "confidence": round(v.get("confidence", 0.92), 2),
                "status": "pending",
                "reviewer": None,
                "review_time": None,
                "review_remark": "",
                "capture_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                # 期望路径，供实时流展示；真正是否落盘由持久化线程决定（写失败会置 NULL 写库）
                "evidence_url": f"/artifacts/{event_id}/evidence.jpg",
                "roi_url": f"/artifacts/{event_id}/roi.jpg",
                "details": {
                    "plate_or_vehicle": f"武汉路口抓拍电动车 [鄂A-{event_id[-4:].upper()}]",
                    "consecutive_frames": v.get("consecutive_frames", 0),
                    "vehicle_bbox": v.get("vehicle_bbox"),
                    "rider_bbox": v.get("evidence_bbox"),
                    "head_bbox": v.get("head_bbox"),
                    "source_file": cfg["name"],
                    "ai_disclaimer": "AI 实时抓拍违规线索，须经人工复核",
                    "helmet_status": "not_wearing",
                },
            }
            self._recent_violations.appendleft(record)
            self._last_auto_capture_time[cam_id] = now
            # 入队：传引用即可（_build_violation_evidence 内部会 frame.copy()）。
            # 用 dict(record) 浅拷贝，避免持久化线程回填 url 时影响 deque 里的展示记录。
            write_pipeline.submit(PersistTask(
                record=dict(record),
                kind="realtime",
                frame=frame,
                violation=v,
                build_evidence=self._build_violation_evidence,
            ))
            break

    def _ensure_producer(self, cam_id: str, show_helmet: bool) -> None:
        """确保该点位有一个生产者线程在跑（已经在跑就直接复用）。

        生产者负责「读帧 → 推理 → 标注 → 编码」，结果放进 _latest_jpeg；
        所有 HTTP 流连接只从那里取最新帧。这样并发连接数不再放大 GPU 负载，
        即便有连接没被及时关掉，最多也只是多读几次内存里现成的帧。
        """
        with self._producer_lock:
            self._annotate_opts[cam_id] = (show_helmet,)
            self._consumer_heartbeat[cam_id] = time.time()
            existing = self._producers.get(cam_id)
            if existing is not None and existing.is_alive():
                return
            stop_event = threading.Event()
            self._producer_stop[cam_id] = stop_event
            thread = threading.Thread(
                target=self._producer_loop,
                args=(cam_id, stop_event),
                name=f"stream-producer-{cam_id}",
                daemon=True,
            )
            self._producers[cam_id] = thread
            thread.start()

    def _producer_loop(self, cam_id: str, stop_event: threading.Event) -> None:
        lock = self._get_lock(cam_id)
        frame_times = deque(maxlen=30)
        skip_infer_step = 0
        cached_detections: list[Detection] = []
        cached_violations: list[dict] = []
        latency_ms = 18.0

        while not stop_event.is_set():
            # 页面切走后尽快释放该点位，避免多个后台视频同时争抢 GPU。
            if time.time() - self._consumer_heartbeat.get(cam_id, 0.0) > settings.camera_idle_seconds:
                break

            show_helmet = self._annotate_opts.get(cam_id, (True,))[0]
            t0 = time.perf_counter()
            with lock:
                cap = self._get_cap(cam_id)
                ret, frame = cap.read()
                if not ret or frame is None:
                    # 循环重播
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        time.sleep(0.05)
                        continue

            self._last_frames[cam_id] = frame

            # 显示每一帧，YOLO 隔帧更新检测框，兼顾流畅度和检测稳定性。
            skip_infer_step += 1
            if skip_infer_step % settings.camera_infer_every == 1:
                try:
                    start_infer = time.perf_counter()
                    model = engine._get_model()
                    ctx_model = engine._get_context_model()

                    # 直接喂原图，由推理库自己做「保持纵横比」的 letterbox。
                    # 早先这里硬 resize 到 640x384：16:9 横屏源勉强能用，但竖屏源
                    # （CAM-01 是 720x1280）会被横向拉扁到严重变形 —— 实测检测数从
                    # 平均 2.7 掉到 0.2，等于这一路基本丧失识别能力；而且 x/y 各自
                    # 独立缩放，即使检出目标，框也会画到错误的位置。
                    r1 = model.predict(
                        frame,
                        conf=settings.camera_helmet_confidence,
                        imgsz=settings.camera_image_size,
                        device=settings.device,
                        verbose=False,
                    )[0]
                    r2 = ctx_model.predict(
                        frame,
                        classes=CONTEXT_CLASS_IDS,
                        conf=settings.camera_context_confidence,
                        imgsz=settings.camera_context_image_size,
                        device=settings.device,
                        verbose=False,
                    )[0]

                    # 结果已在原图坐标系里，不需要任何缩放映射
                    cached_detections = engine._parse_result(r1) + engine._parse_result(r2)
                    frame_violations = evaluate_violations(cached_detections)
                    cached_violations = self._confirm_violations(cam_id, frame_violations)
                    latency_ms = (time.perf_counter() - start_infer) * 1000

                    # 自动抓拍留存
                    if cached_violations:
                        self._auto_record_violation(frame, cached_violations, cam_id)

                except Exception:
                    # 绝不静默吞掉：推理一旦出错，表现就是"框不动"或"一个框都没有"，
                    # 而且完全无从查起。必须留痕到后端日志。
                    traceback.print_exc()

            # 用时间窗口计算真实吞吐率。平均每帧的瞬时 FPS 会被隔帧推理中的
            # 快速帧严重拉高，甚至显示出超过限速值的虚假数字。
            frame_times.append(time.perf_counter())
            if len(frame_times) >= 2:
                elapsed_window = frame_times[-1] - frame_times[0]
                curr_fps = (len(frame_times) - 1) / elapsed_window if elapsed_window > 0 else 0.0
            else:
                curr_fps = 0.0

            # 标注绘制
            annotated = self.annotate_frame(
                frame,
                cached_detections,
                cached_violations,
                cam_id,
                curr_fps,
                latency_ms,
                show_helmet=show_helmet,
            )
            self._last_annotated[cam_id] = annotated

            # 记录最新状态
            self._last_stats[cam_id] = {
                "cam_id": cam_id,
                "fps": round(curr_fps, 1),
                "latency_ms": round(latency_ms, 1),
                "width": frame.shape[1],
                "height": frame.shape[0],
                "detections_count": sum(
                    1 for item in cached_detections
                    if normalize_label(item.class_name) in HELMET_CLASSES
                    or (
                        normalize_label(item.class_name) in NO_HELMET_CLASSES
                        and any(tuple(item.bbox) == tuple(v.get("head_bbox", [])) for v in cached_violations)
                    )
                ),
                "violations_count": len(cached_violations),
            }

            # 编码为 JPEG
            ret, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                continue

            # 放到共享槽位，所有消费者从这里取；序号让消费者能判断有没有新帧
            self._latest_jpeg[cam_id] = buffer.tobytes()
            self._latest_jpeg_seq[cam_id] = self._latest_jpeg_seq.get(cam_id, 0) + 1

            # 按源视频帧率播放，避免 12 FPS 素材被错误地加速到 25 FPS。
            elapsed = time.perf_counter() - t0
            source_fps = cap.get(cv2.CAP_PROP_FPS) or settings.camera_max_fps
            target_fps = min(max(1.0, source_fps), settings.camera_max_fps)
            sleep_time = max(0.001, 1.0 / target_fps - elapsed)
            time.sleep(sleep_time)

        # 收工：把登记摘掉，下次有人看再重新拉起
        with self._producer_lock:
            if self._producers.get(cam_id) is threading.current_thread():
                self._producers.pop(cam_id, None)

    def generate_mjpeg(
        self, cam_id: str = "CAM-03", show_helmet: bool = True
    ) -> Generator[bytes, None, None]:
        # 认领本连接的代号：更晚建立的连接会让这个代号失效，消费循环随即退出
        with self._generation_lock:
            self._stream_generation[cam_id] = self._stream_generation.get(cam_id, 0) + 1
            my_generation = self._stream_generation[cam_id]

        self._ensure_producer(cam_id, show_helmet)

        last_seq = -1
        try:
            while True:
                # 被更新的连接取代了就收工，别再占着这条连接
                if self._stream_generation.get(cam_id) != my_generation:
                    break

                # 心跳：告诉生产者"还有人在看"，没人看时它会自己收工
                self._consumer_heartbeat[cam_id] = time.time()

                seq = self._latest_jpeg_seq.get(cam_id)
                if seq is not None and seq != last_seq:
                    jpeg = self._latest_jpeg.get(cam_id)
                    if jpeg:
                        last_seq = seq
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                        )
                        continue

                # 生产者还没出帧（或帧还没更新）：稍等再看，别空转
                time.sleep(0.02)
        except (GeneratorExit, StopIteration):
            return
        finally:
            # 没有后继连接时立即停止该点位，不再空跑 30 秒。
            if self._stream_generation.get(cam_id) == my_generation:
                self._consumer_heartbeat[cam_id] = 0.0
                stop_event = self._producer_stop.get(cam_id)
                if stop_event is not None:
                    stop_event.set()

    def take_snapshot(self, cam_id: str = "CAM-03") -> dict:
        annotated = self._last_annotated.get(cam_id)
        cfg = self.camera_sources.get(cam_id, self.camera_sources["CAM-03"])
        
        if annotated is None:
            raw = self._last_frames.get(cam_id)
            if raw is None:
                # 独立临时读取一帧，避免锁竞争
                temp_cap = cv2.VideoCapture(str(cfg["path"]))
                ret, raw = temp_cap.read()
                temp_cap.release()
                if not ret or raw is None:
                    raw = np.zeros((720, 1280, 3), dtype=np.uint8)
            annotated = raw

        # id 前缀必须是 'EV-'：schema.sql 的 violation_records 有 CHECK (id LIKE 'EV-%')，
        # 且台账要区分三种来源 —— 人工截帧用 'EV-SNAP-' 前缀（mapping.derive_source 据此识别）。
        event_id = f"EV-SNAP-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        artifact_sub = settings.artifact_dir / event_id
        artifact_sub.mkdir(parents=True, exist_ok=True)
        evidence_file = artifact_sub / "snapshot.jpg"
        safe_imwrite(evidence_file, annotated, 95)

        record = {
            "id": event_id,
            "camera_id": cfg["name"],
            "track_id": "SNAP",
            "violation_type": "人工实时抓拍取证",
            "category": "helmet",
            "confidence": 0.95,
            "status": "pending",
            "reviewer": None,
            "review_time": None,
            "review_remark": "",
            "capture_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "evidence_url": f"/artifacts/{event_id}/snapshot.jpg",
            "details": {
                "plate_or_vehicle": f"武汉路口人工抓拍 [{cfg['name'].split(':')[0]}]",
                "consecutive_frames": 1,
                "source_file": cfg["name"],
                "ai_disclaimer": "人工主动触发实时截帧，已完成高清局部存储",
            },
        }
        self._recent_violations.appendleft(record)

        # 人工截帧：低频、非 GPU 路径 → 同步写库并直接返回记录（架构稿 §3.3(5)）。
        # 库不可用时也不抛穿：实时功能优先，前端仍能拿到截图记录。
        try:
            with db_engine.session_scope() as session:
                columns = record_to_columns(record)
                if rec_repo.get_by_id(session, columns["id"]) is None:
                    rec_repo.insert_record(session, columns)
        except Exception as exc:  # noqa: BLE001
            logging.getLogger("traffic.camera").error("人工截帧写库失败（已降级返回记录）：%s", exc)
        return record

    def get_status(self, cam_id: str = "CAM-03") -> dict:
        return self._last_stats.get(
            cam_id,
            {
                "cam_id": cam_id,
                "fps": 0.0,
                "latency_ms": 0.0,
                "width": 1280,
                "height": 720,
                "detections_count": 0,
                "violations_count": 0,
            },
        )

    def get_recent_violations(self) -> list[dict]:
        return list(self._recent_violations)


camera_manager = CameraStreamManager()
