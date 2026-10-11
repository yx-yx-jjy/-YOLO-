from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import defaultdict
from pathlib import Path

import yaml


CLASS_ALIASES = {
    "with_helmet": "helmet",
    "helmet": "helmet",
    "without_helmet": "no_helmet",
    "no_helmet": "no_helmet",
}
CLASS_IDS = {"helmet": 0, "no_helmet": 1}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert the CC BY bike helmet COCO dataset to YOLO")
    parser.add_argument("--source", type=Path, required=True, help="Dataset root containing train/valid/test")
    parser.add_argument("--output", type=Path, required=True, help="Output YOLO dataset root")
    return parser.parse_args()


def normalize_name(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def link_or_copy(source: Path, destination: Path) -> None:
    if destination.exists():
        return
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def convert_split(source_root: Path, output_root: Path, split: str) -> dict[str, int]:
    split_root = source_root / split
    annotation_path = split_root / "_annotations.coco.json"
    if not annotation_path.exists():
        raise FileNotFoundError(f"Missing COCO annotations: {annotation_path}")

    coco = json.loads(annotation_path.read_text(encoding="utf-8"))
    category_map: dict[int, int] = {}
    for category in coco["categories"]:
        canonical = CLASS_ALIASES.get(normalize_name(category["name"]))
        if canonical:
            category_map[int(category["id"])] = CLASS_IDS[canonical]

    missing_classes = set(CLASS_IDS.values()) - set(category_map.values())
    if missing_classes:
        raise ValueError(f"Dataset is missing required classes: {sorted(missing_classes)}")

    images = {int(item["id"]): item for item in coco["images"]}
    annotations_by_image: dict[int, list[dict]] = defaultdict(list)
    for annotation in coco["annotations"]:
        if int(annotation["category_id"]) in category_map:
            annotations_by_image[int(annotation["image_id"])].append(annotation)

    image_output = output_root / "images" / split
    label_output = output_root / "labels" / split
    image_output.mkdir(parents=True, exist_ok=True)
    label_output.mkdir(parents=True, exist_ok=True)

    boxes_written = 0
    for image_id, image in images.items():
        source_image = split_root / image["file_name"]
        if not source_image.exists() or source_image.suffix.lower() not in IMAGE_SUFFIXES:
            raise FileNotFoundError(f"Missing image referenced by COCO data: {source_image}")

        width = float(image["width"])
        height = float(image["height"])
        lines: list[str] = []
        for annotation in annotations_by_image.get(image_id, []):
            x, y, box_width, box_height = (float(value) for value in annotation["bbox"])
            x1 = max(0.0, min(width, x))
            y1 = max(0.0, min(height, y))
            x2 = max(0.0, min(width, x + box_width))
            y2 = max(0.0, min(height, y + box_height))
            if x2 <= x1 or y2 <= y1:
                continue

            class_id = category_map[int(annotation["category_id"])]
            center_x = ((x1 + x2) / 2) / width
            center_y = ((y1 + y2) / 2) / height
            normalized_width = (x2 - x1) / width
            normalized_height = (y2 - y1) / height
            lines.append(
                f"{class_id} {center_x:.6f} {center_y:.6f} "
                f"{normalized_width:.6f} {normalized_height:.6f}"
            )
            boxes_written += 1

        link_or_copy(source_image, image_output / source_image.name)
        (label_output / f"{source_image.stem}.txt").write_text(
            "\n".join(lines) + ("\n" if lines else ""),
            encoding="ascii",
        )

    return {"images": len(images), "boxes": boxes_written}


def main() -> None:
    args = parse_args()
    source_root = args.source.resolve()
    output_root = args.output.resolve()
    if not source_root.exists():
        raise SystemExit(f"Source dataset does not exist: {source_root}")

    stats = {
        split: convert_split(source_root, output_root, split)
        for split in ("train", "valid", "test")
    }
    dataset_config = {
        "path": output_root.as_posix(),
        "train": "images/train",
        "val": "images/valid",
        "test": "images/test",
        "names": {0: "helmet", 1: "no_helmet"},
    }
    (output_root / "dataset.yaml").write_text(
        yaml.safe_dump(dataset_config, allow_unicode=False, sort_keys=False),
        encoding="ascii",
    )
    print(json.dumps(stats, indent=2))
    print(f"Dataset config: {output_root / 'dataset.yaml'}")


if __name__ == "__main__":
    main()
