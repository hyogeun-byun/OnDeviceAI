from __future__ import annotations

import math

# Joint angle definitions: vertex -> (point_a, vertex, point_c)
# The angle is measured at the vertex landmark between the two limbs.
JOINT_DEFINITIONS: dict[str, tuple[str, str, str]] = {
    "left_elbow": ("left_shoulder", "left_elbow", "left_wrist"),
    "right_elbow": ("right_shoulder", "right_elbow", "right_wrist"),
    "left_shoulder": ("left_elbow", "left_shoulder", "left_hip"),
    "right_shoulder": ("right_elbow", "right_shoulder", "right_hip"),
    "left_hip": ("left_shoulder", "left_hip", "left_knee"),
    "right_hip": ("right_shoulder", "right_hip", "right_knee"),
    "left_knee": ("left_hip", "left_knee", "left_ankle"),
    "right_knee": ("right_hip", "right_knee", "right_ankle"),
}

VISIBILITY_THRESHOLD = 0.3
# Standard deviation (degrees) of the similarity gaussian. Smaller -> stricter.
SIMILARITY_SIGMA_DEG = 35.0


def _keypoint_map(pose_result: dict[str, object]) -> dict[str, dict[str, float]]:
    keypoints = pose_result.get("keypoints") or []
    result: dict[str, dict[str, float]] = {}
    for keypoint in keypoints:
        if isinstance(keypoint, dict) and isinstance(keypoint.get("name"), str):
            result[keypoint["name"]] = keypoint  # type: ignore[assignment]
    return result


def _is_visible(keypoint: dict[str, float]) -> bool:
    visibility = keypoint.get("visibility")
    if visibility is None:
        return True
    return float(visibility) >= VISIBILITY_THRESHOLD


def _angle_degrees(
    point_a: dict[str, float],
    vertex: dict[str, float],
    point_c: dict[str, float],
) -> float:
    ax = float(point_a["x"]) - float(vertex["x"])
    ay = float(point_a["y"]) - float(vertex["y"])
    cx = float(point_c["x"]) - float(vertex["x"])
    cy = float(point_c["y"]) - float(vertex["y"])

    dot = ax * cx + ay * cy
    cross = ax * cy - ay * cx
    return math.degrees(math.atan2(abs(cross), dot))


def compute_joint_angles(pose_result: dict[str, object]) -> dict[str, float]:
    """Return a map of joint name -> angle (degrees) for visible joints only."""
    keypoints = _keypoint_map(pose_result)
    angles: dict[str, float] = {}

    for joint_name, (a_name, vertex_name, c_name) in JOINT_DEFINITIONS.items():
        a = keypoints.get(a_name)
        vertex = keypoints.get(vertex_name)
        c = keypoints.get(c_name)
        if a is None or vertex is None or c is None:
            continue
        if not (_is_visible(a) and _is_visible(vertex) and _is_visible(c)):
            continue
        angles[joint_name] = _angle_degrees(a, vertex, c)

    return angles


def pose_pair_similarity(
    angles_a: dict[str, float],
    angles_b: dict[str, float],
) -> float | None:
    """Return a 0~100 similarity score between two poses, or None if not comparable."""
    common_joints = set(angles_a) & set(angles_b)
    if not common_joints:
        return None

    total = 0.0
    for joint in common_joints:
        diff = abs(angles_a[joint] - angles_b[joint])
        total += math.exp(-(diff * diff) / (2.0 * SIMILARITY_SIGMA_DEG * SIMILARITY_SIGMA_DEG))

    return 100.0 * total / len(common_joints)


def group_telepathy_score(pose_results: list[dict[str, object] | None]) -> tuple[float, int]:
    """Compute the group telepathy score (0~100) and the number of ready players.

    A player is "ready" when a person is detected and enough joints are visible.
    At least two ready players are required to produce a non-zero score.
    """
    angle_sets: list[dict[str, float]] = []
    for pose_result in pose_results:
        if not pose_result or not pose_result.get("person_detected"):
            continue
        angles = compute_joint_angles(pose_result)
        if angles:
            angle_sets.append(angles)

    ready_count = len(angle_sets)
    if ready_count < 2:
        return 0.0, ready_count

    similarities: list[float] = []
    for i in range(len(angle_sets)):
        for j in range(i + 1, len(angle_sets)):
            similarity = pose_pair_similarity(angle_sets[i], angle_sets[j])
            if similarity is not None:
                similarities.append(similarity)

    if not similarities:
        return 0.0, ready_count

    return sum(similarities) / len(similarities), ready_count
