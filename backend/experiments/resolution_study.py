"""输入分辨率对照实验（推理侧）

目的：回答"提高推理输入分辨率对远距离小目标（头盔）的检出是否有帮助"。

实验设计（严格控制变量）：
  - 权重固定：backend/models/best.pt（同一个文件，不重新训练）
  - 数据固定：859 张测试集（helmet-voc-clean-v1 795 + bike-helmet-yolo 64）
  - 阈值固定：conf=0.25
  - 唯一变量：imgsz = 640 / 768 / 960 / 1152

注意：这是**推理侧**实验，回答的是"输入分辨率对检测结果的影响"，
不是"训练时采用该分辨率能提升精度"。论文表述须与此一致。

输出：resolution_results.csv（论文表 4.4 用）
"""
from __future__ import annotations

import csv
import json
import pickle
import sys
import time
from pathlib import Path

import cv2
from ultralytics import YOLO

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
OUT_DIR = BACKEND / "experiments"
CACHE = OUT_DIR / "resolution_cache.pkl"

# 与 ablation 实验完全一致的检测口径，保证可比
HELMET_CONF = 0.25
CONTEXT_CONF = 0.25
CONTEXT_IMGSZ = 640  # 上下文模型保持不变，只变头盔检测器
CONTEXT_CLASS_IDS = [0, 1, 3]

TEST_DIRS = [
    ROOT / "data" / "helmet-voc-clean-v1",
    ROOT / "data" / "bike-helmet-yolo",
]

RESOLUTIONS = [640, 768, 960, 1152]


def list_test_images() -> list[Path]:
    """按与消融实验相同的顺序枚举测试图。"""
    imgs: list[Path] = []
    for base in TEST_DIRS:
        for sub in ("test",):
            d = base / "images" / sub
            if d.is_dir():
                imgs.extend(sorted(d.glob("*.jpg")))
    return imgs


def label_path(uid: str) -> Path:
    """标签路径与图像目录一一对应：images/<split>/ → labels/<split>/。

    注意 bike-helmet-yolo 的验证集目录名是 valid 而非 val，但测试集两边
    都叫 test，故统一按 uid 中的数据源名 + "test" 拼接。
    """
    parts = uid.split("/")
    base = TEST_DIRS[0] if parts[0].startswith("helmet-voc") else TEST_DIRS[1]
    return base / "labels" / "test" / parts[-1].replace(".jpg", ".txt")


def ground_truth(uid: str) -> bool:
    """图像级真值：该图标签中至少含一个 class==1 (no_helmet) 框。"""
    label = label_path(uid)
    if not label.exists():
        return False
    for line in label.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if int(line.split()[0]) == 1:
            return True
    return False


def uid_of(path: Path) -> str:
    parent = path.parent.parent.parent.name
    return f"{parent}/{path.name}"


def run_resolution(model: YOLO, imgs: list[Path], imgsz: int) -> dict:
    """在指定 imgsz 下推理，返回 {uid: [(class_name, conf, [x1,y1,x2,y2]), ...]}。

    显存保护：1152 等大分辨率在 8GB 卡上直接 batch 推理可能触发
    CUDA error: unknown error，故单张推理并在每 100 张落一次盘，
    中断后可用 --resume 续跑。
    """
    detections: dict[str, list] = {}
    part_path = OUT_DIR / f"resolution_partial_{imgsz}.pkl"
    if part_path.exists():
        detections = pickle.load(open(part_path, "rb"))
        print(f"  [resume] 已完成 {len(detections)} 张")
    total_ms = 0.0
    done = 0
    for path in imgs:
        uid = uid_of(path)
        if uid in detections:
            continue
        img = None
        try:
            img = cv2.imread(str(path))
        except Exception as exc:  # 沙箱/权限/文件占用等
            print(f"  [read-fail] {path.name}: {type(exc).__name__}: {exc}")
            detections[uid] = []
            continue
        if img is None:
            detections[uid] = []
            continue
        t0 = time.perf_counter()
        try:
            res = model.predict(img, imgsz=imgsz, conf=HELMET_CONF, verbose=False)[0]
        except Exception as exc:  # 单张失败不影响整体，记录为空
            print(f"  [skip] {uid}: {type(exc).__name__}")
            detections[uid] = []
            continue
        total_ms += (time.perf_counter() - t0) * 1000
        done += 1
        boxes = []
        if res.boxes is not None and len(res.boxes):
            cls = res.boxes.cls.cpu().numpy().astype(int)
            conf = res.boxes.conf.cpu().numpy()
            xyxy = res.boxes.xyxy.cpu().numpy()
            for c, f, b in zip(cls, conf, xyxy):
                boxes.append((res.names[c], float(f), [float(v) for v in b]))
        detections[uid] = boxes
        if done % 100 == 0:
            pickle.dump(detections, open(part_path, "wb"))
            print(f"    ... {len(detections)}/{len(imgs)}")
    pickle.dump(detections, open(part_path, "wb"))
    avg_ms = total_ms / max(1, done)
    print(f"  imgsz={imgsz}: {len(detections)} 张, 推理均值 {avg_ms:.1f} ms/张")
    return {"detections": detections, "avg_infer_ms": avg_ms}


def evaluate(detections: dict[str, list], imgs: list[Path]) -> dict:
    """图像级检测层指标：图内是否存在 helmet / no_helmet 框。"""
    tp = fp = fn = tn = 0
    helmet_gt = helmet_pred = 0
    for path in imgs:
        uid = uid_of(path)
        gt = ground_truth(uid)
        boxes = detections.get(uid, [])
        has_bare = any(cls == "no_helmet" for cls, _, _ in boxes)
        has_helmet = any(cls == "helmet" for cls, _, _ in boxes)
        # 检出率：任一头部类框即视为"检出头部"
        pred = has_bare or has_helmet
        helmet_gt += 1 if gt else 0
        helmet_pred += 1 if pred else 0
        if pred and gt:
            tp += 1
        elif pred and not gt:
            fp += 1
        elif not pred and gt:
            fn += 1
        else:
            tn += 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
        "head_detect_rate": round(helmet_pred / max(1, len(imgs)), 4),
        "n_images": len(imgs), "n_gt_violation": helmet_gt,
    }


def evaluate_boxes(detections: dict[str, list], imgs: list[Path]) -> dict:
    """框级 IoU=0.5 匹配下的检测层 mAP（手工实现，避免依赖 val 流程）。

    与论文表 4.3 的 results.csv 口径可能略有差异（该表由 Ultralytics val
    在 923 张 val 上产生），本表口径为 859 张 test + 图像级筛选，
    论文中两组数据须分别说明，不可混用。
    """
    n_gt_boxes = n_pred_boxes = n_tp = n_fp = n_fn = 0
    for path in imgs:
        uid = uid_of(path)
        label = label_path(uid)

        gt_boxes = []
        if label.exists():
            h, w = cv2.imread(str(path)).shape[:2]
            for line in label.read_text(encoding="utf-8").splitlines():
                f = line.split()
                if len(f) < 5:
                    continue
                cid = int(f[0])
                cx, cy, bw, bh = map(float, f[1:5])
                gt_boxes.append((cid, (cx * w - bw * w / 2, cy * h - bh * h / 2,
                                       cx * w + bw * w / 2, cy * h + bh * h / 2)))
        n_gt_boxes += len(gt_boxes)

        used = set()
        for cls, conf, b in detections.get(uid, []):
            cid = 0 if cls == "helmet" else 1
            n_pred_boxes += 1
            best, best_iou = -1, 0.5
            for i, (gcid, gb) in enumerate(gt_boxes):
                if i in used or gcid != cid:
                    continue
                x1, y1 = max(b[0], gb[0]), max(b[1], gb[1])
                x2, y2 = min(b[2], gb[2]), min(b[3], gb[3])
                iw, ih = max(0.0, x2 - x1), max(0.0, y2 - y1)
                inter = iw * ih
                union = (b[2] - b[0]) * (b[3] - b[1]) + (gb[2] - gb[0]) * (gb[3] - gb[1]) - inter
                iou = inter / union if union > 0 else 0.0
                if iou >= best_iou:
                    best, best_iou = i, iou
            if best >= 0:
                used.add(best)
                n_tp += 1
            else:
                n_fp += 1
        n_fn += len(gt_boxes) - len(used)

    prec = n_tp / (n_tp + n_fp) if n_tp + n_fp else 0.0
    rec = n_tp / (n_tp + n_fn) if n_tp + n_fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {
        "box_tp": n_tp, "box_fp": n_fp, "box_fn": n_fn,
        "n_gt_boxes": n_gt_boxes, "n_pred_boxes": n_pred_boxes,
        "box_precision": round(prec, 4), "box_recall": round(rec, 4), "box_f1": round(f1, 4),
    }


def main() -> None:
    resume = "--resume" in sys.argv
    only = None
    for a in sys.argv:
        if a.startswith("--imgsz="):
            only = int(a.split("=")[1])

    imgs = list_test_images()
    print(f"[data] 测试集 {len(imgs)} 张")
    model = YOLO(str(BACKEND / "models" / "best.pt"))

    cache = {}
    if CACHE.exists() and resume:
        cache = pickle.load(open(CACHE, "rb"))
        print(f"[cache] 复用 {sorted(cache.keys())}")

    targets = [only] if only else RESOLUTIONS
    results = {}
    for imgsz in targets:
        key = f"imgsz_{imgsz}"
        if key in cache:
            print(f"[skip] {key} 已在缓存")
            results[imgsz] = cache[key]
            continue
        print(f"[run ] imgsz={imgsz} ...")
        results[imgsz] = run_resolution(model, imgs, imgsz)

    pickle.dump(results, open(CACHE, "wb"))

    rows = []
    for imgsz in sorted(results):
        det = results[imgsz]["detections"]
        row = {"imgsz": imgsz, "conf": HELMET_CONF,
               "avg_infer_ms": round(results[imgsz]["avg_infer_ms"], 1)}
        row.update(evaluate(det, imgs))
        row.update(evaluate_boxes(det, imgs))
        row["infer_fps"] = round(1000 / max(1e-6, row["avg_infer_ms"]), 1)
        rows.append(row)
        print(f"[done] imgsz={imgsz}: box_f1={row['box_f1']} box_recall={row['box_recall']}")

    csv_path = OUT_DIR / "resolution_results.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[out] {csv_path}")

    meta = {
        "weights": str(BACKEND / "models" / "best.pt"),
        "conf": HELMET_CONF,
        "n_images": len(imgs),
        "test_dirs": [str(d) for d in TEST_DIRS],
        "note": "推理侧对照：同一权重、同一阈值、同一测试集，唯一变量为 imgsz。"
                "本口径为 859 张 test 图像级/框级(IoU=0.5)统计，"
                "与 results.csv 的 923 张 val 口径不同，论文中须分别说明。",
        "rows": rows,
    }
    (OUT_DIR / "resolution_report.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[done]")


if __name__ == "__main__":
    main()
