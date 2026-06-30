"""Pose estimation model comparison benchmark.

Runs 4 models on every frame of an input video, draws the skeleton overlay,
and saves one annotated MP4 per model.  Output filenames include the model
name and average inference time so you can compare at a glance.

Models compared
---------------
1. MoveNet SinglePose Lightning int8  (TFLite)
2. MoveNet SinglePose Thunder  int8   (TFLite)   ← auto-download if missing
3. MediaPipe Pose Lite                (model_complexity=0)
4. MediaPipe Pose Full                (model_complexity=1)

Usage
-----
    # Run from the repo root
    python scratch/compare_models.py --video path/to/input.mp4

    # Custom output folder and thread count
    python scratch/compare_models.py --video input.mp4 --output-dir scratch/out --threads 4

Output
------
    scratch/out/movenet_lightning_<avg_ms>ms.mp4
    scratch/out/movenet_thunder_<avg_ms>ms.mp4
    scratch/out/mediapipe_lite_<avg_ms>ms.mp4
    scratch/out/mediapipe_full_<avg_ms>ms.mp4

    A comparison table is printed to stdout when all models finish.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import numpy as np

# ── Tee: mirror stdout to a log file ────────────────────────────────────────

class _Tee:
    """Writes every print() call to both the original stdout and a log file."""

    def __init__(self, log_path: Path) -> None:
        self._stdout = sys.stdout
        self._file = log_path.open("w", encoding="utf-8", buffering=1)
        sys.stdout = self

    def write(self, data: str) -> int:
        self._stdout.write(data)
        self._file.write(data)
        return len(data)

    def flush(self) -> None:
        self._stdout.flush()
        self._file.flush()

    def close(self) -> None:
        sys.stdout = self._stdout
        self._file.close()


# ── COCO 17 keypoint schema ───────────────────────────────────────────────────
KEYPOINT_NAMES: list[str] = [
    "nose",           # 0
    "left_eye",       # 1
    "right_eye",      # 2
    "left_ear",       # 3
    "right_ear",      # 4
    "left_shoulder",  # 5
    "right_shoulder", # 6
    "left_elbow",     # 7
    "right_elbow",    # 8
    "left_wrist",     # 9
    "right_wrist",    # 10
    "left_hip",       # 11
    "right_hip",      # 12
    "left_knee",      # 13
    "right_knee",     # 14
    "left_ankle",     # 15
    "right_ankle",    # 16
]

SKELETON_EDGES: list[tuple[int, int]] = [
    (0, 1), (0, 2), (1, 3), (2, 4),        # head
    (5, 6),                                  # shoulders
    (5, 7), (7, 9),                          # left arm
    (6, 8), (8, 10),                         # right arm
    (5, 11), (6, 12), (11, 12),             # torso
    (11, 13), (13, 15),                      # left leg
    (12, 14), (14, 16),                      # right leg
]

# MediaPipe 33 landmark index that corresponds to each COCO-17 keypoint
_MP_TO_COCO: list[int] = [
    0,   # nose
    2,   # left_eye
    5,   # right_eye
    7,   # left_ear
    8,   # right_ear
    11,  # left_shoulder
    12,  # right_shoulder
    13,  # left_elbow
    14,  # right_elbow
    15,  # left_wrist
    16,  # right_wrist
    23,  # left_hip
    24,  # right_hip
    25,  # left_knee
    26,  # right_knee
    27,  # left_ankle
    28,  # right_ankle
]

SCORE_THRESHOLD = 0.3
QUALITY_PCK_THRESHOLDS = (0.02, 0.05, 0.10)

# BGR display colours per model
_MODEL_COLORS: dict[str, tuple[int, int, int]] = {
    "movenet_lightning": (0,   255, 170),   # mint
    "movenet_thunder":   (30,  200, 255),   # amber
    "mediapipe_lite":    (200, 100, 255),   # violet
    "mediapipe_full":    (50,  180, 255),   # sky-blue
    "mediapipe_heavy":   (80,  220, 80),    # green
}

# MoveNet Thunder int8 – auto-downloaded when missing
_THUNDER_URL = (
    "https://tfhub.dev/google/lite-model/"
    "movenet/singlepose/thunder/tflite/int8/4?lite-format=tflite"
)

# KeypointArray: float32 ndarray shape (17, 3), columns = [y_norm, x_norm, score]
KeypointArray = np.ndarray


# ── Model runners ─────────────────────────────────────────────────────────────

class MoveNetRunner:
    """TFLite MoveNet runner (Lightning or Thunder)."""

    def __init__(self, model_key: str, model_path: Path, num_threads: int = 4) -> None:
        self.name = model_key
        self._interp: Any = None

        if not model_path.is_file():
            print(f"  [SKIP] {model_key}: model not found at {model_path}")
            return

        interp = _load_tflite(model_path, num_threads)
        if interp is None:
            return

        interp.allocate_tensors()
        inp = interp.get_input_details()[0]
        out = interp.get_output_details()[0]

        self._interp          = interp
        self._input_index     = int(inp["index"])
        self._output_index    = int(out["index"])
        self._input_size      = int(inp["shape"][1])          # square H == W
        self._input_dtype     = inp["dtype"]
        self._in_scale, self._in_zp   = inp["quantization"]
        self._out_scale, self._out_zp = out["quantization"]
        self._out_is_float    = bool(np.issubdtype(out["dtype"], np.floating))

        print(f"  [OK]   {model_key}: input {inp['shape'].tolist()} {inp['dtype'].__name__}")

    @property
    def available(self) -> bool:
        return self._interp is not None

    def run(self, frame_bgr: np.ndarray) -> tuple[KeypointArray | None, float]:
        if not self.available:
            return None, 0.0

        # Preprocess: resize → RGB → quantize
        rgb = cv2.cvtColor(
            cv2.resize(frame_bgr, (self._input_size, self._input_size),
                       interpolation=cv2.INTER_AREA),
            cv2.COLOR_BGR2RGB,
        ).astype(np.float32)

        if np.issubdtype(self._input_dtype, np.floating):
            rgb /= 255.0
            tensor = np.expand_dims(rgb.astype(self._input_dtype), 0)
        elif self._in_scale != 0.0:
            info = np.iinfo(self._input_dtype)
            q = np.clip(np.round(rgb / self._in_scale + self._in_zp),
                        info.min, info.max).astype(self._input_dtype)
            tensor = np.expand_dims(q, 0)
        else:
            tensor = np.expand_dims(rgb.astype(self._input_dtype), 0)

        self._interp.set_tensor(self._input_index, tensor)
        t0 = time.perf_counter()
        self._interp.invoke()
        ms = (time.perf_counter() - t0) * 1000.0

        raw = self._interp.get_tensor(self._output_index).squeeze()
        if raw.shape != (17, 3):
            raw = raw.reshape(17, 3)

        kp: KeypointArray
        if self._out_is_float:
            kp = raw.astype(np.float32)
        elif self._out_scale != 0.0:
            kp = (raw.astype(np.float32) - self._out_zp) * self._out_scale
        else:
            kp = raw.astype(np.float32)

        return kp, ms

    def close(self) -> None:
        self._interp = None


class MediaPipeRunner:
    """MediaPipe Pose runner, outputs remapped COCO-17 keypoints."""

    def __init__(self, model_key: str, model_complexity: int) -> None:
        self.name = model_key
        self._pose: Any = None

        try:
            import mediapipe as mp
            if not hasattr(mp, "solutions"):
                raise AttributeError("mediapipe.solutions is not available")
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=model_complexity,
                smooth_landmarks=True,
                enable_segmentation=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            print(f"  [OK]   {model_key}: MediaPipe model_complexity={model_complexity}")
        except ImportError:
            print(f"  [SKIP] {model_key}: mediapipe not installed  "
                  "(pip install mediapipe)")
        except AttributeError as exc:
            print(f"  [SKIP] {model_key}: unsupported mediapipe API ({exc})")

    @property
    def available(self) -> bool:
        return self._pose is not None

    def run(self, frame_bgr: np.ndarray) -> tuple[KeypointArray | None, float]:
        if not self.available:
            return None, 0.0

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        t0 = time.perf_counter()
        result = self._pose.process(rgb)
        ms = (time.perf_counter() - t0) * 1000.0

        if not result.pose_landmarks:
            return None, ms

        lms = result.pose_landmarks.landmark
        kp = np.zeros((17, 3), dtype=np.float32)
        for coco_i, mp_i in enumerate(_MP_TO_COCO):
            lm = lms[mp_i]
            kp[coco_i] = [lm.y, lm.x, lm.visibility]

        return kp, ms

    def close(self) -> None:
        if self._pose is not None:
            self._pose.close()
            self._pose = None


# ── Drawing helpers ───────────────────────────────────────────────────────────

def draw_skeleton(
    frame: np.ndarray,
    kp: KeypointArray,
    color: tuple[int, int, int],
    threshold: float = SCORE_THRESHOLD,
) -> None:
    h, w = frame.shape[:2]
    pts   = [(int(kp[i, 1] * w), int(kp[i, 0] * h)) for i in range(17)]
    scores = [float(kp[i, 2]) for i in range(17)]

    for a, b in SKELETON_EDGES:
        if scores[a] >= threshold and scores[b] >= threshold:
            cv2.line(frame, pts[a], pts[b], color, 2, cv2.LINE_AA)

    for i, (px, py) in enumerate(pts):
        if scores[i] >= threshold:
            cv2.circle(frame, (px, py), 5, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, (px, py), 5, color, 1, cv2.LINE_AA)


def draw_hud(
    frame: np.ndarray,
    model_name: str,
    cur_ms: float,
    avg_ms: float,
    frame_idx: int,
    total_frames: int,
    color: tuple[int, int, int],
) -> None:
    h, w = frame.shape[:2]

    # Top bar
    cv2.rectangle(frame, (0, 0), (w, 52), (15, 15, 15), -1)
    cv2.putText(frame, model_name, (12, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)
    stats = f"cur {cur_ms:.1f}ms   avg {avg_ms:.1f}ms  (~{1000/avg_ms:.0f}fps)" if avg_ms > 0 else ""
    cv2.putText(frame, stats, (w - 370, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 200, 200), 1, cv2.LINE_AA)

    # Progress bar
    bar_w = int(w * frame_idx / max(total_frames - 1, 1))
    cv2.rectangle(frame, (0, 49), (w, 52),     (50,  50,  50),  -1)
    cv2.rectangle(frame, (0, 49), (bar_w, 52), color, -1)


# ── Per-model video processing ────────────────────────────────────────────────

def _new_quality_acc() -> dict[str, Any]:
    return {
        "frames_with_teacher": 0,
        "teacher_visible_keypoints": 0,
        "matched_keypoints": 0,
        "sum_px_error": 0.0,
        "sum_norm_error": 0.0,
        "pck_hits": {thr: 0 for thr in QUALITY_PCK_THRESHOLDS},
    }


def _update_quality_acc(
    acc: dict[str, Any],
    pred_kp: KeypointArray | None,
    teacher_kp: KeypointArray | None,
    frame_shape: tuple[int, int, int],
) -> None:
    if teacher_kp is None:
        return

    teacher_visible = teacher_kp[:, 2] >= SCORE_THRESHOLD
    teacher_count = int(np.count_nonzero(teacher_visible))
    if teacher_count == 0:
        return

    acc["frames_with_teacher"] += 1
    acc["teacher_visible_keypoints"] += teacher_count

    if pred_kp is None:
        return

    pred_visible = pred_kp[:, 2] >= SCORE_THRESHOLD
    matched = teacher_visible & pred_visible
    matched_count = int(np.count_nonzero(matched))
    if matched_count == 0:
        return

    h, w = frame_shape[:2]
    scale = float(np.hypot(w, h))
    image_scale = np.array([w, h], dtype=np.float32)
    teacher_xy = teacher_kp[matched][:, [1, 0]] * image_scale
    pred_xy = pred_kp[matched][:, [1, 0]] * image_scale
    errors = np.linalg.norm(pred_xy - teacher_xy, axis=1)
    norm_errors = errors / scale if scale > 0 else errors

    acc["matched_keypoints"] += matched_count
    acc["sum_px_error"] += float(np.sum(errors))
    acc["sum_norm_error"] += float(np.sum(norm_errors))
    for thr in QUALITY_PCK_THRESHOLDS:
        acc["pck_hits"][thr] += int(np.count_nonzero(norm_errors <= thr))


def _finalize_quality(acc: dict[str, Any]) -> dict[str, float | int]:
    teacher_count = int(acc["teacher_visible_keypoints"])
    matched_count = int(acc["matched_keypoints"])
    quality: dict[str, float | int] = {
        "teacher_frames": int(acc["frames_with_teacher"]),
        "teacher_keypoints": teacher_count,
        "matched_keypoints": matched_count,
        "detect_rate": matched_count / teacher_count if teacher_count else 0.0,
        "mean_px_error": acc["sum_px_error"] / matched_count if matched_count else 0.0,
        "mean_norm_error": acc["sum_norm_error"] / matched_count if matched_count else 0.0,
    }
    for thr in QUALITY_PCK_THRESHOLDS:
        quality[f"pck@{int(thr * 100)}"] = (
            acc["pck_hits"][thr] / teacher_count if teacher_count else 0.0
        )
    return quality


def process_video(
    runner: MoveNetRunner | MediaPipeRunner,
    video_path: Path,
    output_dir: Path,
    teacher_keypoints: list[KeypointArray | None] | None = None,
    collect_keypoints: bool = False,
) -> dict[str, Any]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    fps   = cap.get(cv2.CAP_PROP_FPS) or 25.0
    fw    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh    = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    color = _MODEL_COLORS.get(runner.name, (0, 255, 0))

    times:  list[float]      = []
    frames: list[np.ndarray] = []
    collected_keypoints: list[KeypointArray | None] = []
    quality_acc = _new_quality_acc() if teacher_keypoints is not None else None

    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        kp, ms = runner.run(frame)
        times.append(ms)
        if collect_keypoints:
            collected_keypoints.append(kp.copy() if kp is not None else None)
        if quality_acc is not None:
            teacher_kp = teacher_keypoints[idx] if idx < len(teacher_keypoints) else None
            _update_quality_acc(quality_acc, kp, teacher_kp, frame.shape)
        avg = sum(times) / len(times)

        if kp is not None:
            draw_skeleton(frame, kp, color)
        draw_hud(frame, runner.name, ms, avg, idx, total, color)
        frames.append(frame)
        idx += 1

        if idx % 30 == 0 or idx == total:
            print(f"    {runner.name}  {idx:>5}/{total}  avg {avg:.1f}ms", end="\r")

    cap.release()

    avg_ms = sum(times) / len(times) if times else 0.0
    print(f"    {runner.name}  {idx:>5}/{total}  avg {avg_ms:.1f}ms  [done]        ")

    # Save annotated video
    out_name = f"{runner.name}_{avg_ms:.0f}ms.mp4"
    out_path = output_dir / out_name
    fourcc   = cv2.VideoWriter.fourcc(*"mp4v")
    writer   = cv2.VideoWriter(str(out_path), fourcc, fps, (fw, fh))
    for f in frames:
        writer.write(f)
    writer.release()
    print(f"    saved: {out_path}")

    result: dict[str, Any] = {
        "avg_ms": avg_ms,
        "fps_eq": 1000.0 / avg_ms if avg_ms > 0 else 0.0,
        "frames": idx,
    }
    if collect_keypoints:
        result["keypoints"] = collected_keypoints
    if quality_acc is not None:
        result["quality"] = _finalize_quality(quality_acc)
    return result


# ── TFLite loader + Thunder auto-download ────────────────────────────────────

def _load_tflite(model_path: Path, num_threads: int) -> Any | None:
    try:
        from tflite_runtime.interpreter import Interpreter
        return Interpreter(model_path=str(model_path), num_threads=num_threads)
    except ImportError:
        pass
    try:
        from tensorflow.lite.python.interpreter import Interpreter  # type: ignore[no-redef]
        return Interpreter(model_path=str(model_path), num_threads=num_threads)
    except ImportError:
        print("  [SKIP] tflite-runtime not installed  (pip install tflite-runtime)")
        return None


def _try_download_thunder(dest: Path) -> bool:
    print(f"  MoveNet Thunder not found. Attempting download: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(
            _THUNDER_URL, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        dest.write_bytes(data)
        print(f"  Downloaded ({len(data) // 1024} KB)")
        return True
    except Exception as exc:
        print(f"  Download failed: {exc}")
        print(f"  Manual URL: {_THUNDER_URL}")
        return False


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compare MoveNet Lightning/Thunder and MediaPipe Lite/Full on a video."
    )
    p.add_argument("--video",      required=True, type=Path,
                   help="Input video file")
    p.add_argument("--output-dir", type=Path, default=Path("scratch/output"),
                   help="Where to save output MP4s (default: scratch/output)")
    p.add_argument("--lightning",  type=Path,
                   default=Path("camera-worker/models/movenet-singlepose-lightning-tflite-int8.tflite"),
                   help="Path to MoveNet Lightning int8 .tflite")
    p.add_argument("--thunder",    type=Path,
                   default=Path("camera-worker/models/movenet-singlepose-thunder-tflite-int8.tflite"),
                   help="Path to MoveNet Thunder int8 .tflite")
    p.add_argument("--threads",    type=int, default=4,
                   help="TFLite CPU threads (default: 4)")
    p.add_argument("--no-download", action="store_true",
                   help="Skip auto-download of Thunder model")
    p.add_argument("--teacher", default="mediapipe_heavy",
                   help="Teacher model for pseudo-labels (default: mediapipe_heavy)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not args.video.is_file():
        raise FileNotFoundError(f"Video not found: {args.video}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    log_path = args.output_dir / f"benchmark_{time.strftime('%Y%m%d_%H%M%S')}.log"
    tee = _Tee(log_path)
    print(f"  log    : {log_path.resolve()}")

    print("=" * 65)
    print("  Pose Model Comparison")
    print(f"  input  : {args.video}")
    print(f"  output : {args.output_dir.resolve()}")
    print(f"  threads: {args.threads}")
    print(f"  teacher: {args.teacher}")
    print("=" * 65)

    # Try to download Thunder if missing
    if not args.thunder.is_file() and not args.no_download:
        _try_download_thunder(args.thunder)

    print("\nInitialising models...")
    runners: list[MoveNetRunner | MediaPipeRunner] = [
        MoveNetRunner("movenet_lightning", args.lightning, args.threads),
        MoveNetRunner("movenet_thunder",   args.thunder,   args.threads),
        MediaPipeRunner("mediapipe_lite",  model_complexity=0),
        MediaPipeRunner("mediapipe_full",  model_complexity=1),
    ]

    active = [r for r in runners if r.available]
    if not active:
        print("\nNo models available. Install tflite-runtime and/or mediapipe.")
        return

    active_by_name = {r.name: r for r in active}
    if args.teacher == "mediapipe_heavy":
        teacher: MoveNetRunner | MediaPipeRunner = MediaPipeRunner(
            "mediapipe_heavy", model_complexity=2
        )
    elif args.teacher in active_by_name:
        teacher = active_by_name[args.teacher]
    else:
        available = ", ".join(sorted([*active_by_name, "mediapipe_heavy"]))
        raise ValueError(f"Teacher model '{args.teacher}' is not available. Available: {available}")

    if not teacher.available:
        raise RuntimeError(f"Teacher model '{teacher.name}' is not available.")

    comparison = [r for r in active if r.name != teacher.name]
    ordered = [teacher] + comparison

    print(f"\nRunning teacher + {len(comparison)} comparison model(s) on {args.video.name}...")
    print(f"Using [{teacher.name}] as pseudo-label teacher for quality metrics.\n")

    results: dict[str, dict[str, Any]] = {}
    teacher_result: dict[str, Any] = {}
    teacher_keypoints: list[KeypointArray | None] = []
    for runner in ordered:
        print(f"[{runner.name}]")
        if runner.name == teacher.name:
            result = process_video(
                runner,
                args.video,
                args.output_dir,
                collect_keypoints=True,
            )
            teacher_keypoints = result.pop("keypoints")
            result["teacher"] = True
            teacher_result = result
            runner.close()
            continue
        else:
            result = process_video(
                runner,
                args.video,
                args.output_dir,
                teacher_keypoints=teacher_keypoints,
            )
            result["teacher"] = False
        results[runner.name] = result
        runner.close()

    print("\n" + "=" * 105)
    print(
        f"  {'Model':<25} {'Avg ms':>9} {'FPS':>8} {'Frames':>8} "
        f"{'PCK@5':>8} {'Err px':>8} {'Detect':>8}"
    )
    print("  " + "-" * 100)
    best = min(results, key=lambda k: results[k]["avg_ms"])
    for name, r in results.items():
        tags = []
        if name == best:
            tags.append("fastest")
        if r.get("teacher"):
            tags.append("teacher")
        tag = f" ({', '.join(tags)})" if tags else ""
        q = r.get("quality")
        if isinstance(q, dict):
            pck5 = f"{float(q['pck@5']) * 100:>7.1f}%"
            err_px = f"{float(q['mean_px_error']):>7.1f}"
            detect = f"{float(q['detect_rate']) * 100:>7.1f}%"
        else:
            pck5 = f"{'N/A':>8}"
            err_px = f"{'N/A':>8}"
            detect = f"{'N/A':>8}"
        print(
            f"  {name:<25} {r['avg_ms']:>8.1f}ms {r['fps_eq']:>7.1f} "
            f"{r['frames']:>8} {pck5} {err_px} {detect}{tag}"
        )
    print("=" * 105)

    json_path = args.output_dir / f"{log_path.stem}.json"
    report = {
        "benchmark": "pose_speed_quality",
        "video": str(args.video),
        "teacher": teacher.name,
        "teacher_result": teacher_result,
        "score_threshold": SCORE_THRESHOLD,
        "pck_thresholds": list(QUALITY_PCK_THRESHOLDS),
        "models": results,
    }
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nOutput videos: {args.output_dir.resolve()}/")
    print(f"JSON saved to : {json_path.resolve()}")
    print(f"Log saved to : {log_path.resolve()}")
    tee.close()
    return

    # ── Summary table ──────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f"  {'Model':<25} {'Avg ms':>9} {'Equiv FPS':>10} {'Frames':>8}")
    print("  " + "-" * 60)
    best = min(results, key=lambda k: results[k]["avg_ms"])
    for name, r in results.items():
        tag = " ◀ fastest" if name == best else ""
        print(f"  {name:<25} {r['avg_ms']:>8.1f}ms {r['fps_eq']:>9.1f}  {r['frames']:>8}{tag}")
    print("=" * 65)
    print(f"\nOutput videos: {args.output_dir.resolve()}/")
    print(f"Log saved to : {log_path.resolve()}")
    tee.close()


if __name__ == "__main__":
    main()
