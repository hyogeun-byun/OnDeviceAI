from __future__ import annotations

import logging
import time
from typing import Any

import cv2

logger = logging.getLogger(__name__)


class PoseEstimator:
    def __init__(
        self,
        camera_id: str,
        enabled: bool,
        backend: str,
        model_complexity: int,
        input_width: int,
        min_detection_confidence: float,
        min_tracking_confidence: float,
        draw_landmarks: bool,
    ) -> None:
        self._camera_id = camera_id
        self._enabled = enabled
        self._backend = backend
        self._input_width = input_width
        self._draw_landmarks = draw_landmarks
        self._pose: Any | None = None
        self._mp_pose: Any | None = None
        self._mp_drawing: Any | None = None

        if not enabled:
            return

        if backend != "mediapipe":
            logger.warning("Unsupported pose backend '%s'. Pose estimation is disabled.", backend)
            self._enabled = False
            return

        try:
            import mediapipe as mp
        except ImportError:
            logger.warning("mediapipe is not installed. Pose estimation is disabled.")
            self._enabled = False
            return

        self._mp_pose = mp.solutions.pose
        self._mp_drawing = mp.solutions.drawing_utils
        self._pose = self._mp_pose.Pose(
            static_image_mode=False,
            model_complexity=model_complexity,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def estimate(self, frame: cv2.typing.MatLike) -> dict[str, object]:
        frame_height, frame_width = frame.shape[:2]
        if not self._enabled or self._pose is None or self._mp_pose is None:
            return self._empty_result(frame_width=frame_width, frame_height=frame_height)

        started_at = time.perf_counter()
        resized_frame = self._resize_for_inference(frame)
        rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False
        result = self._pose.process(rgb_frame)
        inference_ms = (time.perf_counter() - started_at) * 1000

        if not result.pose_landmarks:
            return {
                **self._empty_result(frame_width=frame_width, frame_height=frame_height),
                "inference_ms": inference_ms,
                "backend": self._backend,
            }

        if self._draw_landmarks and self._mp_drawing is not None:
            self._mp_drawing.draw_landmarks(
                frame,
                result.pose_landmarks,
                self._mp_pose.POSE_CONNECTIONS,
            )

        return {
            "camera_id": self._camera_id,
            "person_detected": True,
            "keypoints": self._landmarks_to_keypoints(result.pose_landmarks.landmark),
            "inference_ms": inference_ms,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "backend": self._backend,
        }

    def close(self) -> None:
        if self._pose is not None:
            self._pose.close()
            self._pose = None

    def _empty_result(self, frame_width: int, frame_height: int) -> dict[str, object]:
        return {
            "camera_id": self._camera_id,
            "person_detected": False,
            "keypoints": [],
            "inference_ms": None,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "backend": self._backend,
        }

    def _resize_for_inference(self, frame: cv2.typing.MatLike) -> cv2.typing.MatLike:
        frame_height, frame_width = frame.shape[:2]
        if frame_width <= self._input_width:
            return frame

        scale = self._input_width / frame_width
        input_height = max(1, int(frame_height * scale))
        return cv2.resize(frame, (self._input_width, input_height), interpolation=cv2.INTER_AREA)

    def _landmarks_to_keypoints(self, landmarks: Any) -> list[dict[str, float | str]]:
        if self._mp_pose is None:
            return []

        keypoints: list[dict[str, float | str]] = []
        for index, landmark in enumerate(landmarks):
            name = self._mp_pose.PoseLandmark(index).name.lower()
            keypoints.append(
                {
                    "name": name,
                    "x": float(landmark.x),
                    "y": float(landmark.y),
                    "z": float(landmark.z),
                    "visibility": float(landmark.visibility),
                }
            )
        return keypoints
