from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)


class ServerClient:
    def __init__(self, server_url: str, camera_id: str) -> None:
        self._upload_url = f"{server_url}/api/cameras/{camera_id}/frame"
        self._pose_url = f"{server_url}/api/cameras/{camera_id}/pose"
        self._metrics_url = f"{server_url}/api/cameras/{camera_id}/metrics"
        self._session = requests.Session()

    def send_frame(self, frame_bytes: bytes) -> float | None:
        started_at = time.perf_counter()
        try:
            response = self._session.post(
                self._upload_url,
                files={"frame": ("frame.jpg", frame_bytes, "image/jpeg")},
                timeout=2.0,
            )
            response.raise_for_status()
            return (time.perf_counter() - started_at) * 1000
        except requests.RequestException as exc:
            logger.warning("Could not send frame to server: %s", exc)
            return None

    def send_pose(self, pose_result: dict[str, object]) -> float | None:
        started_at = time.perf_counter()
        try:
            response = self._session.post(
                self._pose_url,
                json=pose_result,
                timeout=2.0,
            )
            response.raise_for_status()
            return (time.perf_counter() - started_at) * 1000
        except requests.RequestException as exc:
            logger.warning("Could not send pose result to server: %s", exc)
            return None

    def send_metrics(self, metrics: dict[str, object]) -> float | None:
        started_at = time.perf_counter()
        try:
            response = self._session.post(
                self._metrics_url,
                json=metrics,
                timeout=2.0,
            )
            response.raise_for_status()
            return (time.perf_counter() - started_at) * 1000
        except requests.RequestException as exc:
            logger.warning("Could not send metrics to server: %s", exc)
            return None
