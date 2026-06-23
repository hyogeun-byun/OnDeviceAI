from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


class ServerClient:
    def __init__(self, server_url: str, camera_id: str) -> None:
        self._upload_url = f"{server_url}/api/cameras/{camera_id}/frame"
        self._pose_url = f"{server_url}/api/cameras/{camera_id}/pose"
        self._session = requests.Session()

    def send_frame(self, frame_bytes: bytes) -> None:
        try:
            response = self._session.post(
                self._upload_url,
                files={"frame": ("frame.jpg", frame_bytes, "image/jpeg")},
                timeout=2.0,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Could not send frame to server: %s", exc)

    def send_pose(self, pose_result: dict[str, object]) -> None:
        try:
            response = self._session.post(
                self._pose_url,
                json=pose_result,
                timeout=2.0,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Could not send pose result to server: %s", exc)

    def close(self) -> None:
        self._session.close()
