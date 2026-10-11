"""规则引擎几何硬约束参数敏感性定量分析（毕业论文表 4.5 配套）。

================================================================================
【目的】
A→B 消融阶段出现 11 张"真阳性丢失"，怀疑几何硬约束 RIDER_MAX_FOOT_Y=0.97 过严。
本脚本在不修改 backend/app/rules.py 的前提下（全部通过 monkeypatch 临时改写模块
级常量），定量回答三个问题：

  1. RIDER_MAX_FOOT_Y 取不同值时，五组消融指标各如何变化？
  2. 另外两个几何常量 RIDER_HORIZONTAL_INSET / RIDER_MAX_MATCH_SCORE 呢？
  3. 因 relative_foot_y 被拒的样本，究竟是"真阳性被误拒"还是"正确拒绝"？

【为什么必须做第3 步】
提高 RIDER_MAX_FOOT_Y 一定会让更多图被接受，FP 与 FN 会同时变化，
单看指标无法判断约束是否该放宽。必须回到原始像素去人工判断"这人到底骑没骑车"。

【实现手法】
复用 ablation.py 的样本枚举 / 缓存读取 / decide() 驱动，不复制任何业务逻辑。
检测结果全部来自backend/experiments/ablation_cache/detections.pkl（859 张，已存在），
本脚本【不跑任何模型推理】。默认参数下会跑一次 selfcheck，证明本脚本的 decide()
与生产 rules.evaluate_violations 逐字段一致。

【输出】
  sensitivity_results.csv        三组扫描 × 五组消融的完整指标（含相对变化量）
  sensitivity_flips_footy.csv    因放宽 foot_y 而改变判定的样本全量清单
  ablation_results_footy_<v>.csv 某个候选 foot_y 取值下的五组消融指标（供论文表 4.5）
  review_crops/                 人工核验用的标注裁剪图
================================================================================
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
EXP_DIR = BACKEND_DIR / "experiments"
for _p in (BACKEND_DIR, EXP_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app import rules  # noqa: E402
from app.rules import Detection, normalize_label  # noqa: E402

import ablation as ab  # noqa: E402

# ----------------------------------------------------------------------------------
# 默认参数（从 rules 模块读取，保证与生产逻辑同源）
# ----------------------------------------------------------------------------------
DEF_INSET = rules.RIDER_HORIZONTAL_INSET    # 0.10
DEF_FOOT_Y = rules.RIDER_MAX_FOOT_Y          # 0.97
DEF_SCORE = rules.RIDER_MAX_MATCH_SCORE     # 0.82

# 扫描网格
FOOT_Y_GRID = [0.95, 0.97, 0.98, 0.99, 0.995, 1.00, 1.02]
INSET_GRID = [0.05, 0.08, 0.10, 0.12, 0.15]
SCORE_GRID = [0.70, 0.75, 0.82, 0.90, 0.95, 1.00]

CSV_RESULTS = EXP_DIR / "sensitivity_results.csv"
CSV_FLIPS = EXP_DIR / "sensitivity_flips_footy.csv"
JSON_REPORT = EXP_DIR / "sensitivity_report.json"
CROP_DIR = EXP_DIR / "review_crops"

ORIGINAL_PARAMS = {"RIDER_HORIZONTAL_INSET": DEF_INSET,
                   "RIDER_MAX_FOOT_Y": DEF_FOOT_Y,
                   "RIDER_MAX_MATCH_SCORE": DEF_SCORE}


@contextmanager
def patched_params(**kwargs):
    """临时改写 rules 模块级几何常量，退出时严格恢复。

    rules._rider_match_score() 在函数体内以全局名读取这三个常量，
    因此改写模块属性即可生效，无需触碰 rules.py 源码。
    """
    saved = {name: getattr(rules, name) for name in kwargs}
    try:
        for name, value in kwargs.items():
            setattr(rules, name, value)
        yield
    finally:
        for name, value in saved.items():
            setattr(rules, name, value)


# ----------------------------------------------------------------------------------
# 几何约束的解析式复算（仅用于诊断报告，不参与判定）
# 与 rules._rider_match_score 的检查顺序、公式逐条对齐
# ----------------------------------------------------------------------------------
def geom_detail(person_box, vehicle_box, inset: float, max_foot_y: float) -> dict:
    """复算一条 (person, vehicle) 配对的全部中间量与每条约束的通过情况。"""
    px1, py1, px2, py2 = person_box
    vx1, vy1, vx2, vy2 = vehicle_box
    person_width = max(1.0, px2 - px1)
    person_height = max(1.0, py2 - py1)
    vehicle_width = max(1.0, vx2 - vx1)
    vehicle_height = max(1.0, vy2 - vy1)
    foot_x = (px1 + px2) / 2
    foot_y = py2

    relative_x = (foot_x - vx1) / vehicle_width
    relative_foot_y = (foot_y - vy1) / vehicle_height
    horizontal_margin = min(person_width * 0.35, vehicle_width * 0.30)
    max_gap_above = min(person_height * 0.25, vehicle_height * 0.40)

    c_x = bool(inset <= relative_x <= 1 - inset)
    c_y = bool(relative_foot_y <= max_foot_y)
    c_margin = bool(vx1 - horizontal_margin <= foot_x <= vx2 + horizontal_margin)
    c_vgap = bool(not (foot_y < vy1 - max_gap_above
                       or foot_y > vy2 + vehicle_height * 0.15))

    if foot_x < vx1:
        horizontal_gap = vx1 - foot_x
    elif foot_x > vx2:
        horizontal_gap = foot_x - vx2
    else:
        horizontal_gap = 0.0
    target_y = vy1 + vehicle_height * 0.22
    vertical_distance = abs(foot_y - target_y) / vehicle_height
    center_distance = abs(foot_x - (vx1 + vx2) / 2) / vehicle_width
    score = horizontal_gap / vehicle_width * 2.0 + vertical_distance + center_distance * 0.35

    return {
        "foot_x": round(foot_x, 1), "foot_y": round(foot_y, 1),
        "vehicle": [round(v, 1) for v in vehicle_box],
        "vehicle_w": round(vehicle_width, 1), "vehicle_h": round(vehicle_height, 1),
        "person_w": round(person_width, 1), "person_h": round(person_height, 1),
        "relative_x": round(relative_x, 4),
        "relative_foot_y": round(relative_foot_y, 4),
        "match_score": round(score, 4),
        "pass_horizontal_inset": c_x,
        "pass_foot_y": c_y,
        "pass_horizontal_margin": c_margin,
        "pass_vertical_gap": c_vgap,
    }


def failed_constraints(detail: dict, score_limit: float) -> list[str]:
    """列出一个配对违反的全部约束（不只第一条，用于判断"抬阈值后会暴露什么"）。"""
    bad = []
    if not detail["pass_horizontal_inset"]:
        bad.append("relative_x超出水平内缩")
    if not detail["pass_foot_y"]:
        bad.append("relative_foot_y超限")
    if not detail["pass_horizontal_margin"]:
        bad.append("脚底水平越界")
    if not detail["pass_vertical_gap"]:
        bad.append("纵向位置越界")
    if detail["match_score"] > score_limit:
        bad.append("匹配代价超限")
    return bad


# ----------------------------------------------------------------------------------
# 样本与缓存
# ----------------------------------------------------------------------------------
def load_samples() -> list:
    """复用 ablation.collect_samples +缓存，不触发任何推理。"""
    samples = ab.collect_samples(None)
    if not samples:
        raise SystemExit("未找到任何测试样本")
    ab.run_inference(samples, batch=4, resume=True)
    empty = [s for s in samples if not s.detections]
    if empty:
        print(f"[warn] {len(empty)} 张图两个检测器均无输出（计入真负样本）")
    return samples


# ----------------------------------------------------------------------------------
# 扫描：单参数敏感性
# ----------------------------------------------------------------------------------
def run_sweep(samples: list, param: str, grid: list, tag: str) -> list[dict]:
    """单变量扫描：只改param，其余两个常量固定为默认值。"""
    baseline: dict[str, dict] = {}
    rows: list[dict] = []
    for value in grid:
        override = {param: value}
        with patched_params(**override):
            for cfg in ab.ABLATION_GROUPS:
                result = ab.evaluate_group(samples, cfg)
                row = ab.metrics(result)
                row["sweep"] = tag
                row["param"] = param
                row["value"] = value
                rows.append(row)
                # 默认取值那一行作为同组对照基准
                if abs(value - ORIGINAL_PARAMS[param]) < 1e-12:
                    baseline[cfg.group] = row
        print(f"  [{tag}] {param}={value:<6} 扫描完成", end="\r")
    print(" " * 40, end="\r")

    # 补齐两组变化量：相对 A 组、相对同组默认取值
    for row in rows:
        ref_a = next(r for r in rows if r["sweep"] == row["sweep"]
                     and r["value"] == row["value"] and r["group"] == "A")
        ref_d = baseline.get(row["group"])
        row["d_tp_vs_A"] = row["tp"] - ref_a["tp"]
        row["d_fp_vs_A"] = row["fp"] - ref_a["fp"]
        row["d_fn_vs_A"] = row["fn"] - ref_a["fn"]
        row["d_tp_vs_default"] = row["tp"] - ref_d["tp"] if ref_d else ""
        row["d_fp_vs_default"] = row["fp"] - ref_d["fp"] if ref_d else ""
        row["d_fn_vs_default"] = row["fn"] - ref_d["fn"] if ref_d else ""
        row["d_f1_vs_default"] = round(row["f1"] - ref_d["f1"], 4) if ref_d else ""
    return rows


# ----------------------------------------------------------------------------------
# 翻转归因：放宽 foot_y 后哪些样本的判定变了，为什么
# ----------------------------------------------------------------------------------
def head_gearage_in_zone(sample, person) -> tuple[int, int]:
    """统计某个 person 头部区域内命中的裸头框数与头盔框数。"""
    zone = rules._head_zone(person.bbox)
    zx1, zy1, zx2, zy2 = zone
    cx, cy = (zx1 + zx2) / 2, (zy1 + zy2) / 2

    def inside(box):
        x1, y1, x2, y2 = box
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        return zx1 <= mx <= zx2 and zy1 <= my <= zy2

    bare = sum(1 for d in sample.bare_heads if inside(d.bbox))
    helm = sum(1 for d in sample.helmets if inside(d.bbox))
    return bare, helm


def flip_analysis(samples: list, new_foot_y: float) -> list[dict]:
    """对比默认 foot_y 与放宽后的 foot_y，找出判定改变的样本并归因。"""
    index = {s.uid: s for s in samples}
    old_preds: dict[str, dict] = {}
    new_preds: dict[str, dict] = {}

    def snapshot(into: dict) -> None:
        for cfg in ab.ABLATION_GROUPS:
            result = ab.evaluate_group(samples, cfg)
            into[cfg.group] = result.preds

    with patched_params():
        snapshot(old_preds)
    with patched_params(RIDER_MAX_FOOT_Y=new_foot_y):
        snapshot(new_preds)

    records = []
    for group in old_preds:
        old, new = old_preds[group], new_preds[group]
        for uid, o in old.items():
            n = new.get(uid, 0)
            if o == n:
                continue
            sample = index[uid]

            # 找出该图里"被 relative_foot_y 拒掉"的人车配对
            foot_y_blocked = []
            for person in sample.people:
                for vidx, vehicle in enumerate(sample.vehicles):
                    detail = geom_detail(person.bbox, vehicle.bbox, DEF_INSET, DEF_FOOT_Y)
                    if detail["pass_foot_y"]:
                        continue
                    bad = failed_constraints(detail, DEF_SCORE)
                    bare, helm = head_gearage_in_zone(sample, person)
                    foot_y_blocked.append({
                        "person_bbox": [round(v, 1) for v in person.bbox],
                        "person_conf": round(person.confidence, 3),
                        "vehicle_bbox": detail["vehicle"],
                        "vehicle_conf": round(vehicle.confidence, 3),
                        "relative_foot_y": detail["relative_foot_y"],
                        "relative_x": detail["relative_x"],
                        "match_score": detail["match_score"],
                        "only_foot_y_violated": bad == ["relative_foot_y超限"],
                        "all_violated": bad,
                        "head_bare_in_zone": bare,
                        "head_helmet_in_zone": helm,
                    })

            records.append({
                "uid": uid, "group": group, "gt": sample.gt_violation,
                "old_pred": o, "new_pred": n,
                "kind": ("真阳性召回" if sample.gt_violation == 1 else "误报增加"),
                "change": ("FN->TP" if sample.gt_violation == 1 else "TN->FP"),
                "gt_bare_boxes": sample.gt_bare_boxes,
                "gt_helmet_boxes": sample.gt_head_boxes,
                "n_people": len(sample.people), "n_vehicles": len(sample.vehicles),
                "n_bare_head_det": len(sample.bare_heads),
                "n_helmet_det": len(sample.helmets),
                "foot_y_blocked_pairs": len(foot_y_blocked),
                "foot_y_blocked": foot_y_blocked,
            })
    return records


# ----------------------------------------------------------------------------------
# 输出
# ----------------------------------------------------------------------------------
def print_sweep(rows: list[dict], title: str, param: str) -> None:
    print("\n" + "=" * 132)
    print(f"【{title}】{param} 单变量敏感性（其余常量固定为默认值）")
    print("=" * 132)
    print(f"默认取值 {param} = {ORIGINAL_PARAMS[param]}")
    header = (f"{'取值':>7}{'组':>4}{'TP':>6}{'FP':>6}{'FN':>6}{'TN':>7}"
              f"{'P':>8}{'R':>8}{'F1':>8}{'FPR':>8}{'Acc':>8}"
              f"{'ΔTP':>6}{'ΔFP':>6}{'ΔFN':>6}{'ΔF1':>8}")
    print(header)
    print("-" * 132)
    for row in rows:
        default_mark = "  <= 默认" if abs(row["value"] - ORIGINAL_PARAMS[param]) < 1e-12 else ""
        print(f"{row['value']:>7}{row['group']:>4}"
              f"{row['tp']:>6}{row['fp']:>6}{row['fn']:>6}{row['tn']:>7}"
              f"{row['precision']:>8.4f}{row['recall']:>8.4f}{row['f1']:>8.4f}"
              f"{row['false_positive_rate']:>8.4f}{row['accuracy']:>8.4f}"
              f"{row['d_tp_vs_default']:>6}{row['d_fp_vs_default']:>6}"
              f"{row['d_fn_vs_default']:>6}{row['d_f1_vs_default']:>8}{default_mark}")
    print("-" * 132)
    print("ΔTP/ΔFP/ΔFN/ΔF1 = 相对【同一消融组、参数取默认值】时的变化量。A 组不做人车关联，故不受该参数影响。")


def write_results_csv(rows: list[dict]) -> None:
    fields = ["sweep", "param", "value", "group", "label", "tp", "fp", "fn", "tn",
              "precision", "recall", "f1", "false_positive_rate", "accuracy",
              "avg_decide_ms", "rule_fps", "n_images", "n_gt_violation", "n_gt_normal",
              "n_events", "n_uncertain",
              "d_tp_vs_A", "d_fp_vs_A", "d_fn_vs_A",
              "d_tp_vs_default", "d_fp_vs_default", "d_fn_vs_default", "d_f1_vs_default"]
    with CSV_RESULTS.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})
    print(f"\n[out] 三组扫描完整指标 CSV：{CSV_RESULTS}")


def write_flips_csv(records: list[dict]) -> None:
    fields = ["uid", "group", "gt", "change", "kind", "gt_bare_boxes", "gt_helmet_boxes",
              "n_people", "n_vehicles", "n_bare_head_det", "n_helmet_det",
              "foot_y_blocked_pairs", "only_foot_y_pairs",
              "foot_y_blocked_detail"]
    with CSV_FLIPS.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for rec in records:
            pairs = rec["foot_y_blocked"]
            writer.writerow({
                "uid": rec["uid"], "group": rec["group"], "gt": rec["gt"],
                "change": rec["change"], "kind": rec["kind"],
                "gt_bare_boxes": rec["gt_bare_boxes"], "gt_helmet_boxes": rec["gt_helmet_boxes"],
                "n_people": rec["n_people"], "n_vehicles": rec["n_vehicles"],
                "n_bare_head_det": rec["n_bare_head_det"], "n_helmet_det": rec["n_helmet_det"],
                "foot_y_blocked_pairs": rec["foot_y_blocked_pairs"],
                "only_foot_y_pairs": sum(1 for p in pairs if p["only_foot_y_violated"]),
                "foot_y_blocked_detail": json.dumps(pairs, ensure_ascii=False),
            })
    print(f"[out] foot_y 翻转样本清单CSV：{CSV_FLIPS}")


# ----------------------------------------------------------------------------------
# 人工核验：导出标注裁剪图
# ----------------------------------------------------------------------------------
def export_review_crops(samples: list, uids: list[str]) -> list[dict]:
    """为待人工核验的样本生成标注图（原图框 + 人车联合裁剪放大）。"""
    from PIL import Image, ImageDraw, ImageFont

    CROP_DIR.mkdir(parents=True, exist_ok=True)
    index = {s.uid: s for s in samples}
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()

    manifest = []
    for uid in uids:
        sample = index.get(uid)
        if sample is None or not sample.image_path.exists():
            continue
        try:
            image = Image.open(sample.image_path).convert("RGB")
        except OSError as exc:
            print(f"[warn] 无法打开 {uid}: {exc}")
            continue

        pairs = []
        for person in sample.people:
            for vehicle in sample.vehicles:
                detail = geom_detail(person.bbox, vehicle.bbox, DEF_INSET, DEF_FOOT_Y)
                if detail["pass_foot_y"]:
                    continue
                pairs.append((person, vehicle, detail))

        stem = sample.image_path.stem
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        for person in sample.people:
            draw.rectangle(person.bbox, outline=(0, 200, 0), width=3)
            draw.text((person.bbox[0], max(0, person.bbox[1] - 18)),
                      f"person {person.confidence:.2f}", fill=(0, 200, 0), font=font)
        for vehicle in sample.vehicles:
            draw.rectangle(vehicle.bbox, outline=(0, 80, 255), width=3)
            draw.text((vehicle.bbox[0], max(0, vehicle.bbox[1] - 18)),
                      f"vehicle {vehicle.confidence:.2f}", fill=(0, 80, 255), font=font)
        for head in sample.bare_heads:
            draw.rectangle(head.bbox, outline=(255, 0, 0), width=4)
        for head in sample.helmets:
            draw.rectangle(head.bbox, outline=(255, 160, 0), width=2)

        out_full = CROP_DIR / f"{stem}__full.jpg"
        annotated.save(out_full, quality=92)

        crops = []
        for idx, (person, vehicle, detail) in enumerate(pairs, 1):
            x1 = min(person.bbox[0], vehicle.bbox[0])
            y1 = min(person.bbox[1], vehicle.bbox[1])
            x2 = max(person.bbox[2], vehicle.bbox[2])
            y2 = max(person.bbox[2], vehicle.bbox[2])
            pad_x, pad_y = (x2 - x1) * 0.25 + 8, (y2 - y1) * 0.15 + 8
            left = max(0, x1 - pad_x)
            top = max(0, y1 - pad_y)
            right = min(image.width, x2 + pad_x)
            bottom = min(image.height, y2 + pad_y)
            if right - left < 4 or bottom - top < 4:
                # 配对框退化（车/人框几乎共线）时直接跳过，放大图无信息量
                continue
            piece = image.crop((left, top, right, bottom)).resize(
                (max(1, int((right - left) * 1.6)), max(1, int((bottom - top) * 1.6))),
                Image.LANCZOS)
            pd = ImageDraw.Draw(piece)
            scale = 1.6
            pd.rectangle([(person.bbox[0] - left) * scale, (person.bbox[1] - top) * scale,
                          (person.bbox[2] - left) * scale, (person.bbox[3] - top) * scale],
                         outline=(0, 220, 0), width=4)
            pd.rectangle([(vehicle.bbox[0] - left) * scale, (vehicle.bbox[1] - top) * scale,
                          (vehicle.bbox[2] - left) * scale, (vehicle.bbox[3] - top) * scale],
                         outline=(0, 90, 255), width=4)
            for head in sample.bare_heads:
                pd.rectangle([(head.bbox[0] - left) * scale, (head.bbox[1] - top) * scale,
                              (head.bbox[2] - left) * scale, (head.bbox[3] - top) * scale],
                             outline=(255, 0, 0), width=5)
            caption = (f"foot_y={detail['relative_foot_y']:.4f}  x={detail['relative_x']:.3f}  "
                       f"score={detail['match_score']:.3f}")
            pd.rectangle([0, 0, piece.width, 26], fill=(0, 0, 0))
            pd.text((6, 5), caption, fill=(255, 255, 0), font=font)
            out_piece = CROP_DIR / f"{stem}__pair{idx}.jpg"
            piece.save(out_piece, quality=93)
            crops.append(str(out_piece))

        manifest.append({
            "uid": uid, "gt": sample.gt_violation,
            "gt_bare_boxes": sample.gt_bare_boxes, "gt_helmet_boxes": sample.gt_head_boxes,
            "image_size": [image.width, image.height],
            "full": str(out_full), "crops": crops,
            "pairs": [{"relative_foot_y": d["relative_foot_y"],
                       "relative_x": d["relative_x"],
                       "match_score": d["match_score"],
                       "person_bbox": [round(v, 1) for v in p.bbox],
                       "vehicle_bbox": d["vehicle"],
                       "only_foot_y_violated": failed_constraints(d, DEF_SCORE) == ["relative_foot_y超限"],
                       "all_violated": failed_constraints(d, DEF_SCORE)}
                      for p, v, d in pairs],
        })
    print(f"[out] 人工核验标注图已写入：{CROP_DIR}（{len(manifest)} 张原图，"
          f"{sum(len(m['crops']) for m in manifest)} 张放大裁剪）")
    return manifest


# ----------------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="规则引擎几何硬约束参数敏感性分析")
    parser.add_argument("--foot-y", type=float, default=1.02,
                        help="导出人工核验图时使用的放宽取值（默认 1.02）")
    parser.add_argument("--skip-crops", action="store_true", help="只做指标扫描，不导出标注图")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    started = time.perf_counter()
    print("=" * 78)
    print("【参数敏感性分析】默认： "
          f"INSET={DEF_INSET}  MAX_FOOT_Y={DEF_FOOT_Y}  MAX_MATCH_SCORE={DEF_SCORE}")
    print("=" * 78)

    samples = load_samples()

    # 基线一致性校验：证明本脚本调用的 decide() 就是生产逻辑
    ab.selfcheck_assert_identical(samples)
    after = {k: getattr(rules, k) for k in ORIGINAL_PARAMS}
    assert after == ORIGINAL_PARAMS, f"参数未恢复：{after}"
    print("[guard] 扫描前 rules 模块参数校验通过，且 monkeypatch 已正确恢复")

    print("\n[scan] 三组单变量扫描中 ...")
    rows: list[dict] = []
    rows += run_sweep(samples, "RIDER_MAX_FOOT_Y", FOOT_Y_GRID, "foot_y")
    rows += run_sweep(samples, "RIDER_HORIZONTAL_INSET", INSET_GRID, "horizontal_inset")
    rows += run_sweep(samples, "RIDER_MAX_MATCH_SCORE", SCORE_GRID, "match_score")

    assert {k: getattr(rules, k) for k in ORIGINAL_PARAMS} == ORIGINAL_PARAMS, "扫描后参数未恢复"
    print("[guard] 扫描结束，rules 模块参数已恢复默认值")

    print_sweep([r for r in rows if r["sweep"] == "foot_y"],
                "表 S1 RIDER_MAX_FOOT_Y 敏感性", "RIDER_MAX_FOOT_Y")
    print_sweep([r for r in rows if r["sweep"] == "horizontal_inset"],
                "表 S2 RIDER_HORIZONTAL_INSET 敏感性", "RIDER_HORIZONTAL_INSET")
    print_sweep([r for r in rows if r["sweep"] == "match_score"],
                "表 S3 RIDER_MAX_MATCH_SCORE 敏感性", "RIDER_MAX_MATCH_SCORE")
    write_results_csv(rows)

    # ---- 翻转归因 ----
    print("\n" + "=" * 78)
    print(f"【翻转归因】放宽 RIDER_MAX_FOOT_Y = 0.97 -> {args.foot_y} 时判定改变的样本")
    print("=" * 78)
    records = flip_analysis(samples, args.foot_y)
    seen: dict[str, dict] = {}
    for rec in records:
        prev = seen.get(rec["uid"])
        if prev is None:
            seen[rec["uid"]] = rec
        else:
            prev["group"] = f"{prev['group']}+{rec['group']}"
    print(f"  受影响图数：{len(seen)}（共{len(records)} 条组级记录）")
    for uid, rec in sorted(seen.items()):
        pairs = rec["foot_y_blocked"]
        only = [p for p in pairs if p["only_foot_y_violated"]]
        fy = ",".join(f"{p['relative_foot_y']:.4f}" for p in pairs)
        print(f"    · {uid}  组={rec['group']}  gt={rec['gt']}  {rec['change']}  "
              f"被foot_y拒的配对={len(pairs)}（其中仅foot_y违反={len(only)}）  "
              f"rel_foot_y=[{fy}]")
    write_flips_csv(records)

    # ---- 人工核验图 ----
    manifest = []
    if not args.skip_crops:
        print("\n[crop] 导出人工核验标注图 ...")
        manifest = export_review_crops(samples, sorted(seen.keys()))

    # ---- 逐取值导出五组消融指标（供论文表 4.5 选用）----
    for value in sorted({DEF_FOOT_Y, args.foot_y} | {0.99, 1.00}):
        with patched_params(RIDER_MAX_FOOT_Y=value):
            group_rows = [ab.metrics(ab.evaluate_group(samples, cfg))
                          for cfg in ab.ABLATION_GROUPS]
        path = EXP_DIR / f"ablation_results_footy_{value}.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(group_rows[0].keys()))
            writer.writeheader()
            for row in group_rows:
                writer.writerow(row)
        print(f"[out] MAX_FOOT_Y={value} 下的五组消融指标：{path}")

    payload = {
        "default_params": ORIGINAL_PARAMS,
        "grids": {"RIDER_MAX_FOOT_Y": FOOT_Y_GRID,
                  "RIDER_HORIZONTAL_INSET": INSET_GRID,
                  "RIDER_MAX_MATCH_SCORE": SCORE_GRID},
        "relaxed_foot_y_for_attribution": args.foot_y,
        "rows": rows,
        "flip_records": records,
        "unique_affected_images": sorted(seen.keys()),
        "review_manifest": manifest,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }
    JSON_REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[out] 完整报告：{JSON_REPORT}")
    print(f"[done] 总耗时 {payload['elapsed_seconds']:.1f}s")


if __name__ == "__main__":
    main()
