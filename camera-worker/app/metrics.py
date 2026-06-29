from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class CameraWorkerMetrics:
    camera_id: str
    log_interval_seconds: float
    metrics_log_path: str | Path | None = None

    def __post_init__(self) -> None:
        self._metrics_log_path = Path(self.metrics_log_path).expanduser() if self.metrics_log_path else None
        if self._metrics_log_path is not None:
            self._metrics_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._started_at = time.perf_counter()
        self._last_log_at = self._started_at
        self._frames = 0
        self._poses = 0
        self._sent_frames = 0
        self._failed_frames = 0
        self._sent_poses = 0
        self._failed_poses = 0
        self._frame_bytes = 0
        self._capture_ms = 0.0
        self._pose_ms = 0.0
        self._encode_ms = 0.0
        self._frame_upload_ms = 0.0
        self._pose_upload_ms = 0.0
        self._lock = Lock()

    def record_frame(
        self,
        frame_bytes: int,
        capture_ms: float,
        encode_ms: float,
        frame_upload_ms: float | None,
    ) -> None:
        with self._lock:
            self._frames += 1
            self._frame_bytes += frame_bytes
            self._capture_ms += capture_ms
            self._encode_ms += encode_ms
            if frame_upload_ms is None:
                self._failed_frames += 1
            else:
                self._sent_frames += 1
                self._frame_upload_ms += frame_upload_ms

    def record_pose(self, pose_ms: float, pose_upload_ms: float | None) -> None:
        with self._lock:
            self._poses += 1
            self._pose_ms += pose_ms
            if pose_upload_ms is None:
                self._failed_poses += 1
            else:
                self._sent_poses += 1
                self._pose_upload_ms += pose_upload_ms

    def maybe_collect(self) -> dict[str, object] | None:
        with self._lock:
            now = time.perf_counter()
            elapsed_seconds = now - self._last_log_at
            if elapsed_seconds < self.log_interval_seconds:
                return None

            frame_fps = self._frames / elapsed_seconds if elapsed_seconds > 0 else 0.0
            pose_fps = self._poses / elapsed_seconds if elapsed_seconds > 0 else 0.0
            kb_per_second = (self._frame_bytes / 1024) / elapsed_seconds if elapsed_seconds > 0 else 0.0
            avg_frame_kb = (self._frame_bytes / 1024) / self._frames if self._frames else 0.0
            payload: dict[str, object] = {
                "camera_id": self.camera_id,
                "elapsed_seconds": elapsed_seconds,
                "frame_fps": frame_fps,
                "pose_fps": pose_fps,
                "avg_capture_ms": self._avg(self._capture_ms, self._frames),
                "avg_pose_ms": self._avg(self._pose_ms, self._poses),
                "avg_encode_ms": self._avg(self._encode_ms, self._frames),
                "avg_frame_upload_ms": self._avg(self._frame_upload_ms, self._sent_frames),
                "avg_pose_upload_ms": self._avg(self._pose_upload_ms, self._sent_poses),
                "avg_frame_kb": avg_frame_kb,
                "upload_kb_s": kb_per_second,
                "sent_frames": self._sent_frames,
                "failed_frames": self._failed_frames,
                "sent_poses": self._sent_poses,
                "failed_poses": self._failed_poses,
            }

            logger.info(
                (
                    "metrics camera_id=%s frame_fps=%.2f pose_fps=%.2f "
                    "avg_capture_ms=%.1f avg_pose_ms=%.1f avg_encode_ms=%.1f "
                    "avg_frame_upload_ms=%.1f avg_pose_upload_ms=%.1f "
                    "avg_frame_kb=%.1f upload_kb_s=%.1f "
                    "sent_frames=%s failed_frames=%s sent_poses=%s failed_poses=%s"
                ),
                payload["camera_id"],
                payload["frame_fps"],
                payload["pose_fps"],
                payload["avg_capture_ms"],
                payload["avg_pose_ms"],
                payload["avg_encode_ms"],
                payload["avg_frame_upload_ms"],
                payload["avg_pose_upload_ms"],
                payload["avg_frame_kb"],
                payload["upload_kb_s"],
                payload["sent_frames"],
                payload["failed_frames"],
                payload["sent_poses"],
                payload["failed_poses"],
            )
            self._write_metrics_payload(payload)
            self._reset(now)
            return payload

    def _write_metrics_payload(self, payload: dict[str, object]) -> None:
        if self._metrics_log_path is None:
            return

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **payload,
        }
        try:
            with self._metrics_log_path.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            logger.warning("failed to write metrics log path=%s", self._metrics_log_path, exc_info=True)

    def _reset(self, now: float) -> None:
        self._last_log_at = now
        self._frames = 0
        self._poses = 0
        self._sent_frames = 0
        self._failed_frames = 0
        self._sent_poses = 0
        self._failed_poses = 0
        self._frame_bytes = 0
        self._capture_ms = 0.0
        self._pose_ms = 0.0
        self._encode_ms = 0.0
        self._frame_upload_ms = 0.0
        self._pose_upload_ms = 0.0

    @staticmethod
    def _avg(total: float, count: int) -> float:
        return total / count if count else 0.0
