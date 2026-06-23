from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    camera_ids: tuple[str, ...]
    visualize_metrics: bool


def read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> ServerConfig:
    load_dotenv()

    camera_ids = tuple(
        camera_id.strip()
        for camera_id in os.getenv("CAMERA_IDS", "camera_01,camera_02,camera_03").split(",")
        if camera_id.strip()
    )

    return ServerConfig(
        host=os.getenv("SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("SERVER_PORT", "8000")),
        camera_ids=camera_ids,
        visualize_metrics=read_bool("VISUALIZE_METRICS", True),
    )
