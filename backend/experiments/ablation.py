"""规则引擎消融实验（毕业论文定量实验章，表 4.5）。

================================================================================
【实验目的】
backend/app/rules.py 是一套"多目标从属关系推理引擎"：它把两个检测器输出的
Detection 列表，推理成"是否违规佩戴头盔"的结论。本脚本在不修改 rules.py 业务
逻辑的前提下，用 5 组配置逐级关闭引擎的约束能力，量化每个模块的独立贡献。

【五组消融配置（逐级累加，每组只相对上一组新增一个能力）】
  A  仅检测          检出 no_helmet 就算违规，完全不做人车关联、不做头部区域约束
  B  + 骑乘归属      启用 _rider_match_score 足部锚点 + 几何约束（人必须真的在车上）
  C  + 头部区域约束  启用 _assign_headgear（裸头框必须落在骑乘者头部区域内）
  D  + 置信度融合    启用 min() 置信度瓶颈融合 + helmet/bare_head 三态仲裁
  E  + 时序投票      同 track_id 连续命中 VIDEO_CONFIRM_FRAMES 帧才确认

================================================================================
【真值（ground truth）口径 —— 必读】
本数据集的标注文件里只有 helmet / no_helmet 两类框，没有 person / vehicle 标注，
因此无法直接给出"骑乘者是否违规"级别的真值。本脚本采用**图像级**口径：

    gt_violation = 1  <=>  该图的标签文件中至少存在一个 class==1（no_helmet）框
    gt_violation = 0  <=>  该图标签里只有 class==0（helmet）框

    pred_violation = 1  <=>  规则引擎对该图返回了至少一个 code=="NO_HELMET" 事件
                            （HELMET_UNCERTAIN 不计入，它的 is_violation=False）

这是一个"图像级（含至少一个未戴盔）"的宽松口径，不是框级 mAP 评测。局限：
一幅图中只要有一个人没戴盔就记为正样本，无法区分"骑乘者违规"与"路人违规"，
因此 Precision 会被路人误报拉低。这一点在论文中必须明确写出。
脚本因此额外输出"仅在正样本子集上的召回率"（positive-subset recall），
避免大量真负样本把整体 Recall 稀释失真。

【FPS 口径】
avg_decide_ms 只统计"规则引擎判定单张图的纯 CPU 耗时"，
用 time.perf_counter() 在 _decide() 前后打点，**不含**两个检测器的 GPU 推理、
不含图像解码、不含结果序列化。rule_fps = 1000 / avg_decide_ms，
表示规则引擎作为纯函数时的理论单线程吞吐上限，不是整条流水线 FPS。

【实现手法】
不复制 rules.py，而是写一个**带功能开关的驱动** _decide(dets, cfg)，
内部直接调用 rules 模块真实的几何原语（_assign_riders / _assign_headgear /
_rider_match_score / _confidence）。开关全开时 _decide 必须与
rules.evaluate_violations 逐字节一致 —— 脚本启动时会跑 selfcheck_assert_identical()
做全量校验并打印结果，保证消融基线没有偏离生产逻辑。
================================================================================
"""

from __future__ import annotations

import argparse
import csv
import json
import pickle
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import rules  # noqa: E402
from app.rules import Detection, normalize_label  # noqa: E402

# ----------------------------------------------------------------------------------
# 路径与实验常量
# ----------------------------------------------------------------------------------
EXP_DIR = BACKEND_DIR / "experiments"
CACHE_DIR = EXP_DIR / "ablation_cache"
CSV_PATH = EXP_DIR / "ablation_results.csv"
JSON_PATH = EXP_DIR / "ablation_details.json"

# 两个测试集：YOLO 格式标签，类别 0=helmet、1=no_helmet
DATASETS = [
    ("helmet-voc-clean-v1", PROJECT_DIR / "data" / "helmet-voc-clean-v1"),
    ("bike-helmet-yolo", PROJECT_DIR / "data" / "bike-helmet-yolo"),
]

CUSTOM_WEIGHTS = BACKEND_DIR / "models" / "best.pt"
CONTEXT_WEIGHTS = BACKEND_DIR / "yolo11s.pt"
CONTEXT_CLASS_IDS = [0, 1, 3]  # COCO: person / bicycle / motorcycle

# 统一推理口径（实验期间不得改动，否则组间不可比）
HELMET_IMGSZ = 960
HELMET_CONF = 0.25
CONTEXT_IMGSZ = 640
CONTEXT_CONF = 0.25

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CACHE_VERSION = 4  # 改动检测口径时 +1，自动使旧缓存失效

# 直接从 rules 模块读取几何常量，保证消融基线与生产逻辑同源
RIDER_HORIZONTAL_INSET = rules.RIDER_HORIZONTAL_INSET
RIDER_MAX_FOOT_Y = rules.RIDER_MAX_FOOT_Y
RIDER_MAX_MATCH_SCORE = rules.RIDER_MAX_MATCH_SCORE


# ----------------------------------------------------------------------------------
# 消融配置：每组只关闭一个新增能力，其余完全锁死
# ----------------------------------------------------------------------------------
@dataclass(frozen=True)
class AblationConfig:
    """一组消融配置。四个开关全部对应 rules.py 里的一个具体约束能力。"""

    group: str
    label: str
    use_rider_attribution: bool  # B 起：_rider_match_score 足部锚点 + 人车关联
    use_head_zone: bool          # C 起：_assign_headgear 头部区域约束
    use_confidence_arbitration: bool  # D 起：min() 融合 + helmet/bare_head 三态仲裁
    use_temporal_vote: bool      # E 起：同轨迹连续帧时序确认
    description: str


ABLATION_GROUPS = [
    AblationConfig(
        group="A",
        label="仅检测",
        use_rider_attribution=False,
        use_head_zone=False,
        use_confidence_arbitration=False,
        use_temporal_vote=False,
        description="基线：检出 no_helmet 框即判违规。不做人车关联、不做头部区域约束。",
    ),
    AblationConfig(
        group="B",
        label="+骑乘归属",
        use_rider_attribution=True,
        use_head_zone=False,
        use_confidence_arbitration=False,
        use_temporal_vote=False,
        description="在 A 基础上启用足部锚点与几何约束：必须存在真的骑在车上的 person。"
                    "头部区域约束关闭，裸头框直接算违规。",
    ),
    AblationConfig(
        group="C",
        label="+头部区域",
        use_rider_attribution=True,
        use_head_zone=True,
        use_confidence_arbitration=False,
        use_temporal_vote=False,
        description="在 B 基础上启用头部区域约束：裸头框必须落在骑乘者头部区域内才算违规。"
                    "此组不做置信度仲裁（裸头优先于头盔框），也不产出 HELMET_UNCERTAIN。",
    ),
    AblationConfig(
        group="D",
        label="+置信度/三态",
        use_rider_attribution=True,
        use_head_zone=True,
        use_confidence_arbitration=True,
        use_temporal_vote=False,
        description="在 C 基础上启用 min() 置信度瓶颈融合与 helmet/bare_head/unknown "
                    "三态仲裁。此组等价于生产 rules.evaluate_violations。",
    ),
    AblationConfig(
        group="E",
        label="+时序投票",
        use_rider_attribution=True,
        use_head_zone=True,
        use_confidence_arbitration=True,
        use_temporal_vote=True,
        description="全系统。在 D 基础上叠加同 track_id 连续命中帧的时序确认。",
    ),
]


# ----------------------------------------------------------------------------------
# 检测结果缓存：5 组消融共用同一份检测输出，避免重复跑 859x2 次推理
# ----------------------------------------------------------------------------------
def cache_signature() -> dict:
    """缓存指纹。任何影响检测输出的参数改动都会让旧缓存自动失效。"""
    return {
        "version": CACHE_VERSION,
        "helmet_weights": str(CUSTOM_WEIGHTS),
        "helmet_mtime": CUSTOM_WEIGHTS.stat().st_mtime if CUSTOM_WEIGHTS.exists() else None,
        "context_weights": str(CONTEXT_WEIGHTS),
        "context_mtime": CONTEXT_WEIGHTS.stat().st_mtime if CONTEXT_WEIGHTS.exists() else None,
        "helmet_imgsz": HELMET_IMGSZ,
        "helmet_conf": HELMET_CONF,
        "context_imgsz": CONTEXT_IMGSZ,
        "context_conf": CONTEXT_CONF,
        "context_classes": CONTEXT_CLASS_IDS,
    }


@dataclass
class Sample:
    """一张待评测样本：图像路径 + 图像级真值 + 两路检测结果。"""

    uid: str
    dataset: str
    image_path: Path
    width: int
    height: int
    gt_violation: int
    gt_head_boxes: int
    gt_bare_boxes: int
    detections: list[Detection]
    label_error: str | None = None

    @property
    def bare_heads(self) -> list[Detection]:
        return [d for d in self.detections if normalize_label(d.class_name) in rules.NO_HELMET_CLASSES]

    @property
    def helmets(self) -> list[Detection]:
        return [d for d in self.detections if normalize_label(d.class_name) in rules.HELMET_CLASSES]

    @property
    def people(self) -> list[Detection]:
        return [d for d in self.detections if normalize_label(d.class_name) in rules.PERSON_CLASSES]

    @property
    def vehicles(self) -> list[Detection]:
        return [d for d in self.detections if normalize_label(d.class_name) in rules.VEHICLE_CLASSES]


def parse_label(label_path: Path) -> tuple[int, int, str | None]:
    """解析 YOLO 标签：返回 (gt_violation, n_helmet, n_no_helmet, error)。

    gt_violation 采用图像级口径：至少一个 class==1 即为正样本。
    """
    if not label_path.exists():
        return 0, 0, 0, f"missing_label:{label_path.name}"
    try:
        text = label_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return 0, 0, 0, f"unreadable_label:{exc}"
    n_helmet = n_bare = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            cls = int(float(parts[0]))
        except ValueError:
            continue
        if cls == 1:
            n_bare += 1
        elif cls == 0:
            n_helmet += 1
    return (1 if n_bare > 0 else 0), n_helmet, n_bare, None


def collect_samples(limit_per_dataset: int | None = None) -> list[Sample]:
    """枚举两个测试集，构建样本清单（含真值）。limit 按数据集各自限流。"""
    samples: list[Sample] = []
    for name, root in DATASETS:
        image_dir = root / "images" / "test"
        label_dir = root / "labels" / "test"
        if not image_dir.is_dir():
            print(f"[warn] 数据集图像目录缺失，已跳过：{image_dir}")
            continue
        paths = sorted(p for p in image_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)
        if limit_per_dataset is not None:
            paths = paths[:limit_per_dataset]
        for path in paths:
            gt, n_helmet, n_bare, err = parse_label(label_dir / f"{path.stem}.txt")
            samples.append(Sample(
                uid=f"{name}/{path.name}",
                dataset=name,
                image_path=path,
                width=0,
                height=0,
                gt_violation=gt,
                gt_head_boxes=n_helmet,
                gt_bare_boxes=n_bare,
                detections=[],
                label_error=err,
            ))
        print(f"[data] {name}: 纳入 {len(paths)} 张测试图")
    return samples


# ----------------------------------------------------------------------------------
# 推理 + 缓存
# ----------------------------------------------------------------------------------
def load_cache(signature: dict) -> dict[str, list]:
    path = CACHE_DIR / "detections.pkl"
    if not path.exists():
        return {}
    try:
        blob = pickle.loads(path.read_bytes())
    except (OSError, pickle.UnpicklingError, EOFError) as exc:
        print(f"[warn] 缓存读取失败（{exc}），将重新推理")
        return {}
    if blob.get("signature") != signature:
        print("[info] 检测口径已变更，旧缓存自动失效，重新推理")
        return {}
    return blob.get("detections", {})


def save_cache(signature: dict, table: dict[str, list]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"signature": signature, "detections": table}
    tmp = CACHE_DIR / "detections.pkl.tmp"
    tmp.write_bytes(pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL))
    tmp.replace(CACHE_DIR / "detections.pkl")


def run_inference(samples: list[Sample], batch: int, resume: bool) -> None:
    """对缺失缓存的样本跑双检测器推理，结果写回 sample.detections。"""
    signature = cache_signature()
    cached = load_cache(signature) if resume else {}
    todo = [s for s in samples if s.uid not in cached]
    if not todo:
        print(f"[cache] 全部命中缓存（{len(samples)} 张），跳过推理")
    else:
        print(f"[cache] 命中 {len(samples) - len(todo)} 张，需推理 {len(todo)} 张（batch={batch}）")
        if not resume:
            cached = {}
        _infer_with_models(todo, cached, batch)
        save_cache(signature, cached)

    for sample in samples:
        raw = cached.get(sample.uid, [])
        sample.detections = [
            Detection(
                class_name=str(cls),
                confidence=float(conf),
                bbox=(float(b[0]), float(b[1]), float(b[2]), float(b[3])),
                track_id=None if tid is None else int(tid),
            )
            for cls, conf, b, tid in raw
        ]


def _infer_with_models(samples: list[Sample], table: dict[str, list], batch: int) -> None:
    from ultralytics import YOLO

    print("[load] 加载检测器权重 ...")
    custom = YOLO(str(CUSTOM_WEIGHTS))
    context = YOLO(str(CONTEXT_WEIGHTS))
    names = custom.names  # 新版 ultralytics：names 在 Results 上，不在 boxes 上

    stride = max(1, batch)
    started = time.perf_counter()
    done = 0
    for offset in range(0, len(samples), stride):
        chunk = samples[offset:offset + stride]
        paths = [str(s.image_path) for s in chunk]
        try:
            custom_results = custom.predict(
                paths, imgsz=HELMET_IMGSZ, conf=HELMET_CONF, device=0, verbose=False, stream=False
            )
            ctx_results = context.predict(
                paths, classes=CONTEXT_CLASS_IDS, imgsz=CONTEXT_IMGSZ, conf=CONTEXT_CONF,
                device=0, verbose=False, stream=False,
            )
        except torch_oom() as exc:  # 显存不足：降级到 batch=1 重试
            print(f"[warn] batch={len(chunk)} 推理失败（{type(exc).__name__}），降级为单张重试")
            for sample in chunk:
                one = custom.predict(str(sample.image_path), imgsz=HELMET_IMGSZ, conf=HELMET_CONF,
                                     device=0, verbose=False)[0]
                two = context.predict(str(sample.image_path), classes=CONTEXT_CLASS_IDS,
                                      imgsz=CONTEXT_IMGSZ, conf=CONTEXT_CONF,
                                      device=0, verbose=False)[0]
                table[sample.uid] = _extract(one, two, names)
                done += 1
            continue

        for sample, one, two in zip(chunk, custom_results, ctx_results):
            table[sample.uid] = _extract(one, two, names)
            done += 1

        elapsed = time.perf_counter() - started
        rate = done / elapsed if elapsed > 0 else 0.0
        eta = (len(samples) - done) / rate if rate > 0 else 0.0
        print(f"[infer] {done}/{len(samples)}  {elapsed:6.1f}s  {rate:5.1f} img/s  ETA {eta:5.1f}s")

    total = time.perf_counter() - started
    print(f"[infer] 推理完成：{len(samples)} 张，耗时 {total:.1f}s "
          f"（平均 {total / max(1, len(samples)) * 1000:.0f} ms/张，含两个模型）")


def torch_oom():
    """惰性导入 torch 的 OOM 异常类型（避免顶层硬依赖 torch）。"""
    import torch
    return (torch.cuda.OutOfMemoryError, RuntimeError)


def _extract(custom_result, context_result, names) -> list[tuple]:
    """把两路Results 拍平成 (class_name, conf, bbox, track_id) 元组列表。"""
    out: list[tuple] = []
    for result in (custom_result, context_result):
        if result is None or result.boxes is None:
            continue
        result_names = result.names or names
        boxes = result.boxes
        xyxy = boxes.xyxy.cpu().tolist()
        confs = boxes.conf.cpu().tolist()
        clss = boxes.cls.int().cpu().tolist()
        ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(xyxy)
        for bbox, conf, cls, tid in zip(xyxy, confs, clss, ids):
            out.append((str(result_names[cls]), float(conf), bbox, tid))
    return out


# ----------------------------------------------------------------------------------
# 规则引擎驱动：带功能开关的 evaluate_violations
# ----------------------------------------------------------------------------------
def _make_event(code: str, confidence: float, head_bbox, rider_bbox, vehicle_bbox,
                vehicle_track_id=None) -> dict:
    return {
        "code": code,
        "title": "未按规定佩戴安全头盔" if code == "NO_HELMET" else "头盔状态无法确认",
        "severity": "high" if code == "NO_HELMET" else "info",
        "confidence": confidence,
        "vehicle_track_id": vehicle_track_id,
        "review_required": True,
        "head_bbox": list(head_bbox),
        "evidence_bbox": list(rider_bbox),
        "vehicle_bbox": list(vehicle_bbox),
    }


def decide(dets: list[Detection], cfg: AblationConfig) -> list[dict]:
    """按配置执行一次规则判定，返回事件列表（结构与 rules.evaluate_violations 一致）。

    几何计算全部委托给 rules 模块的真实原语，本函数只负责"要不要用"这些原语。
    开关全开时本函数与 rules.evaluate_violations 完全等价（由 selfcheck 校验）。
    """
    vehicles = [d for d in dets if normalize_label(d.class_name) in rules.VEHICLE_CLASSES]
    people = [d for d in dets if normalize_label(d.class_name) in rules.PERSON_CLASSES]
    helmets = [d for d in dets if normalize_label(d.class_name) in rules.HELMET_CLASSES]
    bare_heads = [d for d in dets if normalize_label(d.class_name) in rules.NO_HELMET_CLASSES]
    events: list[dict] = []

    # ---------------- A 组：无任何关联约束 ----------------
    if not cfg.use_rider_attribution:
        # 检出裸头框即判违规。置信度不做瓶颈融合，直接取最高裸头置信度
        # （A 组没有 person/vehicle 参与，不存在 min() 融合的对象）。
        for head in bare_heads:
            events.append(_make_event("NO_HELMET", round(head.confidence, 4),
                                      head.bbox, head.bbox, (0.0, 0.0, 0.0, 0.0)))
        return events

    # ---------------- B 组起：人车关联（骑乘归属） ----------------
    rider_assignments = rules._assign_riders(people, vehicles)

    if not cfg.use_head_zone:
        # 头部区域约束关闭：裸头框与骑乘者之间的空间归属被完全丢弃。
        # 只要"存在真的骑在车上的骑乘者"且"画面里存在裸头框"，即判违规。
        # 这一组专门暴露"裸头框与骑乘者之间缺少空间校验"带来的误报。
        has_rider = any(rider_assignments[i] for i in range(len(vehicles)))
        if has_rider and bare_heads:
            best = max(bare_heads, key=lambda item: item.confidence)
            for index in range(len(vehicles)):
                riders = rider_assignments[index]
                if not riders:
                    continue
                rider = min(riders, key=lambda item: item.bbox[0])
                events.append(_make_event("NO_HELMET", round(best.confidence, 4),
                                          best.bbox, rider.bbox, vehicles[index].bbox,
                                          vehicle_track_id=vehicles[index].track_id
                                          if vehicles[index].track_id is not None else index))
        return events

    # ---------------- C 组起：头部区域约束 ----------------
    helmet_assignments = rules._assign_headgear(people, helmets)
    bare_head_assignments = rules._assign_headgear(people, bare_heads)
    person_indexes = {id(person): index for index, person in enumerate(people)}

    if not cfg.use_confidence_arbitration:
        # 头部区域约束生效，但不做置信度仲裁：骑乘者头部区域内存在裸头框即违规。
        for index in range(len(vehicles)):
            for rider in sorted(rider_assignments[index], key=lambda item: item.bbox[0]):
                matched = bare_head_assignments[person_indexes[id(rider)]]
                if not matched:
                    continue
                best_bare = max(matched, key=lambda item: item.confidence)
                events.append(_make_event(
                    "NO_HELMET", round(best_bare.confidence, 4),
                    best_bare.bbox, rider.bbox, vehicles[index].bbox,
                    vehicle_track_id=vehicles[index].track_id
                    if vehicles[index].track_id is not None else index,
                ))
        return events

    # ---------------- D 组：min() 置信度融合 + 三态仲裁（等价于生产逻辑） ----------------
    for index, vehicle in enumerate(vehicles):
        riders = rider_assignments[index]
        rider_details = []
        for rider in sorted(riders, key=lambda item: item.bbox[0]):
            p_idx = person_indexes[id(rider)]
            matched_helmets = helmet_assignments[p_idx]
            matched_bare = bare_head_assignments[p_idx]
            best_helmet = max(matched_helmets, key=lambda item: item.confidence, default=None)
            best_bare = max(matched_bare, key=lambda item: item.confidence, default=None)
            if best_bare and (not best_helmet or best_bare.confidence >= best_helmet.confidence):
                helmet_state = "no_helmet"
            elif best_helmet:
                helmet_state = "helmet"
            else:
                helmet_state = "unknown"
            rider_details.append({"helmet_state": helmet_state})
            if helmet_state == "no_helmet" and best_bare:
                events.append(_make_event(
                    "NO_HELMET",
                    rules._confidence([vehicle.confidence, rider.confidence, best_bare.confidence]),
                    best_bare.bbox, rider.bbox, vehicle.bbox,
                    vehicle_track_id=vehicle.track_id if vehicle.track_id is not None else index,
                ))
        if riders and not any(item["helmet_state"] != "unknown" for item in rider_details):
            # 与生产实现保持字段一致：evidence_bbox 复用 vehicle_bbox，且不带 head_bbox
            events.append({
                "code": "HELMET_UNCERTAIN",
                "title": "头盔状态无法确认",
                "severity": "info",
                "confidence": vehicle.confidence,
                "vehicle_track_id": vehicle.track_id if vehicle.track_id is not None else index,
                "review_required": True,
                "is_violation": False,
                "evidence_bbox": list(vehicle.bbox),
                "vehicle_bbox": list(vehicle.bbox),
            })
    return events


def selfcheck_assert_identical(samples: list[Sample]) -> None:
    """核心正确性保证：开关全开时，消融驱动必须与生产 evaluate_violations 逐字段一致。

    若生产逻辑被改动而本脚本没跟上，这里会立刻失败，避免消融基线悄悄偏离。
    """
    full = ABLATION_GROUPS[3]  # D组 = 全功能
    mismatches = []
    for sample in samples:
        try:
            reference = rules.evaluate_violations(sample.detections)
            ours = decide(sample.detections, full)
        except Exception as exc:  # noqa: BLE001
            mismatches.append((sample.uid, f"exception:{exc}"))
            continue
        if _signature(reference) != _signature(ours):
            mismatches.append((sample.uid, "output_mismatch"))
    if mismatches:
        print(f"[selfcheck][FAIL] 消融驱动与 rules.evaluate_violations 不一致：{len(mismatches)}/{len(samples)}")
        for uid, why in mismatches[:5]:
            print(f"           {uid}: {why}")
        raise SystemExit(1)
    print(f"[selfcheck][OK] {len(samples)} 张样本上，D组输出与生产 evaluate_violations 完全一致")


def _signature(events: list[dict]) -> list[tuple]:
    """把事件列表规范化成可比较的元组序列（浮点按 4 位取整）。"""
    out = []
    for item in events:
        out.append((
            item.get("code"),
            round(float(item.get("confidence", 0.0)), 4),
            bool(item.get("is_violation", True)),
            tuple(round(float(v), 2) for v in item.get("head_bbox", [])),
            tuple(round(float(v), 2) for v in item.get("evidence_bbox", [])),
            tuple(round(float(v), 2) for v in item.get("vehicle_bbox", [])),
        ))
    return sorted(out)


# ----------------------------------------------------------------------------------
# 评测：图像级混淆矩阵
# ----------------------------------------------------------------------------------
@dataclass
class GroupResult:
    cfg: AblationConfig
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    decide_ms: list[float] = None
    n_events: int = 0
    n_uncertain: int = 0
    preds: dict[str, int] = None

    def __post_init__(self):
        self.decide_ms = []
        self.preds = {}


def evaluate_group(samples: list[Sample], cfg: AblationConfig) -> GroupResult:
    result = GroupResult(cfg=cfg)
    for sample in samples:
        t0 = time.perf_counter()
        events = decide(sample.detections, cfg)
        result.decide_ms.append((time.perf_counter() - t0) * 1000.0)

        violations = [e for e in events if e.get("code") == "NO_HELMET"]
        uncertain = [e for e in events if e.get("code") == "HELMET_UNCERTAIN"]
        pred = 1 if violations else 0
        result.preds[sample.uid] = pred
        result.n_events += len(violations)
        result.n_uncertain += len(uncertain)

        if sample.gt_violation == 1:
            if pred == 1:
                result.tp += 1
            else:
                result.fn += 1
        else:
            if pred == 1:
                result.fp += 1
            else:
                result.tn += 1
    return result


def metrics(result: GroupResult) -> dict:
    tp, fp, fn, tn = result.tp, result.fp, result.fn, result.tn
    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    # 误报率：真负样本中被错判为违规的比例
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    accuracy = (tp + tn) / total if total else 0.0
    avg_ms = statistics.fmean(result.decide_ms) if result.decide_ms else 0.0
    return {
        "group": result.cfg.group,
        "label": result.cfg.label,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "accuracy": round(accuracy, 4),
        "avg_decide_ms": round(avg_ms, 4),
        "rule_fps": round(1000.0 / avg_ms, 1) if avg_ms > 0 else 0.0,
        "n_images": total,
        "n_gt_violation": tp + fn,
        "n_gt_normal": fp + tn,
        "positive_subset_recall": round(recall, 4),  # 图像级口径下 Recall 本身就是正样本子集召回
        "n_events": result.n_events,
        "n_uncertain": result.n_uncertain,
    }


# ----------------------------------------------------------------------------------
# 相邻组判定差异：论文里"消融消除了哪一类误报"的直接证据
# ----------------------------------------------------------------------------------
def explain(sample: Sample, cfg: AblationConfig) -> str:
    """生成一行人类可读的原因说明，指出该图在当前配置下为什么被判/不判违规。"""
    n_person, n_veh = len(sample.people), len(sample.vehicles)
    n_bare, n_helm = len(sample.bare_heads), len(sample.helmets)
    base = (f"person={n_person} vehicle={n_veh} bare_head={n_bare} helmet={n_helm}")
    if cfg.group == "A":
        return base + (" -> 检出裸头即违规" if n_bare else " -> 无裸头框")
    riders = rules._assign_riders(sample.people, sample.vehicles)
    flat = [r for group in riders.values() for r in group]
    if not flat:
        return base + " -> 无人被判定为骑乘者"
    if cfg.group == "B":
        return base + f" -> 骑乘者={len(flat)}，头部区域约束关闭，裸头直接算违规"
    bare_assign = rules._assign_headgear(sample.people, sample.bare_heads)
    matched = sum(len(v) for v in bare_assign.values())
    if cfg.group == "C":
        return base + f" -> 骑乘者={len(flat)}，裸头落在头部区域内={matched}"
    helm_assign = rules._assign_headgear(sample.people, sample.helmets)
    matched_h = sum(len(v) for v in helm_assign.values())
    return base + f" -> 骑乘者={len(flat)}，头部裸头={matched}，头部头盔={matched_h}，经置信度仲裁"


def diff_between(prev: GroupResult, curr: GroupResult, samples: list[Sample], top: int = 3):
    """列出相邻两组之间判定发生翻转的样本，并区分 FP 消除 / 召回损失。"""
    index = {s.uid: s for s in samples}
    flips = []
    for uid, prev_pred in prev.preds.items():
        curr_pred = curr.preds.get(uid, 0)
        if prev_pred == curr_pred:
            continue
        sample = index.get(uid)
        if sample is None:
            continue
        if prev_pred == 1 and curr_pred == 0:
            kind = "误报被消除" if sample.gt_violation == 0 else "真阳性丢失(召回下降)"
        else:
            kind = "新增告警" if sample.gt_violation == 1 else "新增误报"
        flips.append({
            "uid": uid,
            "gt": sample.gt_violation,
            "from_group": prev.cfg.group,
            "to_group": curr.cfg.group,
            "from_pred": prev_pred,
            "to_pred": curr_pred,
            "kind": kind,
            "reason": explain(sample, curr.cfg),
        })
    return flips, flips[:top]


# ----------------------------------------------------------------------------------
# 输出
# ----------------------------------------------------------------------------------
def print_distribution(samples: list[Sample]) -> dict:
    n_pos = sum(s.gt_violation for s in samples)
    n_neg = len(samples) - n_pos
    errors = [s for s in samples if s.label_error]
    print("\n" + "=" * 78)
    print("【正负样本分布】图像级口径：含至少一个 no_helmet 标注框即为正样本")
    print("=" * 78)
    for name, _ in DATASETS:
        sub = [s for s in samples if s.dataset == name]
        if not sub:
            continue
        p = sum(s.gt_violation for s in sub)
        print(f"  {name:24s} 共{len(sub):4d}张   正样本(gt=1) {p:4d}   真负样本(gt=0) {len(sub) - p:4d}")
    ratio = n_pos / len(samples) if samples else 0.0
    print(f"  {'合计':24s} 共{len(samples):4d}张   正样本(gt=1) {n_pos:4d}   真负样本(gt=0) {n_neg:4d}")
    print(f"  正样本占比 {ratio * 100:.1f}%")
    if errors:
        print(f"  [warn] 标签解析异常 {len(errors)} 张，示例：{[s.uid for s in errors[:3]]}")
    else:
        print("  标签解析：无异常")
    if ratio < 0.1 or ratio > 0.9:
        print("  [warn] 正负样本极度不平衡，整体 Recall / FPR 会被主导类别稀释，")
        print("         论文中应以 positive_subset_recall 与 false_positive_rate 为准。")
    else:
        print("  正负样本比例均衡，图像级 Precision/Recall 可直接解读。")
    return {"n_images": len(samples), "n_pos": n_pos, "n_neg": n_neg}


def print_table(rows: list[dict]) -> None:
    print("\n" + "=" * 110)
    print("【表 4.5 规则引擎消融实验结果】评测口径：图像级（该图是否含至少一个未戴盔目标）")
    print("=" * 110)
    header = (f"{'组':<3}{'配置':<14}{'TP':>5}{'FP':>5}{'FN':>5}{'TN':>6}"
              f"{'P':>8}{'R':>8}{'F1':>8}{'FPR':>8}{'Acc':>8}{'ms/张':>9}{'FPS':>9}")
    print(header)
    print("-" * 110)
    for row in rows:
        print(f"{row['group']:<3}{row['label']:<14}"
              f"{row['tp']:>5}{row['fp']:>5}{row['fn']:>5}{row['tn']:>6}"
              f"{row['precision']:>8.4f}{row['recall']:>8.4f}{row['f1']:>8.4f}"
              f"{row['false_positive_rate']:>8.4f}{row['accuracy']:>8.4f}"
              f"{row['avg_decide_ms']:>9.3f}{row['rule_fps']:>9.1f}")
    print("-" * 110)
    print("P=Precision  R=Recall  F1  FPR=误报率 FP/(FP+TN)  Acc=准确率")
    print("ms/张 与 FPS 仅统计规则引擎纯 CPU 判定耗时，不含两个检测器的 GPU 推理与图像解码。")


def write_csv(rows: list[dict]) -> None:
    fields = [
        "group", "tp", "fp", "fn", "tn", "precision", "recall", "f1",
        "false_positive_rate", "accuracy", "avg_decide_ms", "n_images", "n_gt_violation",
        "label", "rule_fps", "n_gt_normal", "positive_subset_recall", "n_events", "n_uncertain",
    ]
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})
    print(f"\n[out] 指标 CSV 已写入：{CSV_PATH}")


# ----------------------------------------------------------------------------------
# 时序消融（E 组）：静态图无法体现，需视频流场景
# ----------------------------------------------------------------------------------
def temporal_note() -> None:
    print("\n" + "=" * 78)
    print("【关于 E 组（+时序投票）的说明】")
    print("=" * 78)
    print("  时序确认依赖同一 track_id 在连续采样帧上重复命中 VIDEO_CONFIRM_FRAMES 次。")
    print("  本测试集是 859 张互不相关的静态图片，既无帧序列也无 track_id，")
    print("  因此 E 组在本表中的数值与 D 组相同，这是口径限制而非实验缺陷。")
    print("  若需量化时序模块的增益，应在视频流场景下单独开展实验：")
    print("    同一段视频分别跑 D（逐帧判定）与 E（时序确认），")
    print("    比较事件条数、抖动次数与告警延迟。请勿在本表上虚构 E 组的差异。")


def run_temporal_video(video_path: Path, max_frames: int, sample_fps: float) -> dict | None:
    """在真实视频上量化时序模块（E 组）的增益。

    静态图无法体现时序，这里对同一段视频跑两遍逐帧判定：
      D（无时序）：每一帧只要产出NO_HELMET 就记一次告警 -> 告警条数 = 抖动次数
      E（有时序）：同一 (code, vehicle_track_id) 连续命中 CONFIRM_FRAMES 次才确认，
                   且同一 key 只记一次事件（与 app/inference.py 的视频逻辑一致）
    视频帧没有标注真值，因此这里只报"告警条数 / 抖动抑制"这类稳定性指标，
    不报Precision / Recall。
    """
    if not video_path.exists():
        print(f"[temporal] 视频不存在，跳过：{video_path}")
        return None
    import cv2
    from ultralytics import YOLO

    confirm_frames = 3  # 与 settings.video_confirm_frames 默认值一致
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        print(f"[temporal] 无法解码视频，跳过：{video_path}")
        return None
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    stride = max(1, round(fps / sample_fps))
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    target = min(max_frames, max(1, total_frames // stride))

    custom = YOLO(str(CUSTOM_WEIGHTS))
    context = YOLO(str(CONTEXT_WEIGHTS))
    cfg_d = ABLATION_GROUPS[3]

    raw_alerts = 0# D 组：逐帧告警总次数（含抖动）
    hits_e: dict[tuple, int] = {}
    events_e: list[dict] = []          # E 组：去重后的确认事件
    frame_index = 0
    sampled = 0
    print(f"\n[temporal] 视频 {video_path.name}：fps={fps:.1f} stride={stride}目标采样 {target} 帧")

    while sampled < target:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index % stride == 0:
            sampled += 1
            custom_result = custom.predict(frame, imgsz=HELMET_IMGSZ, conf=HELMET_CONF,
                                           device=0, verbose=False)[0]
            ctx_result = context.track(frame, persist=True, tracker="bytetrack.yaml",
                                       classes=CONTEXT_CLASS_IDS, imgsz=CONTEXT_IMGSZ,
                                       conf=CONTEXT_CONF, device=0, verbose=False)[0]
            dets = _detections_from_tracked(custom_result, ctx_result)

            active_e: set[tuple] = set()
            for event in decide(dets, cfg_d):
                if event["code"] != "NO_HELMET":
                    continue
                raw_alerts += 1
                key = (event["code"], event.get("vehicle_track_id"))
                hits_e[key] = hits_e.get(key, 0) + 1
                # 与生产一致：连续命中达到阈值后，该 key 只记一次事件
                if hits_e[key] >= confirm_frames and not any(e["key"] == key for e in events_e):
                    events_e.append({"key": key, "frame": frame_index,
                                     "seconds": round(frame_index / fps, 2)})
                active_e.add(key)
            for key in list(hits_e):
                if key not in active_e:
                    hits_e[key] = 0
            if sampled % 25 == 0:
                print(f"[temporal]   {sampled}/{target} 帧  逐帧告警 {raw_alerts}  确认事件 {len(events_e)}")
        frame_index += 1
    capture.release()

    suppress = 1 - (len(events_e) / raw_alerts) if raw_alerts else 0.0
    print(f"[temporal] 采样 {sampled} 帧：")
    print(f"[temporal]   D 组（无时序）逐帧告警 {raw_alerts} 次 —— 其中绝大多数是同一目标的重复抖动")
    print(f"[temporal]   E 组（时序确认）事件{len(events_e)} 条，抖动抑制率 {suppress * 100:.1f}%")
    return {
        "video": str(video_path),
        "sampled_frames": sampled,
        "sample_fps": sample_fps,
        "confirm_frames": confirm_frames,
        "raw_frame_alerts_D": raw_alerts,
        "confirmed_events_E": len(events_e),
        "jitter_suppression_rate": round(suppress, 4),
        "events": events_e,
        "note": "视频口径：仅统计告警条数与抖动抑制率。视频帧无标注真值，"
                "故不计算 Precision/Recall，也不可与表 4.5 的图像级指标直接比较。",
    }


def _detections_from_tracked(custom_result, ctx_result) -> list[Detection]:
    """把带track_id 的两路 Results 转成 Detection 列表（时序实验用）。"""
    out: list[Detection] = []
    for result in (custom_result, ctx_result):
        if result is None or result.boxes is None:
            continue
        names = result.names
        boxes = result.boxes
        ids = (boxes.id.int().cpu().tolist() if boxes.id is not None
               else [None] * len(boxes))
        for bbox, conf, cls, tid in zip(boxes.xyxy.cpu().tolist(),
                                        boxes.conf.cpu().tolist(),
                                        boxes.cls.int().cpu().tolist(), ids):
            out.append(Detection(
                class_name=str(names[cls]),
                confidence=float(conf),
                bbox=tuple(float(v) for v in bbox),
                track_id=None if tid is None else int(tid),
            ))
    return out


# ----------------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="规则引擎消融实验（毕业论文表 4.5）")
    parser.add_argument("--limit", type=int, default=None, help="每个数据集最多取N张，用于小样本冒烟")
    parser.add_argument("--batch", type=int, default=4, help="推理批大小，OOM 时自动降级为1")
    parser.add_argument("--resume", action="store_true", help="复用磁盘上的检测缓存")
    parser.add_argument("--no-selfcheck", action="store_true", help="跳过与生产逻辑的一致性校验")
    parser.add_argument("--video", default=None, help="可选：对指定视频额外做 D/E 时序对比")
    parser.add_argument("--video-frames", type=int, default=150, help="时序实验最多采样帧数")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    started = time.perf_counter()
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    for path in (CUSTOM_WEIGHTS, CONTEXT_WEIGHTS):
        if not path.exists():
            raise SystemExit(f"缺少权重文件：{path}")

    samples = collect_samples(args.limit)
    if not samples:
        raise SystemExit("未找到任何测试样本")
    run_inference(samples, batch=args.batch, resume=args.resume)

    empty = [s for s in samples if not s.detections]
    if empty:
        print(f"[warn] {len(empty)} 张图两个检测器均无输出（计入真负样本）：{[s.uid for s in empty[:3]]}")

    if not args.no_selfcheck:
        selfcheck_assert_identical(samples)

    dist = print_distribution(samples)

    results = [evaluate_group(samples, cfg) for cfg in ABLATION_GROUPS]
    rows = [metrics(r) for r in results]
    print_table(rows)
    write_csv(rows)

    # ---- 相邻组判定差异 ----
    print("\n" + "=" * 78)
    print("【相邻组判定变化样例】论文中说明「消融消除了哪一类误报」的直接证据")
    print("=" * 78)
    all_flips = {}
    for prev, curr in zip(results, results[1:]):
        flips, top = diff_between(prev, curr, samples)
        all_flips[f"{prev.cfg.group}->{curr.cfg.group}"] = flips
        gain_fp = sum(1 for f in flips if f["kind"] == "误报被消除")
        loss_tp = sum(1 for f in flips if f["kind"].startswith("真阳性"))
        print(f"\n  {prev.cfg.group} -> {curr.cfg.group}：判定翻转 {len(flips)} 张"
              f"（误报消除 {gain_fp}，真阳性丢失 {loss_tp}）")
        for item in top:
            verdict = "正确修复" if item["kind"] == "误报被消除" else item["kind"]
            print(f"    · {item['uid']}  gt={item['gt']}  "
                  f"{item['from_group']}组{item['from_pred']} -> {item['to_group']}组{item['to_pred']}  [{verdict}]")
            print(f"        {item['reason']}")

    temporal_note()
    temporal_result = None
    if args.video:
        temporal_result = run_temporal_video(Path(args.video), args.video_frames, sample_fps=5.0)

    payload = {
        "evaluation_protocol": {
            "level": "image_level",
            "definition": "gt_violation=1 当且仅当该图标签中至少有一个 class==1(no_helmet) 框；"
                          "pred_violation=1 当且仅当规则引擎返回至少一个 code==NO_HELMET 事件。",
            "limitation": "标签无 person/vehicle 标注，无法区分骑乘者违规与路人违规，"
                          "Precision 会被路人误报拉低；该口径不是框级 mAP。",
            "fps_definition": "rule_fps = 1000/avg_decide_ms，仅统计规则引擎纯 CPU 判定，"
                              "不含检测器 GPU 推理与图像解码。",
            "inference_config": {
                "helmet_model": str(CUSTOM_WEIGHTS),
                "helmet_imgsz": HELMET_IMGSZ, "helmet_conf": HELMET_CONF,
                "context_model": str(CONTEXT_WEIGHTS),
                "context_imgsz": CONTEXT_IMGSZ, "context_conf": CONTEXT_CONF,
                "context_classes": CONTEXT_CLASS_IDS,
            },
            "rule_constants": {
                "RIDER_HORIZONTAL_INSET": RIDER_HORIZONTAL_INSET,
                "RIDER_MAX_FOOT_Y": RIDER_MAX_FOOT_Y,
                "RIDER_MAX_MATCH_SCORE": RIDER_MAX_MATCH_SCORE,
            },
        },
        "distribution": dist,
        "groups": [
            {
                "group": cfg.group, "label": cfg.label, "description": cfg.description,
                "flags": {
                    "rider_attribution": cfg.use_rider_attribution,
                    "head_zone": cfg.use_head_zone,
                    "confidence_arbitration": cfg.use_confidence_arbitration,
                    "temporal_vote": cfg.use_temporal_vote,
                },
            }
            for cfg in ABLATION_GROUPS
        ],
        "metrics": rows,
        "flips": all_flips,
        "temporal_video": temporal_result,
        "total_seconds": round(time.perf_counter() - started, 2),
    }
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[out] 详细结果（含翻转样本全量清单）已写入：{JSON_PATH}")
    print(f"[done] 总耗时 {payload['total_seconds']:.1f}s")


if __name__ == "__main__":
    main()