from app.rules import Detection, evaluate_violations


def test_no_helmet_requires_positive_bare_head_detection():
    detections = [
        Detection("electric_bicycle", 0.95, (100, 200, 300, 400), 7),
        Detection("person", 0.94, (140, 80, 230, 350), 12),
    ]
    results = evaluate_violations(detections)
    assert not any(item["code"] == "NO_HELMET" for item in results)
    uncertain = next(item for item in results if item["code"] == "HELMET_UNCERTAIN")
    assert uncertain["rider_bboxes"] == [[140, 80, 230, 350]]


def test_bare_head_creates_helmet_review_event():
    detections = [
        Detection("electric_bicycle", 0.96, (100, 200, 320, 420), 7),
        Detection("person", 0.95, (130, 80, 220, 360), 12),
        Detection("person", 0.93, (215, 95, 295, 365), 13),
        Detection("helmet", 0.91, (150, 75, 195, 125)),
        Detection("no_helmet", 0.90, (230, 90, 275, 140)),
    ]
    results = evaluate_violations(detections)
    codes = {item["code"] for item in results}
    assert "NO_HELMET" in codes


def test_person_is_assigned_to_only_one_nearest_vehicle():
    detections = [
        Detection("bicycle", 0.94, (100, 200, 200, 360), 1),
        Detection("motorcycle", 0.91, (140, 250, 340, 460), 2),
        Detection("person", 0.93, (115, 90, 185, 330), 10),
        Detection("no_helmet", 0.88, (132, 92, 168, 135)),
    ]
    results = evaluate_violations(detections)
    no_helmet = [item for item in results if item["code"] == "NO_HELMET"]
    assert len(no_helmet) == 1
    assert no_helmet[0]["vehicle_track_id"] in {1, 2}
    assert no_helmet[0]["head_bbox"] == [132, 92, 168, 135]
    assert no_helmet[0]["vehicle_bbox"]


def test_nearby_pedestrian_is_not_counted_as_rider():
    detections = [
        Detection("bicycle", 0.94, (100, 220, 200, 380), 1),
        Detection("person", 0.93, (120, 100, 180, 350), 10),
        Detection("person", 0.96, (230, 80, 300, 360), 11),
    ]
    results = evaluate_violations(detections)
    assert not any(item["code"] == "NO_HELMET" for item in results)


def test_dismounted_person_leaning_over_motorcycle_is_not_a_rider():
    # Geometry reproduced from a person standing beside and inspecting a bike.
    detections = [
        Detection("motorcycle", 0.78, (345.4, 185.0, 558.8, 339.0), 1),
        Detection("person", 0.93, (291.9, 153.2, 417.4, 337.9), 10),
        Detection("no_helmet", 0.90, (325.0, 150.0, 370.0, 190.0)),
    ]
    results = evaluate_violations(detections)
    assert not any(item["code"] == "NO_HELMET" for item in results)
