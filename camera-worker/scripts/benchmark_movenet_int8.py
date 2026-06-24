from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np


KEYPOINT_NAMES = [
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


def load_interpreter(model_path: Path, num_threads: int) -> Any:
    try:
        from tflite_runtime.interpreter import Interpreter
    except ImportError:
        try:
            from tensorflow.lite.python.interpreter import Interpreter
        except ImportError as error:
            raise RuntimeError(
                "Install either tflite-runtime or tensorflow to run this script."
            ) from error

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


def preprocess_image(image_path: Path, input_details: dict[str, Any]) -> np.ndarray:
    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    _, input_height, input_width, channels = input_details["shape"]
    if channels != 3:
        raise ValueError(f"Expected 3 input channels, got {channels}")

    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(image_rgb, (input_width, input_height), interpolation=cv2.INTER_LINEAR)
    normalized = resized.astype(np.float32)

    if np.issubdtype(input_details["dtype"], np.floating):
        normalized /= 255.0

    return np.expand_dims(quantize_input(normalized, input_details), axis=0)


def parse_keypoints(raw_output: np.ndarray, output_details: dict[str, Any]) -> list[dict[str, float | str]]:
    output = dequantize_output(raw_output, output_details)
    keypoints = np.squeeze(output)

    if keypoints.shape != (17, 3):
        keypoints = keypoints.reshape(17, 3)

    parsed: list[dict[str, float | str]] = []
    for name, (y, x, score) in zip(KEYPOINT_NAMES, keypoints):
        parsed.append(
            {
                "name": name,
                "x": float(x),
                "y": float(y),
                "score": float(score),
                "visibility": float(score),
            }
        )
    return parsed


def run_benchmark(
    model_path: Path,
    image_path: Path,
    warmup_runs: int,
    runs: int,
    num_threads: int,
) -> dict[str, object]:
    interpreter = load_interpreter(model_path=model_path, num_threads=num_threads)
    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]
    input_tensor = preprocess_image(image_path=image_path, input_details=input_details)

    interpreter.set_tensor(input_details["index"], input_tensor)
    for _ in range(warmup_runs):
        interpreter.invoke()

    inference_times_ms: list[float] = []
    for _ in range(runs):
        interpreter.set_tensor(input_details["index"], input_tensor)
        started_at = time.perf_counter()
        interpreter.invoke()
        inference_times_ms.append((time.perf_counter() - started_at) * 1000)

    raw_output = interpreter.get_tensor(output_details["index"])
    keypoints = parse_keypoints(raw_output=raw_output, output_details=output_details)
    detected_keypoints = [keypoint for keypoint in keypoints if float(keypoint["score"]) >= 0.3]

    return {
        "model_path": str(model_path),
        "image_path": str(image_path),
        "input_shape": input_details["shape"].tolist(),
        "input_dtype": str(input_details["dtype"]),
        "input_quantization": input_details["quantization"],
        "output_shape": output_details["shape"].tolist(),
        "output_dtype": str(output_details["dtype"]),
        "output_quantization": output_details["quantization"],
        "warmup_runs": warmup_runs,
        "runs": runs,
        "num_threads": num_threads,
        "avg_inference_ms": sum(inference_times_ms) / len(inference_times_ms),
        "min_inference_ms": min(inference_times_ms),
        "max_inference_ms": max(inference_times_ms),
        "detected_keypoint_count": len(detected_keypoints),
        "keypoints": keypoints,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark MoveNet Lightning INT8 TFLite on one image.")
    parser.add_argument("--model", required=True, type=Path, help="Path to MoveNet INT8 .tflite model.")
    parser.add_argument("--image", required=True, type=Path, help="Path to input image.")
    parser.add_argument("--warmup-runs", default=5, type=int)
    parser.add_argument("--runs", default=30, type=int)
    parser.add_argument("--num-threads", default=2, type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.runs <= 0:
        raise ValueError("--runs must be greater than 0")
    if args.warmup_runs < 0:
        raise ValueError("--warmup-runs must be 0 or greater")

    result = run_benchmark(
        model_path=args.model,
        image_path=args.image,
        warmup_runs=args.warmup_runs,
        runs=args.runs,
        num_threads=args.num_threads,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
