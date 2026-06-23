from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


class ServerClient:
    def __init__(self, server_url: str, camera_id: str) -> None:
        self._upload_url = f"{server_url}/api/cameras/{camera_id}/frame"

    def send_frame(self, frame_bytes: bytes) -> None:
        try:
            response = requests.post(
                self._upload_url,
                files={"frame": ("frame.jpg", frame_bytes, "image/jpeg")},
                timeout=2.0,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Could not send frame to server: %s", exc)

