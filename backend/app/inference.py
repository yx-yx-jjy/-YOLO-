from __future__ import annotations

import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable

import cv2

from .config import settings
from .media_utils import safe_imwrite
from .rules import (
    Detection,
    evaluate_violations,
    normalize_label,
    HELMET_CLASSES,
    NO_HELMET_CLASSES,
)


REQUIRED_CLASS_GROUPS = {
    "vehicle": {"electric_bicycle", "electric-bike", "ebike", "e-bike", "motorcycle", "bicycle", "scooter"},
    "person": {"person", "rider", "driver"},
    "helmet": {"helmet", "with_helmet", "wearing_helmet"},
    "no_helmet": {"no_helmet", "without_helmet", "bare_head", "head", "no-helmet"},
}
CONTEXT_CLASS_IDS = [0, 1, 3]  # person, bicycle, motorcycle in COCO


class ModelUnavailableError(RuntimeError):
    pass


class YoloInferenceEngine:
    def __init__(self) -> None:
        self._model = None
        self._context_model = None
        self._lock = threading.Lock()

    def status(self) -> dict:
        if not settings.weights_path.exists():
            return {
                "ready": False,
                "reason": "custom_weights_missing",
                "message": f"未找到定制模型权重：{settings.weights_path}",
                "weights_path": str(settings.weights_path),
                "required_classes": sorted(REQUIRED_CLASS_GROUPS),
            }
        if not settings.context_weights_path.exists():
            return {
                "ready": False,
                "reason": "context_weights_missing",
                "message": f"未找到人车上下文模型：{settings.context_weights_path}",
                "weights_path": str(settings.context_weights_path),
            }
        try:
            model = self._get_model()
            context_model = self._get_context_model()
            custom_names = [normalize_label(str(value)) for value in model.names.values()]
            context_names = [normalize_label(str(value)) for value in context_model.names.values()]
            available_names = set(custom_names) | set(context_names)
            missing = [
                group for group, aliases in REQUIRED_CLASS_GROUPS.items()
                if not aliases.intersection(available_names)
            ]
            if missing:
                return {
                    "ready": False,
                    "reason": "incompatible_classes",
                    "message": f"模型缺少必要语义类别：{', '.join(missing)}",
                    "custom_classes": custom_names,
                    "context_classes": context_names,
                    "required_classes": sorted(REQUIRED_CLASS_GROUPS),
                }
            return {
                "ready": True,
                "message": "YOLO 定制模型已就绪",
                "weights_path": str(settings.weights_path),
                "context_weights_path": str(settings.context_weights_path),
                "device": settings.device,
                "thresholds": {
                    "helmet": settings.helmet_confidence,
                    "context": settings.context_confidence,
                    "helmet_roi": settings.roi_helmet_confidence,
                },
                "custom_classes": custom_names,
                "context_classes": [context_names[index] for index in CONTEXT_CLASS_IDS],
            }
        except Exception as exc:
            return {"ready": False, "reason": "model_load_failed", "message": str(exc)}

    def _get_model(self):
        if self._model is not None:
            return self._model
        if not settings.weights_path.exists():
            raise ModelUnavailableError(f"缺少模型权重：{settings.weights_path}")
        with self._lock:
            if self._model is None:
                from ultralytics import YOLO
                self._model = YOLO(str(settings.weights_path))
        return self._model

    def _get_context_model(self):
        if self._context_model is not None:
            return self._context_model
        if not settings.context_weights_path.exists():
            raise ModelUnavailableError(f"缺少人车上下文模型：{settings.context_weights_path}")
        with self._lock:
            if self._context_model is None:
                from ultralytics import YOLO
                self._context_model = YOLO(str(settings.context_weights_path))
        return self._context_model

    @staticmethod
    def _parse_result(result) -> list[Detection]:
        detections: list[Detection] = []
        if result.boxes is None:
            return detections
        names = result.names
        ids = result.boxes.id.int().cpu().tolist() if result.boxes.id is not None else [None] * len(result.boxes)
        boxes = result.boxes.xyxy.cpu().tolist()
        confidences = result.boxes.conf.cpu().tolist()
        classes = result.boxes.cls.int().cpu().tolist()
        for bbox, confidence, class_id, track_id in zip(boxes, confidences, classes, ids):
            detections.append(Detection(
                class_name=str(names[class_id]),
                confidence=float(confidence),
                bbox=tuple(float(value) for value in bbox),
                track_id=track_id,
            ))
        return detections

    @staticmethod
    def _annotate(frame, detections: list[Detection], violations: list[dict]):
        canvas = frame.copy()
        # Context detections (person/bicycle/motorcycle) are used only by the
        # association rules. They are intentionally never exposed in evidence.
        visible_detections = [
            item for item in detections
            if normalize_label(item.class_name) in HELMET_CLASSES
            or (
                normalize_label(item.class_name) in NO_HELMET_CLASSES
                and tuple(item.bbox) in {
                    tuple(event.get("head_bbox", []))
                    for event in violations
                    if event.get("code") == "NO_HELMET"
                }
            )
        ]
        violating_boxes = {
            tuple(item.get("head_bbox", []))
            for item in violations
            if item.get("code") == "NO_HELMET"
        }
        for detection in visible_detections:
            x1, y1, x2, y2 = (int(value) for value in detection.bbox)
            is_violation = tuple(detection.bbox) in violating_boxes
            color = (35, 48, 220) if is_violation else (52, 168, 83)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
            label = f"{detection.class_name} {detection.confidence:.2f}"
            cv2.rectangle(canvas, (x1, max(0, y1 - 22)), (x1 + max(110, len(label) * 8), y1), color, -1)
            cv2.putText(canvas, label, (x1 + 4, max(14, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        return canvas

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

    @classmethod
    def _save_event_roi(
        cls,
        annotated,
        event: dict,
        artifact_dir: Path,
        event_index: int,
    ) -> str | None:
        """Save a close crop around the violating rider's head/upper body."""
        height, width = annotated.shape[:2]
        focus_box = cls._clip_bbox(event.get("head_bbox", []), width, height)
        if focus_box is None:
            focus_box = cls._clip_bbox(event.get("evidence_bbox", []), width, height)
        if focus_box is None:
            return None

        x1, y1, x2, y2 = focus_box
        box_width = x2 - x1
        box_height = y2 - y1
        pad_x = max(24, int(box_width * 0.25))
        pad_y = max(24, int(box_height * 0.20))
        crop_x1 = max(0, x1 - pad_x)
        crop_y1 = max(0, y1 - pad_y)
        crop_x2 = min(width, x2 + pad_x)
        crop_y2 = min(height, y2 + pad_y)
        roi = annotated[crop_y1:crop_y2, crop_x1:crop_x2].copy()
        filename = f"event_{event_index:03d}_roi.jpg"
        if not safe_imwrite(artifact_dir / filename, roi, 94):
            return None
        return f"/artifacts/{artifact_dir.name}/{filename}"

    def _refine_uncertain_headgear(
        self,
        frame,
        model,
        detections: list[Detection],
        violations: list[dict],
    ) -> list[Detection]:
        """Retry headgear detection on rider head crops for uncertain vehicles."""
        height, width = frame.shape[:2]
        rider_boxes = {
            tuple(box)
            for event in violations
            if event.get("code") == "HELMET_UNCERTAIN"
            for box in event.get("rider_bboxes", [])
            if len(box) == 4
        }
        refined: list[Detection] = []
        for rider_box in rider_boxes:
            x1, y1, x2, y2 = rider_box
            rider_width = max(1.0, x2 - x1)
            rider_height = max(1.0, y2 - y1)
            crop_x1 = max(0, int(x1 - rider_width * 0.25))
            crop_y1 = max(0, int(y1 - rider_height * 0.10))
            crop_x2 = min(width, int(x2 + rider_width * 0.25))
            crop_y2 = min(height, int(y1 + rider_height * 0.48))
            if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
                continue

            crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
            crop_result = model.predict(
                source=crop,
                conf=settings.roi_helmet_confidence,
                imgsz=settings.roi_image_size,
                device=settings.device,
                verbose=False,
            )[0]
            for item in self._parse_result(crop_result):
                bx1, by1, bx2, by2 = item.bbox
                refined.append(Detection(
                    class_name=item.class_name,
                    confidence=item.confidence,
                    bbox=(
                        bx1 + crop_x1,
                        by1 + crop_y1,
                        bx2 + crop_x1,
                        by2 + crop_y1,
                    ),
                ))
        return detections + refined

    def analyze_image(self, source: Path, artifact_dir: Path, progress: Callable[[int, str], None]) -> dict:
        model = self._get_model()
        context_model = self._get_context_model()
        progress(20, "正在解码图片")
        frame = cv2.imread(str(source))
        if frame is None:
            raise ValueError("无法解码图片，请使用有效的 JPG、JPEG、PNG 或 WEBP 文件")
        started = time.perf_counter()
        result = model.predict(
            source=frame,
            conf=settings.helmet_confidence,
            imgsz=settings.image_size,
            device=settings.device,
            verbose=False,
        )[0]
        context_result = context_model.predict(
            source=frame,
            classes=CONTEXT_CLASS_IDS,
            conf=settings.context_confidence,
            imgsz=settings.image_size,
            device=settings.device,
            verbose=False,
        )[0]
        progress(75, "正在执行违规关联规则")
        detections = self._parse_result(result) + self._parse_result(context_result)
        violations = evaluate_violations(detections)
        if any(item["code"] == "HELMET_UNCERTAIN" for item in violations):
            detections = self._refine_uncertain_headgear(
                frame, model, detections, violations
            )
            violations = evaluate_violations(detections)
        inference_ms = (time.perf_counter() - started) * 1000
        annotated = self._annotate(frame, detections, violations)
        confirmed = [item for item in violations if item["code"] not in {"HELMET_UNCERTAIN"}]
        visible_detections = [
            item for item in detections
            if normalize_label(item.class_name) in HELMET_CLASSES
            or (
                normalize_label(item.class_name) in NO_HELMET_CLASSES
                and any(
                    item.bbox == tuple(event.get("head_bbox", []))
                    for event in violations
                    if event.get("code") == "NO_HELMET"
                )
            )
        ]
        output_path = artifact_dir / "annotated.jpg"
        safe_imwrite(output_path, annotated, 92)
        annotated_url = f"/artifacts/{artifact_dir.name}/annotated.jpg"
        for index, event in enumerate(confirmed, start=1):
            event["evidence_url"] = annotated_url
            event["roi_url"] = self._save_event_roi(annotated, event, artifact_dir, index)
        progress(100, "分析完成")
        return {
            "media_type": "image",
            "width": int(frame.shape[1]),
            "height": int(frame.shape[0]),
            "inference_ms": round(inference_ms, 1),
            "detections": [item.to_dict() for item in visible_detections],
            "events": confirmed,
            "uncertain": [item for item in violations if item["code"] == "HELMET_UNCERTAIN"],
            "summary": {"objects": len(visible_detections), "violations": len(confirmed)},
            "annotated_url": annotated_url,
        }

    def analyze_video(self, source: Path, artifact_dir: Path, progress: Callable[[int, str], None]) -> dict:
        model = self._get_model()
        context_model = self._get_context_model()
        capture = cv2.VideoCapture(str(source))
        if not capture.isOpened():
            raise ValueError("无法解码视频，请使用有效的 MP4、AVI、MOV 或 MKV 文件")

        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        stride = max(1, round(fps / settings.video_sample_fps))
        sampled_total = max(1, frame_count // stride)
        event_hits: dict[tuple, int] = defaultdict(int)
        events_by_key: dict[tuple, dict] = {}
        sampled = 0
        frame_index = 0
        started = time.perf_counter()

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if frame_index % stride:
                    frame_index += 1
                    continue

                sampled += 1
                result = model.predict(
                    source=frame,
                    conf=settings.helmet_confidence,
                    imgsz=settings.image_size,
                    device=settings.device,
                    verbose=False,
                )[0]
                context_result = context_model.track(
                    source=frame,
                    persist=True,
                    tracker="bytetrack.yaml",
                    classes=CONTEXT_CLASS_IDS,
                    conf=settings.context_confidence,
                    imgsz=settings.image_size,
                    device=settings.device,
                    verbose=False,
                )[0]
                detections = self._parse_result(result) + self._parse_result(context_result)
                frame_violations = [
                    item for item in evaluate_violations(detections)
                    if item["code"] != "HELMET_UNCERTAIN"
                ]
                active_keys = set()
                for violation in frame_violations:
                    key = (violation["code"], violation.get("vehicle_track_id"))
                    active_keys.add(key)
                    event_hits[key] += 1
                    if event_hits[key] >= settings.video_confirm_frames and key not in events_by_key:
                        seconds = frame_index / fps
                        evidence_name = f"event_{len(events_by_key) + 1:03d}.jpg"
                        evidence_path = artifact_dir / evidence_name
                        annotated = self._annotate(frame, detections, frame_violations)
                        safe_imwrite(evidence_path, annotated, 92)
                        event_index = len(events_by_key) + 1
                        events_by_key[key] = {
                            **violation,
                            "timestamp_seconds": round(seconds, 2),
                            "frame_index": frame_index,
                            "consecutive_frames": event_hits[key],
                            "evidence_url": f"/artifacts/{artifact_dir.name}/{evidence_name}",
                            "roi_url": self._save_event_roi(
                                annotated, violation, artifact_dir, event_index
                            ),
                        }
                for key in list(event_hits):
                    if key not in active_keys:
                        event_hits[key] = 0

                progress(min(98, round(sampled / sampled_total * 100)), f"已分析 {sampled}/{sampled_total} 个采样帧")
                frame_index += 1
        finally:
            capture.release()

        progress(100, "分析完成")
        events = list(events_by_key.values())
        return {
            "media_type": "video",
            "width": width,
            "height": height,
            "fps": round(fps, 2),
            "duration_seconds": round(frame_count / fps, 2) if fps else 0,
            "sampled_frames": sampled,
            "processing_seconds": round(time.perf_counter() - started, 2),
            "events": events,
            "summary": {"objects": None, "violations": len(events)},
        }


engine = YoloInferenceEngine()
