from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CameraTrafficSnapshot:
    frames: int = 0
    poses: int = 0
    frame_bytes: int = 0


@dataclass
class TrafficMetrics:
    log_interval_seconds: float = 5.0
    _last_log_at: float = field(default_factory=time.perf_counter)
    _cameras: dict[str, CameraTrafficSnapshot] = field(default_factory=dict)
    _latest: dict[str, dict[str, object]] = field(default_factory=dict)

    def record_frame(self, camera_id: str, frame_bytes: int) -> None:
        camera = self._cameras.setdefault(camera_id, CameraTrafficSnapshot())
        camera.frames += 1
        camera.frame_bytes += frame_bytes
        self._maybe_log()

    def record_pose(self, camera_id: str) -> None:
        camera = self._cameras.setdefault(camera_id, CameraTrafficSnapshot())
        camera.poses += 1
        self._maybe_log()

    def _maybe_log(self) -> None:
        now = time.perf_counter()
        elapsed_seconds = now - self._last_log_at
        if elapsed_seconds < self.log_interval_seconds:
            return

        for camera_id, camera in self._cameras.items():
            frame_fps = camera.frames / elapsed_seconds if elapsed_seconds > 0 else 0.0
            pose_fps = camera.poses / elapsed_seconds if elapsed_seconds > 0 else 0.0
            kb_per_second = (camera.frame_bytes / 1024) / elapsed_seconds if elapsed_seconds > 0 else 0.0
            avg_frame_kb = (camera.frame_bytes / 1024) / camera.frames if camera.frames else 0.0
            logger.info(
                (
                    "server_metrics camera_id=%s recv_frame_fps=%.2f recv_pose_fps=%.2f "
                    "recv_kb_s=%.1f avg_frame_kb=%.1f frames=%s poses=%s"
                ),
                camera_id,
                frame_fps,
                pose_fps,
                kb_per_second,
                avg_frame_kb,
                camera.frames,
                camera.poses,
            )
            self._latest[camera_id] = {
                "recv_frame_fps": frame_fps,
                "recv_pose_fps": pose_fps,
                "recv_kb_s": kb_per_second,
                "avg_frame_kb": avg_frame_kb,
                "frames": camera.frames,
                "poses": camera.poses,
            }

        self._cameras.clear()
        self._last_log_at = now

    def get_latest(self, camera_id: str) -> dict[str, object] | None:
        return self._latest.get(camera_id)
