from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from threading import Lock

import websocket

logger = logging.getLogger(__name__)


class WebSocketCameraClient:
    def __init__(self, server_url: str, camera_id: str) -> None:
        self._ws_url = self._build_ws_url(server_url=server_url, camera_id=camera_id)
        self._socket: websocket.WebSocket | None = None
        self._lock = Lock()

    def send_frame(self, frame_bytes: bytes) -> float | None:
        return self._send(lambda socket: socket.send_binary(frame_bytes))

    def send_pose(self, pose_result: dict[str, object]) -> float | None:
        return self._send_json({"type": "pose", "payload": pose_result})

    def send_metrics(self, metrics: dict[str, object]) -> float | None:
        return self._send_json({"type": "metrics", "payload": metrics})

    def close(self) -> None:
        with self._lock:
            self._close_socket()

    def _send_json(self, payload: dict[str, object]) -> float | None:
        return self._send(lambda socket: socket.send(json.dumps(payload)))

    def _send(self, send_callback: Callable[[websocket.WebSocket], object]) -> float | None:
        started_at = time.perf_counter()
        with self._lock:
            try:
                socket = self._connect()
                send_callback(socket)
                return (time.perf_counter() - started_at) * 1000
            except Exception as exc:
                logger.warning("Could not send websocket message: %s", exc)
                self._close_socket()
                return None

    def _connect(self) -> websocket.WebSocket:
        if self._socket is not None and self._socket.connected:
            return self._socket

        logger.info("Connecting camera websocket: %s", self._ws_url)
        self._socket = websocket.create_connection(self._ws_url, timeout=3.0)
        return self._socket

    def _close_socket(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None

    @staticmethod
    def _build_ws_url(server_url: str, camera_id: str) -> str:
        if server_url.startswith("https://"):
            base_url = "wss://" + server_url.removeprefix("https://")
        elif server_url.startswith("http://"):
            base_url = "ws://" + server_url.removeprefix("http://")
        else:
            base_url = server_url
        return f"{base_url.rstrip('/')}/api/cameras/{camera_id}/ws"
