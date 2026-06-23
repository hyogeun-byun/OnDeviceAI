from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class CameraWorkerConfig:
    camera_id: str
    server_url: str
    camera_index: int
    frame_width: int
    frame_height: int
    jpeg_quality: int
    fps: float


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
    )
