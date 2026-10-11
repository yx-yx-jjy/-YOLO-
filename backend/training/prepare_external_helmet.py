from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import yaml


IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
SOURCE_CLASSES = ["head", "helmet"]
TARGET_NAMES = {0: "helmet", 1: "no_helmet"}
CLASS_REMAP = {0: 1, 1: 0}
RF_SUFFIX_RE = re.compile(r"\.rf\.[0-9a-f]+$", re.IGNORECASE)
VIDEO_FRAME_RE = re.compile(r"_mp4-\d+.*$", re.IGNORECASE)


@dataclass(frozen=True)
class Candidate:
    split: str
    image: Path
    label: Path
    origin: str
    rows: tuple[tuple[int, float, float, float, float], ...]
    oversized: bool


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Clean and remap the external helmet dataset")
    parser.add_argument(
        "--source",
        type=Path,
        default=root / "数据集" / "电动车头盔和不佩戴头盔" / "电动车头盔和不佩戴头盔",
    )
    parser.add_argument(
        "--base-dataset",
        type=Path,
        default=root / "data" / "bike-helmet-yolo",
    )
    parser.add_argument(
        "--manual-dataset",
        type=Path,
        default=root / "data" / "wuhan-manual-yolo",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "data" / "ebike-helmet-clean-v1",
    )
    parser.add_argument("--seed", type=int, default=20261001)
    return parser.parse_args()


def origin_key(stem: str) -> str:
    return RF_SUFFIX_RE.sub("", stem).lower()


def split_group(origin: str) -> str:
    # Adjacent frames from the same exported video must stay in one split.
    return VIDEO_FRAME_RE.sub("", origin)


def split_for(group: str, seed: int) -> str:
    digest = hashlib.sha256(f"{seed}:{group}".encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "val"
    return "test"


def find_image(directory: Path, stem: str) -> Path | None:
    for suffix in IMAGE_SUFFIXES:
        path = directory / f"{stem}{suffix}"
        if path.exists():
            return path
    return None


def read_rows(path: Path) -> tuple[tuple[tuple[int, float, float, float, float], ...], bool]:
    rows: list[tuple[int, float, float, float, float]] = []
    oversized = False
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        parts = raw.split()
        if len(parts) != 5:
            raise ValueError(f"{path}:{line_number}: expected 5 columns")
        class_id = int(parts[0])
        if class_id not in CLASS_REMAP:
            raise ValueError(f"{path}:{line_number}: unsupported class {class_id}")
        x, y, width, height = map(float, parts[1:])
        if width <= 0 or height <= 0:
            raise ValueError(f"{path}:{line_number}: non-positive box")
        if x - width / 2 < 0 or y - height / 2 < 0:
            raise ValueError(f"{path}:{line_number}: box crosses the top/left edge")
        if x + width / 2 > 1 or y + height / 2 > 1:
            raise ValueError(f"{path}:{line_number}: box crosses the bottom/right edge")
        oversized |= width * height > 0.25 or width > 0.8 or height > 0.8
        rows.append((class_id, x, y, width, height))
    if not rows:
        raise ValueError(f"{path}: empty annotations are not expected in this source")
    return tuple(rows), oversized


def existing_origin_keys(dataset: Path) -> set[str]:
    keys: set[str] = set()
    images_root = dataset / "images"
    if not images_root.exists():
        return keys
    for image in images_root.glob("*/*"):
        if image.is_file() and image.suffix.lower() in IMAGE_SUFFIXES:
            keys.add(origin_key(image.stem))
    return keys


def reset_output(output: Path) -> None:
    marker = output / ".generated-by-prepare-external-helmet"
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


def write_yaml(output: Path, base: Path, manual: Path, project_root: Path) -> Path:
    dataset_yaml = {
        "path": output.resolve().as_posix(),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": TARGET_NAMES,
    }
    (output / "dataset.yaml").write_text(
        yaml.safe_dump(dataset_yaml, sort_keys=False), encoding="ascii"
    )

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
    path = output / "combined-dataset-v4.yaml"
    path.write_text(yaml.safe_dump(combined, sort_keys=False), encoding="ascii")
    return path


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    base = args.base_dataset.resolve()
    manual = args.manual_dataset.resolve()
    output = args.output.resolve()
    project_root = Path(__file__).resolve().parents[2]

    classes_path = source / "labels" / "classes.txt"
    if not classes_path.exists():
        raise SystemExit(f"Missing class definition: {classes_path}")
    classes = [line.strip() for line in classes_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if classes != SOURCE_CLASSES:
        raise SystemExit(f"Expected source classes {SOURCE_CLASSES}, found {classes}")

    candidates: list[Candidate] = []
    for split in ("train", "val", "test"):
        image_dir = source / "images" / split
        label_dir = source / "labels" / split
        if not image_dir.is_dir() or not label_dir.is_dir():
            raise SystemExit(f"Missing source split: {split}")
        for label in sorted(label_dir.glob("*.txt")):
            image = find_image(image_dir, label.stem)
            if image is None:
                raise SystemExit(f"Missing image for {label}")
            rows, oversized = read_rows(label)
            candidates.append(
                Candidate(split, image, label, origin_key(label.stem), rows, oversized)
            )

    by_origin: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        by_origin[candidate.origin].append(candidate)

    base_origins = existing_origin_keys(base)
    excluded_overlap = {origin for origin in by_origin if origin in base_origins}
    excluded_oversized = {
        origin for origin, items in by_origin.items() if any(item.oversized for item in items)
    }
    excluded = excluded_overlap | excluded_oversized

    selected: list[Candidate] = []
    for origin, items in sorted(by_origin.items()):
        if origin in excluded:
            continue
        # One representative prevents augmented copies from dominating training.
        selected.append(sorted(items, key=lambda item: (item.split != "train", item.image.name))[0])

    reset_output(output)
    image_counts: Counter = Counter()
    box_counts: dict[str, Counter] = defaultdict(Counter)
    split_groups: dict[str, set[str]] = defaultdict(set)
    for candidate in selected:
        group = split_group(candidate.origin)
        split = split_for(group, args.seed)
        split_groups[split].add(group)
        image_dir = output / "images" / split
        label_dir = output / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        link_or_copy(candidate.image, image_dir / candidate.image.name)

        remapped: list[str] = []
        for class_id, x, y, width, height in candidate.rows:
            target_id = CLASS_REMAP[class_id]
            remapped.append(f"{target_id} {x:.8f} {y:.8f} {width:.8f} {height:.8f}")
            box_counts[split][target_id] += 1
        (label_dir / f"{candidate.image.stem}.txt").write_text(
            "\n".join(remapped) + "\n", encoding="ascii"
        )
        image_counts[split] += 1

    if set.intersection(*(set(value) for value in split_groups.values())):
        raise RuntimeError("A source group leaked across generated splits")

    config = write_yaml(output, base, manual, project_root)
    report = [
        f"source_images: {len(candidates)}",
        f"source_origins: {len(by_origin)}",
        f"excluded_old_overlap_origins: {len(excluded_overlap)}",
        f"excluded_oversized_origins: {len(excluded_oversized)}",
        f"selected_unique_origins: {len(selected)}",
    ]
    for split in ("train", "val", "test"):
        report.append(
            f"{split}: images={image_counts[split]} helmet={box_counts[split][0]} "
            f"no_helmet={box_counts[split][1]} groups={len(split_groups[split])}"
        )
    report.append(f"combined_config: {config}")
    (output / "preparation-report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
