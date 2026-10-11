from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


VEHICLE_CLASSES = {
    "electric_bicycle", "electric-bike", "ebike", "e-bike", "motorcycle",
    "motorbike", "bicycle", "scooter",
}
PERSON_CLASSES = {"person", "rider", "driver"}
HELMET_CLASSES = {"helmet", "with_helmet", "wearing_helmet"}
NO_HELMET_CLASSES = {
    "no_helmet", "without_helmet", "bare_head", "head", "no-helmet",
}
# Violation reporting should favor precision: a person standing next to or
# leaning over a vehicle must not be treated as a rider. These insets describe
# the high-confidence mounted area inside a detected vehicle box.
RIDER_HORIZONTAL_INSET = 0.10
# 0.99 means the rider's foot anchor may sit level with the vehicle's bottom edge
# (relative_foot_y <= 0.99), i.e. slightly below the box but not past it. A value
# of 0.97 rejected genuine riders whenever the person's box was a few pixels
# taller than the vehicle's, which is common when the vehicle is detected weakly.
# 1.00 is deliberately NOT used: it starts admitting detection false positives
# (measured: 0.99 -> 317 TP/12 FP, 1.00 -> 318 TP/13 FP).
RIDER_MAX_FOOT_Y = 0.99
RIDER_MAX_MATCH_SCORE = 0.82


def normalize_label(label: str) -> str:
    return label.strip().lower().replace(" ", "_")


@dataclass(frozen=True)
class Detection:
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]
    track_id: int | None = None

    def to_dict(self) -> dict:
        result = asdict(self)
        result["bbox"] = [round(value, 1) for value in self.bbox]
        result["confidence"] = round(self.confidence, 4)
        return result


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _point_in_box(point: tuple[float, float], box: tuple[float, float, float, float]) -> bool:
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def _rider_match_score(
    person_box: tuple[float, float, float, float],
    vehicle_box: tuple[float, float, float, float],
) -> float | None:
    """Return a lower-is-better rider/vehicle score, or None if implausible.

    A rider's lower-body anchor should be horizontally over the vehicle and
    close to its upper section. Using the person's center against a large
    expanded vehicle area pulled nearby pedestrians into several vehicles.
    """
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

    # A standing person's center is commonly at the extreme side of the
    # vehicle and their feet reach the same ground line as the wheels.
    if not RIDER_HORIZONTAL_INSET <= relative_x <= 1 - RIDER_HORIZONTAL_INSET:
        return None
    if relative_foot_y > RIDER_MAX_FOOT_Y:
        return None

    horizontal_margin = min(person_width * 0.35, vehicle_width * 0.30)
    if not vx1 - horizontal_margin <= foot_x <= vx2 + horizontal_margin:
        return None

    max_gap_above = min(person_height * 0.25, vehicle_height * 0.40)
    if foot_y < vy1 - max_gap_above or foot_y > vy2 + vehicle_height * 0.15:
        return None

    if foot_x < vx1:
        horizontal_gap = vx1 - foot_x
    elif foot_x > vx2:
        horizontal_gap = foot_x - vx2
    else:
        horizontal_gap = 0.0

    target_y = vy1 + vehicle_height * 0.22
    vertical_distance = abs(foot_y - target_y) / vehicle_height
    center_distance = abs(foot_x - (vx1 + vx2) / 2) / vehicle_width
    return horizontal_gap / vehicle_width * 2.0 + vertical_distance + center_distance * 0.35


def _head_zone(person_box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = person_box
    width = x2 - x1
    height = y2 - y1
    return (x1 - width * 0.2, y1 - height * 0.08, x2 + width * 0.2, y1 + height * 0.42)


def _assign_riders(
    people: list[Detection], vehicles: list[Detection]
) -> dict[int, list[Detection]]:
    """Assign each person to at most one vehicle."""
    assignments: dict[int, list[Detection]] = {index: [] for index in range(len(vehicles))}
    for person in people:
        candidates = [
            (score, vehicle_index)
            for vehicle_index, vehicle in enumerate(vehicles)
            if (score := _rider_match_score(person.bbox, vehicle.bbox)) is not None
        ]
        if candidates:
            score, vehicle_index = min(candidates)
            if score <= RIDER_MAX_MATCH_SCORE:
                assignments[vehicle_index].append(person)
    return assignments


def _assign_headgear(
    people: list[Detection], headgear: list[Detection]
) -> dict[int, list[Detection]]:
    """Assign every helmet/bare-head box to its nearest person head once."""
    assignments: dict[int, list[Detection]] = {index: [] for index in range(len(people))}
    for item in headgear:
        item_center = _center(item.bbox)
        candidates: list[tuple[float, int]] = []
        for person_index, person in enumerate(people):
            zone = _head_zone(person.bbox)
            if not _point_in_box(item_center, zone):
                continue
            zone_width = max(1.0, zone[2] - zone[0])
            zone_height = max(1.0, zone[3] - zone[1])
            zone_center = _center(zone)
            score = (
                abs(item_center[0] - zone_center[0]) / zone_width
                + abs(item_center[1] - zone_center[1]) / zone_height
            )
            candidates.append((score, person_index))
        if candidates:
            _, person_index = min(candidates)
            assignments[person_index].append(item)
    return assignments


def _confidence(values: Iterable[float]) -> float:
    values = list(values)
    return round(min(values), 4) if values else 0.0


def evaluate_violations(detections: list[Detection]) -> list[dict]:
    vehicles = [item for item in detections if normalize_label(item.class_name) in VEHICLE_CLASSES]
    people = [item for item in detections if normalize_label(item.class_name) in PERSON_CLASSES]
    helmets = [item for item in detections if normalize_label(item.class_name) in HELMET_CLASSES]
    bare_heads = [item for item in detections if normalize_label(item.class_name) in NO_HELMET_CLASSES]
    violations: list[dict] = []
    rider_assignments = _assign_riders(people, vehicles)
    helmet_assignments = _assign_headgear(people, helmets)
    bare_head_assignments = _assign_headgear(people, bare_heads)
    person_indexes = {id(person): index for index, person in enumerate(people)}

    for vehicle_index, vehicle in enumerate(vehicles):
        riders = rider_assignments[vehicle_index]
        vehicle_id = vehicle.track_id if vehicle.track_id is not None else vehicle_index

        rider_details = []
        for rider in sorted(riders, key=lambda item: item.bbox[0]):
            person_index = person_indexes[id(rider)]
            matched_helmets = helmet_assignments[person_index]
            matched_bare_heads = bare_head_assignments[person_index]
            best_helmet = max(matched_helmets, key=lambda item: item.confidence, default=None)
            best_bare_head = max(matched_bare_heads, key=lambda item: item.confidence, default=None)
            if best_bare_head and (not best_helmet or best_bare_head.confidence >= best_helmet.confidence):
                helmet_state = "no_helmet"
            elif best_helmet:
                helmet_state = "helmet"
            else:
                helmet_state = "unknown"
            rider_details.append({"helmet_state": helmet_state})

            if helmet_state == "no_helmet" and best_bare_head:
                violations.append({
                    "code": "NO_HELMET",
                    "title": "未按规定佩戴安全头盔",
                    "severity": "high",
                    "confidence": _confidence([vehicle.confidence, rider.confidence, best_bare_head.confidence]),
                    "vehicle_track_id": vehicle_id,
                    "review_required": True,
                    "evidence_bbox": list(rider.bbox),
                    "head_bbox": list(best_bare_head.bbox),
                    "vehicle_bbox": list(vehicle.bbox),
                })

        if riders and not any(item["helmet_state"] != "unknown" for item in rider_details):
            violations.append({
                "code": "HELMET_UNCERTAIN",
                "title": "头盔状态无法确认",
                "severity": "info",
                "confidence": vehicle.confidence,
                "vehicle_track_id": vehicle_id,
                "review_required": True,
                "is_violation": False,
                "evidence_bbox": list(vehicle.bbox),
                "vehicle_bbox": list(vehicle.bbox),
                "rider_bboxes": [list(rider.bbox) for rider in riders],
            })

    return violations
