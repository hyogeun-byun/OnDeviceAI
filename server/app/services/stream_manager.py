from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock


@dataclass(frozen=True)
class CameraFrame:
    frame_bytes: bytes
    updated_at: datetime
    version: int


@dataclass(frozen=True)
class CameraPose:
    pose_result: dict[str, object]
    updated_at: datetime
    version: int


@dataclass(frozen=True)
class CameraWorkerMetrics:
    metrics: dict[str, object]
    updated_at: datetime
    version: int


@dataclass(frozen=True)
class CameraCapture:
    capture_id: int
    camera_id: str
    frame_bytes: bytes
    pose_result: dict[str, object] | None
    captured_at: datetime


class StreamManager:
    def __init__(self, camera_ids: tuple[str, ...]) -> None:
        self._camera_ids = camera_ids
        self._frames: dict[str, CameraFrame] = {}
        self._poses: dict[str, CameraPose] = {}
        self._worker_metrics: dict[str, CameraWorkerMetrics] = {}
        self._captures: dict[int, dict[str, CameraCapture]] = {}
        self._capture_id = 0
        self._lock = Lock()

    def update_frame(self, camera_id: str, frame_bytes: bytes) -> None:
        with self._lock:
            current_version = self._frames.get(camera_id).version if camera_id in self._frames else 0
            self._frames[camera_id] = CameraFrame(
                frame_bytes=frame_bytes,
                updated_at=datetime.now(timezone.utc),
                version=current_version + 1,
            )

    def update_pose(self, camera_id: str, pose_result: dict[str, object]) -> None:
        with self._lock:
            current_version = self._poses.get(camera_id).version if camera_id in self._poses else 0
            self._poses[camera_id] = CameraPose(
                pose_result=pose_result,
                updated_at=datetime.now(timezone.utc),
                version=current_version + 1,
            )

    def update_worker_metrics(self, camera_id: str, metrics: dict[str, object]) -> None:
        with self._lock:
            current_version = (
                self._worker_metrics.get(camera_id).version if camera_id in self._worker_metrics else 0
            )
            self._worker_metrics[camera_id] = CameraWorkerMetrics(
                metrics=metrics,
                updated_at=datetime.now(timezone.utc),
                version=current_version + 1,
            )

    def get_frame(self, camera_id: str) -> bytes | None:
        with self._lock:
            frame = self._frames.get(camera_id)
            return frame.frame_bytes if frame else None

    def get_frame_with_version(self, camera_id: str) -> tuple[int, bytes] | None:
        with self._lock:
            frame = self._frames.get(camera_id)
            if frame is None:
                return None
            return frame.version, frame.frame_bytes

    def get_pose(self, camera_id: str) -> dict[str, object] | None:
        with self._lock:
            pose = self._poses.get(camera_id)
            if pose is None:
                return None
            return {
                **pose.pose_result,
                "updated_at": pose.updated_at.isoformat(),
                "version": pose.version,
            }

    def get_worker_metrics(self, camera_id: str) -> dict[str, object] | None:
        with self._lock:
            metrics = self._worker_metrics.get(camera_id)
            if metrics is None:
                return None
            return {
                **metrics.metrics,
                "updated_at": metrics.updated_at.isoformat(),
                "version": metrics.version,
            }

    def create_capture_set(self) -> tuple[int, list[dict[str, object]]]:
        with self._lock:
            self._capture_id += 1
            capture_id = self._capture_id
            captured_at = datetime.now(timezone.utc)
            captures: dict[str, CameraCapture] = {}

            for camera_id in self._camera_ids:
                frame = self._frames.get(camera_id)
                if frame is None:
                    continue

                pose = self._poses.get(camera_id)
                captures[camera_id] = CameraCapture(
                    capture_id=capture_id,
                    camera_id=camera_id,
                    frame_bytes=frame.frame_bytes,
                    pose_result=pose.pose_result if pose is not None else None,
                    captured_at=captured_at,
                )

            self._captures[capture_id] = captures
            return capture_id, [
                self._capture_to_dict(capture)
                for capture in captures.values()
            ]

    def get_capture_image(self, capture_id: int, camera_id: str) -> bytes | None:
        with self._lock:
            capture = self._captures.get(capture_id, {}).get(camera_id)
            return capture.frame_bytes if capture is not None else None

    def list_camera_statuses(self) -> list[dict[str, object]]:
        with self._lock:
            camera_ids = list(
                dict.fromkeys(
                    [
                        *self._camera_ids,
                        *self._frames.keys(),
                        *self._poses.keys(),
                        *self._worker_metrics.keys(),
                    ]
                )
            )
            return [
                {
                    "camera_id": camera_id,
                    "online": camera_id in self._frames,
                    "updated_at": self._frames[camera_id].updated_at.isoformat()
                    if camera_id in self._frames
                    else None,
                    "pose_online": camera_id in self._poses,
                    "pose_updated_at": self._poses[camera_id].updated_at.isoformat()
                    if camera_id in self._poses
                    else None,
                    "person_detected": self._poses[camera_id].pose_result.get("person_detected")
                    if camera_id in self._poses
                    else False,
                    "keypoint_count": len(self._poses[camera_id].pose_result.get("keypoints", []))
                    if camera_id in self._poses
                    else 0,
                }
                for camera_id in camera_ids
            ]

    @staticmethod
    def _capture_to_dict(capture: CameraCapture) -> dict[str, object]:
        return {
            "capture_id": capture.capture_id,
            "camera_id": capture.camera_id,
            "captured_at": capture.captured_at.isoformat(),
            "image_url": f"/api/cameras/{capture.camera_id}/captures/{capture.capture_id}/image",
            "pose": capture.pose_result,
            "person_detected": capture.pose_result.get("person_detected")
            if capture.pose_result is not None
            else False,
            "keypoint_count": len(capture.pose_result.get("keypoints", []))
            if capture.pose_result is not None
            else 0,
        }
