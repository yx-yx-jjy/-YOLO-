"""把一个标注工作区（X-AnyLabeling 的 labels/*.json）校验并转换成 YOLO 训练集。

本项目有【两个模型】，各自独立的类别和数据集，绝不混在一起：

    profile       类别                             工作区            输出
    helmet        helmet / no_helmet               标注工作区        data/wuhan-manual-yolo
    rider_count   single_rider / multiple_riders   标注工作区-载人   data/rider-count-yolo

两者的差别不只是类别名：
  · 头盔模型只框「头部」，且已有 bike-helmet-yolo 作为基础数据集，
    所以产物是「补充集 + 合并配置」；
  · 载人数模型框「整车 + 全部乘员」，没有外部基础数据集，
    所以产物就是完整数据集本身，train/val/test 由本脚本从标注里划出来。

用法：
    python prepare_manual.py --profile helmet
    python prepare_manual.py --profile rider_count
（一般不用手敲，双击对应工作区里的 bat 即可。）
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")

PROFILES: dict[str, dict] = {
    "helmet": {
        "title": "头盔模型（helmet / no_helmet，只框头部）",
        "workspace": "标注工作区",
        "output": "data/wuhan-manual-yolo",
        "base_dataset": "data/bike-helmet-yolo",
        "class_ids": {"helmet": 0, "no_helmet": 1},
        "names": ["helmet", "no_helmet"],
    },
    "rider_count": {
        "title": "载人数模型（single_rider / multiple_riders，框整车+全部乘员）",
        "workspace": "标注工作区-载人",
        "output": "data/rider-count-yolo",
        "base_dataset": None,
        "class_ids": {"single_rider": 0, "multiple_riders": 1},
        "names": ["single_rider", "multiple_riders"],
    },
}

# 载人数模型没有外部基础数据集，val / test 只能从标注里划。
# 用「排序后按固定步长取」而不是随机，保证同一份标注每次划出来的划分完全一致。
VAL_EVERY = 10
VAL_OFFSET = 0
TEST_EVERY = 10
TEST_OFFSET = 5


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Validate LabelMe annotations and prepare a YOLO training set"
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="helmet",
        help="选择要准备哪个模型的数据集",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="标注工作区目录（默认按 profile 决定）",
    )
    parser.add_argument(
        "--base-dataset",
        type=Path,
        default=None,
        help="已有 YOLO 数据集，作为基础数据集（仅 helmet profile 用）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="生成的 YOLO 数据集目录（默认按 profile 决定）",
    )
    args = parser.parse_args()
    args.project_root = project_root
    return args


def find_image(images_dir: Path, stem: str) -> Path | None:
    for suffix in IMAGE_SUFFIXES:
        candidate = images_dir / f"{stem}{suffix}"
        if candidate.exists():
            return candidate
    return None


def convert_annotation(
    annotation_path: Path, class_ids: dict[str, int]
) -> tuple[list[str], Counter]:
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    width = int(payload.get("imageWidth") or 0)
    height = int(payload.get("imageHeight") or 0)
    if width <= 0 or height <= 0:
        raise ValueError("imageWidth/imageHeight 缺失或无效")

    lines: list[str] = []
    counts: Counter = Counter()
    for index, shape in enumerate(payload.get("shapes", []), start=1):
        label = str(shape.get("label", "")).strip()
        if label not in class_ids:
            raise ValueError(f"第 {index} 个框类别 {label!r} 不在 {list(class_ids)} 中")
        if shape.get("shape_type") != "rectangle":
            raise ValueError(f"第 {index} 个标注不是 rectangle")
        points = shape.get("points") or []
        if len(points) != 2 or any(len(point) != 2 for point in points):
            raise ValueError(f"第 {index} 个框坐标格式无效")

        x1, x2 = sorted((float(points[0][0]), float(points[1][0])))
        y1, y2 = sorted((float(points[0][1]), float(points[1][1])))
        if x1 < 0 or y1 < 0 or x2 > width or y2 > height or x2 <= x1 or y2 <= y1:
            raise ValueError(
                f"第 {index} 个框越界或面积为零: {(x1, y1, x2, y2)} / {(width, height)}"
            )

        center_x = ((x1 + x2) / 2) / width
        center_y = ((y1 + y2) / 2) / height
        box_width = (x2 - x1) / width
        box_height = (y2 - y1) / height
        lines.append(
            f"{class_ids[label]} {center_x:.6f} {center_y:.6f} "
            f"{box_width:.6f} {box_height:.6f}"
        )
        counts[label] += 1
    return lines, counts


def write_names_block(names: list[str]) -> list[str]:
    return ["names:"] + [f"  {index}: {name}" for index, name in enumerate(names)]


def write_helmet_combined_yaml(output: Path, base_dataset: Path, names: list[str]) -> Path:
    """头盔模型：产物是「补充集」，训练时与基础数据集合并，所以写合并配置。"""
    config_path = output / "combined-dataset.yaml"
    base = base_dataset.resolve().as_posix()
    manual = output.resolve().as_posix()
    lines = [
        f'path: "{Path(base_dataset).resolve().parents[1].as_posix()}"',
        "train:",
        f'  - "{base}/images/train"',
        f'  - "{manual}/images/train"',
        f'val: "{base}/images/valid"',
        f'test: "{base}/images/test"',
    ]
    lines += write_names_block(names)
    lines.append("")
    config_path.write_text("\n".join(lines), encoding="utf-8")
    return config_path


def write_standalone_yaml(output: Path, names: list[str]) -> Path:
    """载人数模型：没有基础数据集，产物就是完整数据集，自带 train/val/test。"""
    config_path = output / "dataset.yaml"
    lines = [
        f'path: "{output.resolve().as_posix()}"',
        "train: images/train",
        "val: images/val",
        "test: images/test",
    ]
    lines += write_names_block(names)
    lines.append("")
    config_path.write_text("\n".join(lines), encoding="utf-8")
    return config_path


def assign_splits(stems: list[str], split_own_data: bool) -> dict[str, list[str]]:
    """决定每张图进哪个 split。

    helmet profile 用外部数据集的 val/test，自己的图全部进 train；
    rider_count profile 没有外部数据，按固定步长自己划。
    """
    if not split_own_data:
        return {"train": list(stems), "val": [], "test": []}
    splits: dict[str, list[str]] = {"train": [], "val": [], "test": []}
    for index, stem in enumerate(stems):
        if index % VAL_EVERY == VAL_OFFSET:
            splits["val"].append(stem)
        elif index % TEST_EVERY == TEST_OFFSET:
            splits["test"].append(stem)
        else:
            splits["train"].append(stem)
    return splits


def main() -> None:
    args = parse_args()
    profile = PROFILES[args.profile]
    project_root: Path = args.project_root

    workspace = (args.workspace or project_root / profile["workspace"]).resolve()
    output = (args.output or project_root / profile["output"]).resolve()
    base_dataset = None
    if profile["base_dataset"] is not None:
        base_dataset = (
            args.base_dataset.resolve()
            if args.base_dataset is not None
            else (project_root / profile["base_dataset"]).resolve()
        )

    class_ids: dict[str, int] = profile["class_ids"]
    names: list[str] = profile["names"]

    images_dir = workspace / "images"
    annotations_dir = workspace / "labels"

    print(f"profile : {args.profile} —— {profile['title']}")
    print(f"工作区  : {workspace}")
    print(f"输出到  : {output}")
    if base_dataset is not None:
        print(f"基础数据集: {base_dataset}")
    print("-" * 66)

    if not images_dir.is_dir() or not annotations_dir.is_dir():
        raise SystemExit(f"标注工作区缺少 images/ 或 labels/: {workspace}")
    if base_dataset is not None and not base_dataset.is_dir():
        raise SystemExit(f"基础数据集不存在: {base_dataset}")

    annotations = sorted(annotations_dir.glob("*.json"))
    if not annotations:
        raise SystemExit("没有找到 labels/*.json，请先在标注软件中保存标注")

    prepared: list[tuple[Path, list[str]]] = []
    totals: Counter = Counter()
    errors: list[str] = []
    for annotation in annotations:
        image = find_image(images_dir, annotation.stem)
        if image is None:
            errors.append(f"{annotation.name}: 找不到同名图片")
            continue
        try:
            lines, counts = convert_annotation(annotation, class_ids)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"{annotation.name}: {exc}")
            continue
        prepared.append((image, lines))
        totals.update(counts)

    if errors:
        print("标注质检失败，未写入训练集：")
        for error in errors:
            print(f"  - {error}")
        raise SystemExit(1)

    # 按文件名排序后再划分，保证可重复
    prepared.sort(key=lambda item: item[0].name)
    splits = assign_splits(
        [image.stem for image, _ in prepared], split_own_data=base_dataset is None
    )
    lines_by_stem = {image.stem: lines for image, lines in prepared}
    image_by_stem = {image.stem: image for image, lines in prepared}

    # 先清掉旧产物，避免换了划分后留下孤儿文件
    for kind in ("images", "labels"):
        for stale_dir in output.glob(f"{kind}/*"):
            if stale_dir.is_dir():
                shutil.rmtree(stale_dir)

    for split_name, split_stems in splits.items():
        if not split_stems:
            continue
        out_images = output / "images" / split_name
        out_labels = output / "labels" / split_name
        out_images.mkdir(parents=True, exist_ok=True)
        out_labels.mkdir(parents=True, exist_ok=True)
        for stem in split_stems:
            image = image_by_stem[stem]
            shutil.copy2(image, out_images / image.name)
            body = lines_by_stem[stem]
            (out_labels / f"{stem}.txt").write_text(
                "\n".join(body) + ("\n" if body else ""), encoding="ascii"
            )

    if base_dataset is not None:
        config_path = write_helmet_combined_yaml(output, base_dataset, names)
    else:
        config_path = write_standalone_yaml(output, names)

    all_images = sum(1 for path in images_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)
    print("标注质检通过")
    print(f"  已标图片 : {len(prepared)}/{all_images}")
    for label, class_id in sorted(class_ids.items(), key=lambda item: item[1]):
        print(f"    {class_id} {label}: {totals[label]}")
    print("  划分     : " + "  ".join(f"{k} {len(v)}" for k, v in splits.items() if v))
    print(f"  数据集   : {output}")
    print(f"  训练配置 : {config_path}")


if __name__ == "__main__":
    main()
