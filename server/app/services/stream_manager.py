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


class StreamManager:
    def __init__(self, camera_ids: tuple[str, ...]) -> None:
        self._camera_ids = camera_ids
        self._frames: dict[str, CameraFrame] = {}
        self._poses: dict[str, CameraPose] = {}
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

    def list_camera_statuses(self) -> list[dict[str, object]]:
        with self._lock:
            camera_ids = list(dict.fromkeys([*self._camera_ids, *self._frames.keys(), *self._poses.keys()]))
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
