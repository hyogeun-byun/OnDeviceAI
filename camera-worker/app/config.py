from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_DEFAULT_MODEL_PATH = str(
    Path(__file__).resolve().parents[1] / "models" / "movenet-singlepose-lightning-tflite-int8.tflite"
)


@dataclass(frozen=True)
class CameraWorkerConfig:
    camera_id: str
    server_url: str
    camera_index: int
    frame_width: int
    frame_height: int
    jpeg_quality: int
    fps: float
    log_interval_seconds: float
    pose_enabled: bool
    pose_model_path: str
    pose_num_threads: int
    pose_draw_landmarks: bool


def read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> CameraWorkerConfig:
    load_dotenv()

    return CameraWorkerConfig(
        camera_id=os.getenv("CAMERA_ID", "camera_01"),
        server_url=os.getenv("SERVER_URL", "http://127.0.0.1:8000").rstrip("/"),
        camera_index=int(os.getenv("CAMERA_INDEX", "0")),
        frame_width=int(os.getenv("FRAME_WIDTH", "640")),
        frame_height=int(os.getenv("FRAME_HEIGHT", "480")),
        jpeg_quality=int(os.getenv("JPEG_QUALITY", "80")),
        fps=float(os.getenv("FPS", "10")),
        log_interval_seconds=max(1.0, float(os.getenv("LOG_INTERVAL_SECONDS", "5"))),
        pose_enabled=read_bool("POSE_ENABLED", True),
        pose_model_path=os.getenv("POSE_MODEL_PATH", _DEFAULT_MODEL_PATH),
        pose_num_threads=int(os.getenv("POSE_NUM_THREADS", "4")),
        pose_draw_landmarks=read_bool("POSE_DRAW_LANDMARKS", True),
    )
