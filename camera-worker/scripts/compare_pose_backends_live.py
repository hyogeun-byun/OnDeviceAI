from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np


MOVENET_KEYPOINT_NAMES = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]

COCO_EDGES = [
    ("nose", "left_eye"),
    ("nose", "right_eye"),
    ("left_eye", "left_ear"),
    ("right_eye", "right_ear"),
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
]


def load_tflite_interpreter(model_path: Path, num_threads: int) -> Any:
    try:
        from tflite_runtime.interpreter import Interpreter
    except ImportError:
        try:
            from tensorflow.lite.python.interpreter import Interpreter
        except ImportError as error:
            raise RuntimeError("Install either tflite-runtime or tensorflow.") from error

    interpreter = Interpreter(model_path=str(model_path), num_threads=num_threads)
    interpreter.allocate_tensors()
    return interpreter


def quantize_input(image: np.ndarray, input_details: dict[str, Any]) -> np.ndarray:
    dtype = input_details["dtype"]
    if np.issubdtype(dtype, np.floating):
        return image.astype(dtype)

    scale, zero_point = input_details["quantization"]
    if scale == 0:
        return image.astype(dtype)

    quantized = (image / scale) + zero_point
    info = np.iinfo(dtype)
    return np.clip(np.round(quantized), info.min, info.max).astype(dtype)


def dequantize_output(output: np.ndarray, output_details: dict[str, Any]) -> np.ndarray:
    if np.issubdtype(output.dtype, np.floating):
        return output.astype(np.float32)

    scale, zero_point = output_details["quantization"]
    if scale == 0:
        return output.astype(np.float32)
    return (output.astype(np.float32) - zero_point) * scale


def preprocess_movenet_frame(frame_bgr: cv2.typing.MatLike, input_details: dict[str, Any]) -> np.ndarray:
    _, input_height, input_width, channels = input_details["shape"]
    if channels != 3:
        raise ValueError(f"Expected MoveNet input with 3 channels, got {channels}")

    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(frame_rgb, (input_width, input_height), interpolation=cv2.INTER_LINEAR)
    image = resized.astype(np.float32)

    if np.issubdtype(input_details["dtype"], np.floating):
        image /= 255.0

    return np.expand_dims(quantize_input(image, input_details), axis=0)


def run_movenet(
    interpreter: Any,
    input_details: dict[str, Any],
    output_details: dict[str, Any],
    frame_bgr: cv2.typing.MatLike,
) -> tuple[list[dict[str, float | str]], float]:
    input_tensor = preprocess_movenet_frame(frame_bgr, input_details)
    interpreter.set_tensor(input_details["index"], input_tensor)

    started_at = time.perf_counter()
    interpreter.invoke()
    inference_ms = (time.perf_counter() - started_at) * 1000

    raw_output = interpreter.get_tensor(output_details["index"])
    output = dequantize_output(raw_output, output_details)
    keypoints = np.squeeze(output)
    if keypoints.shape != (17, 3):
        keypoints = keypoints.reshape(17, 3)

    return [
        {
            "name": name,
            "x": float(x),
            "y": float(y),
            "score": float(score),
        }
        for name, (y, x, score) in zip(MOVENET_KEYPOINT_NAMES, keypoints)
    ], inference_ms


def resize_for_mediapipe(frame_bgr: cv2.typing.MatLike, input_width: int) -> cv2.typing.MatLike:
    frame_height, frame_width = frame_bgr.shape[:2]
    if frame_width <= input_width:
        return frame_bgr

    scale = input_width / frame_width
    input_height = max(1, int(frame_height * scale))
    return cv2.resize(frame_bgr, (input_width, input_height), interpolation=cv2.INTER_AREA)


def run_mediapipe(
    pose: Any,
    mp_pose: Any,
    frame_bgr: cv2.typing.MatLike,
    input_width: int,
) -> tuple[list[dict[str, float | str]], float]:
    resized_frame = resize_for_mediapipe(frame_bgr, input_width)
    rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
    rgb_frame.flags.writeable = False

    started_at = time.perf_counter()
    result = pose.process(rgb_frame)
    inference_ms = (time.perf_counter() - started_at) * 1000

    if not result.pose_landmarks:
        return [], inference_ms

    keypoints: list[dict[str, float | str]] = []
    for index, landmark in enumerate(result.pose_landmarks.landmark):
        keypoints.append(
            {
                "name": mp_pose.PoseLandmark(index).name.lower(),
                "x": float(landmark.x),
                "y": float(landmark.y),
                "score": float(landmark.visibility),
            }
        )
    return keypoints, inference_ms


def draw_pose(
    frame: cv2.typing.MatLike,
    keypoints: list[dict[str, float | str]],
    edges: list[tuple[str, str]],
    color: tuple[int, int, int],
    min_score: float,
    x_offset: int = 0,
) -> int:
    frame_height, frame_width = frame.shape[:2]
    point_map: dict[str, tuple[int, int]] = {}

    for keypoint in keypoints:
        score = float(keypoint["score"])
        if score < min_score:
            continue
        x = int(float(keypoint["x"]) * frame_width) + x_offset
        y = int(float(keypoint["y"]) * frame_height)
        point_map[str(keypoint["name"])] = (x, y)

    for start_name, end_name in edges:
        start = point_map.get(start_name)
        end = point_map.get(end_name)
        if start is not None and end is not None:
            cv2.line(frame, start, end, color, 2)

    for point in point_map.values():
        cv2.circle(frame, point, 4, color, -1)

    return len(point_map)


def put_label(
    frame: cv2.typing.MatLike,
    text: str,
    origin: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    cv2.putText(
        frame,
        text,
        origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 0, 0),
        4,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        text,
        origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        color,
        2,
        cv2.LINE_AA,
    )


def run_live_comparison(args: argparse.Namespace) -> None:
    import mediapipe as mp

    movenet = load_tflite_interpreter(args.movenet_model, args.num_threads)
    movenet_input = movenet.get_input_details()[0]
    movenet_output = movenet.get_output_details()[0]

    mp_pose = mp.solutions.pose
    mediapipe_pose = mp_pose.Pose(
        static_image_mode=False,
        model_complexity=args.mediapipe_model_complexity,
        smooth_landmarks=True,
        enable_segmentation=False,
        min_detection_confidence=args.mediapipe_min_detection_confidence,
        min_tracking_confidence=args.mediapipe_min_tracking_confidence,
    )

    capture = cv2.VideoCapture(args.camera_index)
    if not capture.isOpened():
        raise RuntimeError(f"Could not open camera index {args.camera_index}")

    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.frame_width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.frame_height)

    movenet_times: list[float] = []
    mediapipe_times: list[float] = []
    fps = 0.0
    frame_count = 0
    fps_started_at = time.perf_counter()

    print("Live comparison started. Press 'q' or ESC to quit.")
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("Could not read frame from camera")

            mediapipe_keypoints, mediapipe_ms = run_mediapipe(
                pose=mediapipe_pose,
                mp_pose=mp_pose,
                frame_bgr=frame,
                input_width=args.mediapipe_input_width,
            )
            movenet_keypoints, movenet_ms = run_movenet(
                interpreter=movenet,
                input_details=movenet_input,
                output_details=movenet_output,
                frame_bgr=frame,
            )

            mediapipe_times.append(mediapipe_ms)
            movenet_times.append(movenet_ms)
            if len(mediapipe_times) > args.avg_window:
                mediapipe_times.pop(0)
            if len(movenet_times) > args.avg_window:
                movenet_times.pop(0)

            mediapipe_count = draw_pose(
                frame=frame,
                keypoints=mediapipe_keypoints,
                edges=COCO_EDGES,
                color=(0, 255, 0),
                min_score=args.min_score,
            )
            movenet_count = draw_pose(
                frame=frame,
                keypoints=movenet_keypoints,
                edges=COCO_EDGES,
                color=(255, 0, 255),
                min_score=args.min_score,
            )

            frame_count += 1
            elapsed_seconds = time.perf_counter() - fps_started_at
            if elapsed_seconds >= 1.0:
                fps = frame_count / elapsed_seconds
                frame_count = 0
                fps_started_at = time.perf_counter()

            mediapipe_avg = sum(mediapipe_times) / len(mediapipe_times)
            movenet_avg = sum(movenet_times) / len(movenet_times)
            faster = "MoveNet" if movenet_avg < mediapipe_avg else "MediaPipe"

            put_label(frame, f"MediaPipe green: {mediapipe_ms:.1f} ms avg {mediapipe_avg:.1f} ms kp {mediapipe_count}", (12, 28), (0, 255, 0))
            put_label(frame, f"MoveNet INT8 magenta: {movenet_ms:.1f} ms avg {movenet_avg:.1f} ms kp {movenet_count}", (12, 58), (255, 0, 255))
            put_label(frame, f"Display FPS: {fps:.1f} | Faster avg: {faster}", (12, 88), (0, 255, 255))

            cv2.imshow("MediaPipe vs MoveNet INT8 live benchmark", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in {27, ord("q")}:
                break
    finally:
        mediapipe_pose.close()
        capture.release()
        cv2.destroyAllWindows()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare MediaPipe Pose and MoveNet INT8 on a live camera.")
    parser.add_argument("--movenet-model", required=True, type=Path, help="Path to MoveNet INT8 .tflite model.")
    parser.add_argument("--camera-index", default=0, type=int)
    parser.add_argument("--frame-width", default=640, type=int)
    parser.add_argument("--frame-height", default=480, type=int)
    parser.add_argument("--num-threads", default=2, type=int, help="TFLite interpreter thread count.")
    parser.add_argument("--min-score", default=0.3, type=float, help="Minimum keypoint score to draw.")
    parser.add_argument("--avg-window", default=30, type=int, help="Number of recent frames used for avg ms.")
    parser.add_argument("--mediapipe-input-width", default=256, type=int)
    parser.add_argument("--mediapipe-model-complexity", default=0, type=int)
    parser.add_argument("--mediapipe-min-detection-confidence", default=0.5, type=float)
    parser.add_argument("--mediapipe-min-tracking-confidence", default=0.5, type=float)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.avg_window <= 0:
        raise ValueError("--avg-window must be greater than 0")
    run_live_comparison(args)


if __name__ == "__main__":
    main()
