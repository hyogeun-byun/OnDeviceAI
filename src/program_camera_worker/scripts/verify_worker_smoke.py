from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import load_config
from app.network.websocket_client import WebSocketCameraClient


MEDIAPIPE_LANDMARKS = (
    "nose",
    "left_eye_inner",
    "left_eye",
    "left_eye_outer",
    "right_eye_inner",
    "right_eye",
    "right_eye_outer",
    "left_ear",
    "right_ear",
    "mouth_left",
    "mouth_right",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_pinky",
    "right_pinky",
    "left_index",
    "right_index",
    "left_thumb",
    "right_thumb",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
)


def synthetic_pose(camera_id: str) -> dict[str, object]:
    keypoints = []
    for index, name in enumerate(MEDIAPIPE_LANDMARKS):
        row = index // 6
        col = index % 6
        keypoints.append(
            {
                "name": name,
                "x": 0.25 + col * 0.08,
                "y": 0.15 + row * 0.10,
                "z": 0.0,
                "visibility": 0.99,
            }
        )
    return {
        "camera_id": camera_id,
        "person_detected": True,
        "keypoints": keypoints,
        "inference_ms": 1.0,
        "frame_width": 640,
        "frame_height": 480,
        "backend": "mediapipe-smoke",
    }


def synthetic_metrics(camera_id: str) -> dict[str, object]:
    return {
        "camera_id": camera_id,
        "elapsed_seconds": 5.0,
        "frame_fps": 10.0,
        "pose_fps": 10.0,
        "avg_capture_ms": 1.0,
        "avg_pose_ms": 1.0,
        "avg_encode_ms": 1.0,
        "avg_frame_upload_ms": 1.0,
        "avg_pose_upload_ms": 1.0,
        "avg_frame_kb": 20.0,
        "upload_kb_s": 200.0,
        "sent_frames": 10,
        "failed_frames": 0,
        "sent_poses": 10,
        "failed_poses": 0,
    }


def main() -> None:
    config = load_config()
    client = WebSocketCameraClient(server_url=config.server_url, camera_id=config.camera_id)
    print(f"camera_id={config.camera_id}")
    print(f"server_url={config.server_url}")
    print("sending synthetic pose via camera worker WebSocket path")
    pose_ms = client.send_pose(synthetic_pose(config.camera_id))
    metrics_ms = client.send_metrics(synthetic_metrics(config.camera_id))
    client.close()
    print(f"send_pose_ms={pose_ms}")
    print(f"send_metrics_ms={metrics_ms}")
    if pose_ms is None or metrics_ms is None:
        raise SystemExit("camera worker websocket smoke failed")
    print("camera worker websocket smoke OK")


if __name__ == "__main__":
    main()
