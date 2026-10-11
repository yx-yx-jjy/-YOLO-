from __future__ import annotations

import argparse
import csv
import hashlib
import os
import random
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import yaml
from PIL import Image


TARGET_CLASS_IDS = {"helmet": 0, "no helmet": 1}
TARGET_NAMES = {0: "helmet", 1: "no_helmet"}
RIDER_CLASSES = {"motorcycler", "bicycler"}
KNOWN_CLASSES = set(TARGET_CLASS_IDS) | RIDER_CLASSES
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
INDEX_RE = re.compile(r"\.(\d+)$")


@dataclass(frozen=True)
class Box:
    class_id: int
    xmin: float
    ymin: float
    xmax: float
    ymax: float


@dataclass(frozen=True)
class Record:
    index: int
    group: int
    image: Path
    annotation: Path
    width: int
    height: int
    boxes: tuple[Box, ...]
    digest: str


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Clean Pascal VOC helmet data and convert it to grouped YOLO splits"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=project_root / "数据集" / "头盔数据" / "头盔数据",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "data" / "helmet-voc-clean-v1",
    )
    parser.add_argument("--seed", type=int, default=20261002)
    return parser.parse_args()


def numeric_index(stem: str) -> int:
    match = INDEX_RE.search(stem)
    if not match:
        raise ValueError(f"Cannot extract numeric index from {stem!r}")
    return int(match.group(1))


def image_index(source: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in source.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if path.name in result:
            raise ValueError(f"Duplicate image filename: {path.name}")
        result[path.name] = path
    return result


def parse_record(annotation: Path, images: dict[str, Path]) -> Record:
    root = ET.parse(annotation).getroot()
    filename = (root.findtext("filename") or "").strip()
    image = images.get(filename)
    if image is None:
        raise FileNotFoundError(f"Missing image for {annotation}: {filename}")

    xml_width = int(root.findtext("size/width") or 0)
    xml_height = int(root.findtext("size/height") or 0)
    with Image.open(image) as handle:
        width, height = handle.size
    if width <= 0 or height <= 0 or (width, height) != (xml_width, xml_height):
        raise ValueError(
            f"Image/XML size mismatch for {filename}: image={(width, height)}, "
            f"xml={(xml_width, xml_height)}"
        )

    names: set[str] = set()
    boxes: list[Box] = []
    for item in root.findall("object"):
        name = (item.findtext("name") or "").strip().lower()
        if name not in KNOWN_CLASSES:
            raise ValueError(f"Unknown class {name!r} in {annotation}")
        names.add(name)
        bounds = item.find("bndbox")
        if bounds is None:
            raise ValueError(f"Missing bndbox in {annotation}")
        xmin = float(bounds.findtext("xmin") or 0)
        ymin = float(bounds.findtext("ymin") or 0)
        xmax = float(bounds.findtext("xmax") or 0)
        ymax = float(bounds.findtext("ymax") or 0)
        if xmin < 0 or ymin < 0 or xmax <= xmin or ymax <= ymin:
            raise ValueError(f"Invalid box in {annotation}: {(xmin, ymin, xmax, ymax)}")
        if xmax > width or ymax > height:
            raise ValueError(f"Out-of-bounds box in {annotation}: {(xmin, ymin, xmax, ymax)}")
        if name in TARGET_CLASS_IDS:
            boxes.append(Box(TARGET_CLASS_IDS[name], xmin, ymin, xmax, ymax))

    if not boxes:
        raise LookupError("missing helmet status")
    if not (names & RIDER_CLASSES):
        raise LookupError("missing rider")

    index = numeric_index(image.stem)
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    return Record(
        index=index,
        group=index // 100,
        image=image,
        annotation=annotation,
        width=width,
        height=height,
        boxes=tuple(boxes),
        digest=digest,
    )


def status_signature(record: Record) -> tuple[int, int]:
    counts = Counter(box.class_id for box in record.boxes)
    return counts[0], counts[1]


def deduplicate(records: list[Record]) -> tuple[list[Record], dict[str, int]]:
    by_digest: dict[str, list[Record]] = defaultdict(list)
    for record in records:
        by_digest[record.digest].append(record)

    selected: list[Record] = []
    duplicate_groups = 0
    duplicate_images_removed = 0
    conflicting_groups = 0
    conflicting_images_removed = 0
    for items in by_digest.values():
        if len(items) == 1:
            selected.append(items[0])
            continue
        duplicate_groups += 1
        signatures = {status_signature(item) for item in items}
        if len(signatures) != 1:
            conflicting_groups += 1
            conflicting_images_removed += len(items)
            continue
        selected.append(min(items, key=lambda item: item.index))
        duplicate_images_removed += len(items) - 1

    return sorted(selected, key=lambda item: item.index), {
        "duplicate_groups": duplicate_groups,
        "duplicate_images_removed": duplicate_images_removed,
        "conflicting_duplicate_groups": conflicting_groups,
        "conflicting_duplicate_images_removed": conflicting_images_removed,
    }


def split_vector(records: list[Record]) -> tuple[int, int, int]:
    counts = Counter(box.class_id for record in records for box in record.boxes)
    return len(records), counts[0], counts[1]


def choose_grouped_splits(records: list[Record], seed: int) -> dict[int, str]:
    grouped: dict[int, list[Record]] = defaultdict(list)
    for record in records:
        grouped[record.group].append(record)
    keys = sorted(grouped)
    if len(keys) < 10:
        raise ValueError("At least 10 source groups are required for an 80/10/10 split")

    total = split_vector(records)
    target_ratios = {"train": 0.8, "val": 0.1, "test": 0.1}
    val_groups = max(1, round(len(keys) * 0.1))
    test_groups = max(1, round(len(keys) * 0.1))
    vectors = {key: split_vector(grouped[key]) for key in keys}
    rng = random.Random(seed)
    best_score = float("inf")
    best: dict[int, str] | None = None

    # Search deterministic group assignments for balanced images and both classes.
    for _ in range(20_000):
        shuffled = keys.copy()
        rng.shuffle(shuffled)
        test = set(shuffled[:test_groups])
        val = set(shuffled[test_groups : test_groups + val_groups])
        assignment = {
            key: "test" if key in test else "val" if key in val else "train"
            for key in keys
        }
        actual = {split: [0, 0, 0] for split in target_ratios}
        for key, split in assignment.items():
            for position, value in enumerate(vectors[key]):
                actual[split][position] += value
        score = 0.0
        for split, ratio in target_ratios.items():
            for position, value in enumerate(actual[split]):
                target = total[position] * ratio
                score += ((value - target) / max(1.0, target)) ** 2
        if score < best_score:
            best_score = score
            best = assignment

    if best is None:
        raise RuntimeError("Failed to construct grouped splits")
    return best


def reset_output(output: Path) -> None:
    marker = output / ".generated-by-prepare-voc-helmet"
    if output.exists():
        if not marker.exists():
            raise SystemExit(f"Refusing to replace unrecognized directory: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    marker.write_text("generated\n", encoding="ascii")


def link_or_copy(source: Path, destination: Path) -> None:
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def yolo_lines(record: Record) -> list[str]:
    lines: list[str] = []
    for box in record.boxes:
        center_x = ((box.xmin + box.xmax) / 2) / record.width
        center_y = ((box.ymin + box.ymax) / 2) / record.height
        width = (box.xmax - box.xmin) / record.width
        height = (box.ymax - box.ymin) / record.height
        lines.append(
            f"{box.class_id} {center_x:.8f} {center_y:.8f} {width:.8f} {height:.8f}"
        )
    return lines


def write_configs(output: Path, project_root: Path) -> tuple[Path, Path]:
    dataset = {
        "path": output.resolve().as_posix(),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": TARGET_NAMES,
    }
    dataset_path = output / "dataset.yaml"
    dataset_path.write_text(yaml.safe_dump(dataset, sort_keys=False), encoding="ascii")

    base = project_root / "data" / "bike-helmet-yolo"
    manual = project_root / "data" / "wuhan-manual-yolo"
    combined = {
        "path": project_root.resolve().as_posix(),
        "train": [
            (base / "images" / "train").resolve().as_posix(),
            (manual / "images" / "train").resolve().as_posix(),
            (output / "images" / "train").resolve().as_posix(),
        ],
        "val": [
            (base / "images" / "valid").resolve().as_posix(),
            (output / "images" / "val").resolve().as_posix(),
        ],
        "test": [
            (base / "images" / "test").resolve().as_posix(),
            (output / "images" / "test").resolve().as_posix(),
        ],
        "names": TARGET_NAMES,
    }
    combined_path = output / "combined-dataset-v5.yaml"
    combined_path.write_text(yaml.safe_dump(combined, sort_keys=False), encoding="ascii")
    return dataset_path, combined_path


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    project_root = Path(__file__).resolve().parents[2]
    if not source.is_dir():
        raise SystemExit(f"Source dataset does not exist: {source}")

    images = image_index(source)
    annotations = sorted(source.rglob("*.xml"))
    if len(images) != len(annotations):
        raise SystemExit(
            f"Expected one annotation per image, found images={len(images)}, xml={len(annotations)}"
        )

    candidates: list[Record] = []
    exclusions: Counter[str] = Counter()
    for annotation in annotations:
        try:
            candidates.append(parse_record(annotation, images))
        except LookupError as exc:
            exclusions[str(exc)] += 1

    selected, duplicate_stats = deduplicate(candidates)
    assignments = choose_grouped_splits(selected, args.seed)
    reset_output(output)

    split_records: dict[str, list[Record]] = defaultdict(list)
    for record in selected:
        split_records[assignments[record.group]].append(record)

    manifest_path = output / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["split", "group", "index", "sha256", "source_image"])
        for split in ("train", "val", "test"):
            image_dir = output / "images" / split
            label_dir = output / "labels" / split
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)
            for record in sorted(split_records[split], key=lambda item: item.index):
                link_or_copy(record.image, image_dir / record.image.name)
                (label_dir / f"{record.image.stem}.txt").write_text(
                    "\n".join(yolo_lines(record)) + "\n", encoding="ascii"
                )
                writer.writerow(
                    [split, record.group, record.index, record.digest, str(record.image)]
                )

    split_groups = {
        split: {record.group for record in records}
        for split, records in split_records.items()
    }
    if (
        split_groups["train"] & split_groups["val"]
        or split_groups["train"] & split_groups["test"]
        or split_groups["val"] & split_groups["test"]
    ):
        raise RuntimeError("Source groups leaked across generated splits")
    split_hashes = {
        split: {record.digest for record in records}
        for split, records in split_records.items()
    }
    if (
        split_hashes["train"] & split_hashes["val"]
        or split_hashes["train"] & split_hashes["test"]
        or split_hashes["val"] & split_hashes["test"]
    ):
        raise RuntimeError("Duplicate image content leaked across generated splits")

    dataset_path, combined_path = write_configs(output, project_root)
    report = [
        f"source_images: {len(images)}",
        f"source_annotations: {len(annotations)}",
        f"eligible_before_dedup: {len(candidates)}",
        f"excluded_missing_helmet_status: {exclusions['missing helmet status']}",
        f"excluded_missing_rider: {exclusions['missing rider']}",
    ]
    report.extend(f"{key}: {value}" for key, value in duplicate_stats.items())
    for split in ("train", "val", "test"):
        image_count, helmet_count, no_helmet_count = split_vector(split_records[split])
        report.append(
            f"{split}: images={image_count} helmet={helmet_count} "
            f"no_helmet={no_helmet_count} groups={len(split_groups[split])}"
        )
    report.extend(
        [
            f"dataset_config: {dataset_path}",
            f"combined_config: {combined_path}",
            "combined_config_excludes: ebike-helmet-clean-v1",
        ]
    )
    report_text = "\n".join(report) + "\n"
    (output / "preparation-report.txt").write_text(report_text, encoding="utf-8")
    print(report_text, end="")


if __name__ == "__main__":
    main()
