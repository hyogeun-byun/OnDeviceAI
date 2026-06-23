from __future__ import annotations

from itertools import combinations
from math import exp, hypot
from statistics import mean
from typing import Any

MIN_VISIBILITY = 0.2
MIN_COMMON_KEYPOINTS = 6


def calculate_pose_similarity(captures: list[dict[str, object]]) -> dict[str, object]:
    pose_items = [
        {
            "camera_id": str(capture["camera_id"]),
            "keypoints": _normalize_keypoints(capture.get("pose")),
        }
        for capture in captures
    ]
    pose_items = [item for item in pose_items if item["keypoints"]]

    if len(pose_items) < 2:
        return {
            "score": 100.0 if len(pose_items) == 1 else 0.0,
            "pair_count": 0,
            "pairs": [],
            "summary": "single_pose" if len(pose_items) == 1 else "no_pose",
        }

    pairs = []
    for first, second in combinations(pose_items, 2):
        pair = _compare_pair(first["camera_id"], first["keypoints"], second["camera_id"], second["keypoints"])
        pairs.append(pair)

    valid_scores = [float(pair["score"]) for pair in pairs if pair["score"] is not None]
    return {
        "score": mean(valid_scores) if valid_scores else 0.0,
        "pair_count": len(valid_scores),
        "pairs": pairs,
        "summary": "ok" if valid_scores else "not_enough_common_keypoints",
    }


def _compare_pair(
    first_camera_id: str,
    first_keypoints: dict[str, tuple[float, float]],
    second_camera_id: str,
    second_keypoints: dict[str, tuple[float, float]],
) -> dict[str, object]:
    common_names = sorted(set(first_keypoints) & set(second_keypoints))
    if len(common_names) < MIN_COMMON_KEYPOINTS:
        return {
            "camera_ids": [first_camera_id, second_camera_id],
            "score": None,
            "common_keypoints": len(common_names),
            "average_distance": None,
        }

    distances = [
        hypot(
            first_keypoints[name][0] - second_keypoints[name][0],
            first_keypoints[name][1] - second_keypoints[name][1],
        )
        for name in common_names
    ]
    average_distance = mean(distances)
    score = max(0.0, min(100.0, 100.0 * exp(-2.5 * average_distance)))
    return {
        "camera_ids": [first_camera_id, second_camera_id],
        "score": score,
        "common_keypoints": len(common_names),
        "average_distance": average_distance,
    }


def _normalize_keypoints(pose: object) -> dict[str, tuple[float, float]]:
    if not isinstance(pose, dict):
        return {}

    raw_keypoints = pose.get("keypoints", [])
    if not isinstance(raw_keypoints, list):
        return {}

    keypoints = {
        str(keypoint["name"]): (float(keypoint["x"]), float(keypoint["y"]))
        for keypoint in raw_keypoints
        if _is_visible_keypoint(keypoint)
    }
    if not keypoints:
        return {}

    center_x, center_y = _pose_center(keypoints)
    scale = _pose_scale(keypoints)
    return {
        name: ((x - center_x) / scale, (y - center_y) / scale)
        for name, (x, y) in keypoints.items()
    }


def _is_visible_keypoint(keypoint: Any) -> bool:
    if not isinstance(keypoint, dict):
        return False
    if not {"name", "x", "y"} <= set(keypoint):
        return False
    return float(keypoint.get("visibility") or 1.0) >= MIN_VISIBILITY


def _pose_center(keypoints: dict[str, tuple[float, float]]) -> tuple[float, float]:
    hip_names = ["left_hip", "right_hip"]
    hip_points = [keypoints[name] for name in hip_names if name in keypoints]
    if hip_points:
        return mean([point[0] for point in hip_points]), mean([point[1] for point in hip_points])

    return mean([point[0] for point in keypoints.values()]), mean([point[1] for point in keypoints.values()])


def _pose_scale(keypoints: dict[str, tuple[float, float]]) -> float:
    scale_candidates = []
    for first_name, second_name in [("left_shoulder", "right_shoulder"), ("left_hip", "right_hip")]:
        if first_name in keypoints and second_name in keypoints:
            first = keypoints[first_name]
            second = keypoints[second_name]
            scale_candidates.append(hypot(first[0] - second[0], first[1] - second[1]))

    if scale_candidates:
        return max(mean(scale_candidates), 0.001)

    xs = [point[0] for point in keypoints.values()]
    ys = [point[1] for point in keypoints.values()]
    return max(hypot(max(xs) - min(xs), max(ys) - min(ys)), 0.001)
