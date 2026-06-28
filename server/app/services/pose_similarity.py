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

# ---------------------------------------------------------------------------
# Torso normalisation
# ---------------------------------------------------------------------------
_TORSO_ANCHORS = ("left_shoulder", "right_shoulder", "left_hip", "right_hip")
_MIN_TORSO_HEIGHT = 0.05  # normalised units; skip if person is too small


# ---------------------------------------------------------------------------
# Ready-pose detection  ("양팔 T자" — both arms horizontal, elbows extended)
# ---------------------------------------------------------------------------
# Players hold both arms out sideways (like the letter T) to trigger game start.
# Shoulder angle (elbow-shoulder-hip) ≈ 85~95° means arm is horizontal.
# Elbow angle (shoulder-elbow-wrist) ≈ 155~180° means arm is straight.
READY_POSE_SHOULDER_MIN = 70.0   # degrees — shoulder joint
READY_POSE_SHOULDER_MAX = 110.0
READY_POSE_ELBOW_MIN    = 140.0  # degrees — elbow joint (arm straight)

# Approximate joint angles (degrees) of a neutral standing "rest" pose
# (arms hanging down, legs straight). Poses far from this are "expressive";
# poses close to it (everyone just standing identically) score low even when
# similarity is high — this is the anti-"stand still and win" gate.
REST_ANGLES: dict[str, float] = {
    "left_elbow": 165.0,
    "right_elbow": 165.0,
    "left_shoulder": 12.0,
    "right_shoulder": 12.0,
    "left_hip": 172.0,
    "right_hip": 172.0,
    "left_knee": 175.0,
    "right_knee": 175.0,
}
# Average deviation (degrees) from rest that counts as "fully expressive".
EXPRESSIVENESS_FULL_DEG = 45.0
# How much a still/neutral group is penalised. The activity factor maps
# expressiveness 0..1 -> ACTIVITY_FLOOR..1, then multiplies the similarity.
ACTIVITY_FLOOR = 0.12
# Below this group expressiveness the coach yells "move more!".
STILL_EXPRESSIVENESS = 0.18


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


def _aspect_x_scale(pose_result: dict[str, object]) -> float:
    """Return the x-axis scale (frame_width / frame_height) used to undo the
    aspect-ratio distortion of normalised keypoint coordinates.

    Keypoint ``x`` is normalised to the frame width and ``y`` to the frame
    height. For a non-square frame (e.g. 640x480) one normalised unit of x and
    one of y span different pixel distances, which warps every measured angle.
    Scaling x by the frame aspect ratio puts both axes in the same units so the
    angles are geometrically correct. Falls back to 1.0 when the frame size is
    missing or invalid.
    """
    width = pose_result.get("frame_width")
    height = pose_result.get("frame_height")
    try:
        w = float(width)  # type: ignore[arg-type]
        h = float(height)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 1.0
    if w > 0.0 and h > 0.0:
        return w / h
    return 1.0


def _angle_degrees(
    point_a: dict[str, float],
    vertex: dict[str, float],
    point_c: dict[str, float],
    x_scale: float = 1.0,
) -> float:
    ax = (float(point_a["x"]) - float(vertex["x"])) * x_scale
    ay = float(point_a["y"]) - float(vertex["y"])
    cx = (float(point_c["x"]) - float(vertex["x"])) * x_scale
    cy = float(point_c["y"]) - float(vertex["y"])

    dot = ax * cx + ay * cy
    cross = ax * cy - ay * cx
    return math.degrees(math.atan2(abs(cross), dot))


def _normalize_keypoints_to_torso(
    keypoints: dict[str, dict[str, float]],
    x_scale: float,
) -> dict[str, dict[str, float]] | None:
    """Project keypoints into the torso coordinate frame.

    Frame definition
    ----------------
    * Origin  — midpoint of the four torso anchors (torso centre).
    * Y-axis  — hip-midpoint → shoulder-midpoint (spine direction, upward).
    * X-axis  — 90° CCW from Y (rightward in image).
    * Scale   — torso height (shoulder-mid to hip-mid distance) == 1.0.

    Removes camera tilt, player position, and body-size differences.
    Returns None when any anchor is invisible or the torso is too small.
    """
    for name in _TORSO_ANCHORS:
        kp = keypoints.get(name)
        if kp is None or not _is_visible(kp):
            return None

    def _px(kp: dict[str, float]) -> tuple[float, float]:
        return float(kp["x"]) * x_scale, float(kp["y"])

    lsx, lsy = _px(keypoints["left_shoulder"])
    rsx, rsy = _px(keypoints["right_shoulder"])
    lhx, lhy = _px(keypoints["left_hip"])
    rhx, rhy = _px(keypoints["right_hip"])

    smx, smy = (lsx + rsx) / 2.0, (lsy + rsy) / 2.0  # shoulder midpoint
    hmx, hmy = (lhx + rhx) / 2.0, (lhy + rhy) / 2.0  # hip midpoint

    spine_x, spine_y = smx - hmx, smy - hmy
    torso_h = math.hypot(spine_x, spine_y)
    if torso_h < _MIN_TORSO_HEIGHT:
        return None

    # Unit Y-axis (upward along spine) and X-axis (90° CCW from Y).
    uy_x, uy_y = spine_x / torso_h, spine_y / torso_h
    ux_x, ux_y = -uy_y, uy_x

    cx = (lsx + rsx + lhx + rhx) / 4.0
    cy = (lsy + rsy + lhy + rhy) / 4.0

    normalised: dict[str, dict[str, float]] = {}
    for name, kp in keypoints.items():
        dx = float(kp["x"]) * x_scale - cx
        dy = float(kp["y"]) - cy
        new_kp = dict(kp)
        new_kp["x"] = (dx * ux_x + dy * ux_y) / torso_h
        new_kp["y"] = (dx * uy_x + dy * uy_y) / torso_h
        normalised[name] = new_kp  # type: ignore[assignment]
    return normalised


def detect_ready_pose(pose_result: dict[str, object] | None) -> bool:
    """Return True when the player is holding the T-pose (양팔 T자).

    Both arms must be raised out to the sides (shoulder ~90°). The defining
    feature is judged from the shoulder joints (elbow-shoulder-hip), which only
    need the shoulder, elbow and hip keypoints — these stay visible even when
    the wrists leave the frame edge during a wide T-pose.

    The elbow-straightness check needs the wrist, which is frequently cut off (or
    drops below the confidence threshold) when the arms are fully extended, so it
    is only enforced when the wrist is actually visible. This keeps the gesture
    reliable instead of silently never triggering.
    """
    if not pose_result or not pose_result.get("person_detected"):
        return False
    angles = compute_joint_angles(pose_result)
    # Both arms must be horizontal — this is the gesture's defining feature.
    for joint in ("left_shoulder", "right_shoulder"):
        angle = angles.get(joint)
        if angle is None or not (READY_POSE_SHOULDER_MIN <= angle <= READY_POSE_SHOULDER_MAX):
            return False
    # Arms should be straight, but only check when the wrist (and thus the elbow
    # angle) is available; a missing elbow angle means the wrist is out of frame.
    for joint in ("left_elbow", "right_elbow"):
        angle = angles.get(joint)
        if angle is not None and angle < READY_POSE_ELBOW_MIN:
            return False
    return True


def compute_joint_angles(pose_result: dict[str, object]) -> dict[str, float]:
    """Return joint-name → angle (degrees) for all visible joints.

    Keypoints are first projected into the torso coordinate frame so that
    camera tilt, player position, and body-size differences are cancelled out.
    Falls back to raw aspect-ratio-corrected coords when torso anchors are
    missing or the person is too small in frame.
    """
    keypoints = _keypoint_map(pose_result)
    x_scale = _aspect_x_scale(pose_result)

    normalised = _normalize_keypoints_to_torso(keypoints, x_scale)
    if normalised is not None:
        work_kps = normalised
        angle_x_scale = 1.0  # torso frame already has isotropic units
    else:
        work_kps = keypoints
        angle_x_scale = x_scale

    angles: dict[str, float] = {}
    for joint_name, (a_name, vertex_name, c_name) in JOINT_DEFINITIONS.items():
        a = work_kps.get(a_name)
        vertex = work_kps.get(vertex_name)
        c = work_kps.get(c_name)
        if a is None or vertex is None or c is None:
            continue
        if not (_is_visible(a) and _is_visible(vertex) and _is_visible(c)):
            continue
        angles[joint_name] = _angle_degrees(a, vertex, c, angle_x_scale)
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
    """Backward-compatible wrapper returning ``(score, ready_count)``.

    ``score`` already includes the activity (anti-stillness) gate.
    """
    analysis = analyze_group(pose_results)
    return analysis["score"], analysis["ready_count"]


def pose_expressiveness(angles: dict[str, float]) -> float:
    """0~1 measure of how far a pose is from the neutral standing rest pose."""
    if not angles:
        return 0.0
    deviations = [
        abs(angle - REST_ANGLES[joint])
        for joint, angle in angles.items()
        if joint in REST_ANGLES
    ]
    if not deviations:
        return 0.0
    mean_dev = sum(deviations) / len(deviations)
    factor = mean_dev / EXPRESSIVENESS_FULL_DEG
    return max(0.0, min(1.0, factor))


def _activity_factor(expressiveness: float) -> float:
    return ACTIVITY_FLOOR + (1.0 - ACTIVITY_FLOOR) * expressiveness


def analyze_group(pose_results: list[dict[str, object] | None]) -> dict:
    """Full per-tick analysis used by the game.

    Returns a dict with:
      - ``score``: 0~100 telepathy gauge (similarity gated by group activity)
      - ``similarity``: 0~100 raw pairwise pose similarity (no activity gate)
      - ``expressiveness``: 0~1 average how-much-they-moved-from-rest
      - ``ready_count``: number of detected players
      - ``players``: list aligned to ``pose_results`` with per-player
        ``{index, present, sync, expressiveness}`` (sync = avg similarity to the
        other present players, 0~100, or None).
    """
    n = len(pose_results)
    angles_by_index: list[dict[str, float] | None] = [None] * n
    expr_by_index: list[float] = [0.0] * n

    for i, pose_result in enumerate(pose_results):
        if not pose_result or not pose_result.get("person_detected"):
            continue
        angles = compute_joint_angles(pose_result)
        if angles:
            angles_by_index[i] = angles
            expr_by_index[i] = pose_expressiveness(angles)

    present_indices = [i for i in range(n) if angles_by_index[i] is not None]
    ready_count = len(present_indices)

    # Pairwise similarities (and per-player sync accumulation).
    sync_sum = [0.0] * n
    sync_cnt = [0] * n
    similarities: list[float] = []
    for a in range(len(present_indices)):
        for b in range(a + 1, len(present_indices)):
            ia, ib = present_indices[a], present_indices[b]
            sim = pose_pair_similarity(angles_by_index[ia], angles_by_index[ib])  # type: ignore[arg-type]
            if sim is None:
                continue
            similarities.append(sim)
            sync_sum[ia] += sim
            sync_cnt[ia] += 1
            sync_sum[ib] += sim
            sync_cnt[ib] += 1

    similarity = sum(similarities) / len(similarities) if similarities else 0.0
    expressiveness = (
        sum(expr_by_index[i] for i in present_indices) / ready_count if ready_count else 0.0
    )
    score = similarity * _activity_factor(expressiveness) if ready_count >= 2 else 0.0

    players = []
    for i in range(n):
        present = angles_by_index[i] is not None
        sync = (sync_sum[i] / sync_cnt[i]) if sync_cnt[i] else None
        players.append(
            {
                "index": i,
                "present": present,
                "sync": round(sync, 1) if sync is not None else None,
                "expressiveness": round(expr_by_index[i], 3),
            }
        )

    return {
        "score": score,
        "similarity": similarity,
        "expressiveness": expressiveness,
        "ready_count": ready_count,
        "players": players,
    }


def analyze_group_debug(pose_results: list[dict[str, object] | None]) -> dict:
    """Verbose variant of :func:`analyze_group` for the diagnostics overlay.

    On top of the regular game analysis it exposes, per board, the visible
    joint count and each measured joint angle, plus the pairwise similarity
    matrix and the separated similarity / activity-factor / final-score values.
    Used only by the ``/api/debug/analysis`` endpoint — never on the game loop.
    """
    base = analyze_group(pose_results)

    boards: list[dict[str, object]] = []
    angles_by_index: list[dict[str, float] | None] = []
    for index, pose_result in enumerate(pose_results):
        detected = bool(pose_result and pose_result.get("person_detected"))
        angles = compute_joint_angles(pose_result) if detected and pose_result else {}
        angles_by_index.append(angles or None)
        boards.append(
            {
                "index": index,
                "person_detected": detected,
                "visible_joints": len(angles),
                "angles": {name: round(value, 1) for name, value in angles.items()},
                "missing_joints": [j for j in JOINT_DEFINITIONS if j not in angles],
            }
        )

    present = [i for i in range(len(pose_results)) if angles_by_index[i] is not None]
    pairs: list[dict[str, object]] = []
    for a in range(len(present)):
        for b in range(a + 1, len(present)):
            ia, ib = present[a], present[b]
            sim = pose_pair_similarity(angles_by_index[ia], angles_by_index[ib])  # type: ignore[arg-type]
            pairs.append({"a": ia, "b": ib, "sim": round(sim, 1) if sim is not None else None})

    return {
        "ready_count": base["ready_count"],
        "similarity": round(base["similarity"], 1),
        "activity_factor": round(_activity_factor(base["expressiveness"]), 3),
        "expressiveness": round(base["expressiveness"], 3),
        "score": round(base["score"], 1),
        "boards": boards,
        "pairs": pairs,
    }

