from __future__ import annotations

import logging
import time

from app.camera.camera_reader import CameraReader
from app.camera.frame_encoder import FrameEncoder
from app.config import load_config
from app.inference.pose_estimator import PoseEstimator
from app.metrics import CameraWorkerMetrics
from app.network.server_client import ServerClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    config = load_config()
    sleep_seconds = 1.0 / config.fps if config.fps > 0 else 0.1

    logger.info(
        (
            "Starting camera worker: camera_id=%s server=%s target_fps=%.2f "
            "pose_enabled=%s pose_interval=%s pose_input_width=%s jpeg_quality=%s"
        ),
        config.camera_id,
        config.server_url,
        config.fps,
        config.pose_enabled,
        config.pose_inference_interval,
        config.pose_input_width,
        config.jpeg_quality,
    )

    camera_reader = CameraReader(
        camera_index=config.camera_index,
        frame_width=config.frame_width,
        frame_height=config.frame_height,
    )
    frame_encoder = FrameEncoder(jpeg_quality=config.jpeg_quality)
    server_client = ServerClient(server_url=config.server_url, camera_id=config.camera_id)
    metrics = CameraWorkerMetrics(
        camera_id=config.camera_id,
        log_interval_seconds=config.log_interval_seconds,
    )
    pose_estimator = PoseEstimator(
        camera_id=config.camera_id,
        enabled=config.pose_enabled,
        backend=config.pose_backend,
        model_complexity=config.pose_model_complexity,
        input_width=config.pose_input_width,
        min_detection_confidence=config.pose_min_detection_confidence,
        min_tracking_confidence=config.pose_min_tracking_confidence,
        draw_landmarks=config.pose_draw_landmarks,
    )

    try:
        camera_reader.open()
        frame_index = 0
        while True:
            loop_started_at = time.perf_counter()
            capture_started_at = time.perf_counter()
            frame = camera_reader.read()
            capture_ms = (time.perf_counter() - capture_started_at) * 1000

            if config.pose_enabled and frame_index % config.pose_inference_interval == 0:
                pose_started_at = time.perf_counter()
                pose_result = pose_estimator.estimate(frame)
                pose_ms = (time.perf_counter() - pose_started_at) * 1000
                pose_upload_ms = server_client.send_pose(pose_result)
                metrics.record_pose(pose_ms=pose_ms, pose_upload_ms=pose_upload_ms)

            encode_started_at = time.perf_counter()
            frame_bytes = frame_encoder.encode_to_jpeg(frame)
            encode_ms = (time.perf_counter() - encode_started_at) * 1000
            frame_upload_ms = server_client.send_frame(frame_bytes)
            metrics.record_frame(
                frame_bytes=len(frame_bytes),
                capture_ms=capture_ms,
                encode_ms=encode_ms,
                frame_upload_ms=frame_upload_ms,
            )
            metrics_payload = metrics.maybe_collect()
            if metrics_payload is not None:
                server_client.send_metrics(metrics_payload)
            frame_index += 1

            elapsed_seconds = time.perf_counter() - loop_started_at
            time.sleep(max(0.0, sleep_seconds - elapsed_seconds))
    except KeyboardInterrupt:
        logger.info("Stopping camera worker.")
    finally:
        pose_estimator.close()
        camera_reader.close()


if __name__ == "__main__":
    main()
