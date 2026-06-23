from __future__ import annotations

import logging
import time

from app.camera.camera_reader import CameraReader
from app.camera.frame_encoder import FrameEncoder
from app.config import load_config
from app.inference.pose_estimator import PoseEstimator
from app.network.server_client import ServerClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    config = load_config()
    sleep_seconds = 1.0 / config.fps if config.fps > 0 else 0.1

    logger.info("Starting camera worker: camera_id=%s server=%s", config.camera_id, config.server_url)

    camera_reader = CameraReader(
        camera_index=config.camera_index,
        frame_width=config.frame_width,
        frame_height=config.frame_height,
    )
    frame_encoder = FrameEncoder(jpeg_quality=config.jpeg_quality)
    server_client = ServerClient(server_url=config.server_url, camera_id=config.camera_id)
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

    # --- TEMP: 단계별 타이밍 계측 (병목 진단용, 진단 후 제거) ---
    timing_report_every = 30
    timing_sums = {"read": 0.0, "estimate": 0.0, "send_pose": 0.0, "encode": 0.0, "send_frame": 0.0, "loop": 0.0}
    timing_counts = {key: 0 for key in timing_sums}
    timing_window = 0
    # --- END TEMP ---

    try:
        camera_reader.open()
        frame_index = 0
        while True:
            loop_started = time.perf_counter()

            t0 = time.perf_counter()
            frame = camera_reader.read()
            timing_sums["read"] += (time.perf_counter() - t0) * 1000
            timing_counts["read"] += 1

            if config.pose_enabled and frame_index % config.pose_inference_interval == 0:
                t0 = time.perf_counter()
                pose_result = pose_estimator.estimate(frame)
                timing_sums["estimate"] += (time.perf_counter() - t0) * 1000
                timing_counts["estimate"] += 1

                t0 = time.perf_counter()
                server_client.send_pose(pose_result)
                timing_sums["send_pose"] += (time.perf_counter() - t0) * 1000
                timing_counts["send_pose"] += 1

            t0 = time.perf_counter()
            frame_bytes = frame_encoder.encode_to_jpeg(frame)
            timing_sums["encode"] += (time.perf_counter() - t0) * 1000
            timing_counts["encode"] += 1

            t0 = time.perf_counter()
            server_client.send_frame(frame_bytes)
            timing_sums["send_frame"] += (time.perf_counter() - t0) * 1000
            timing_counts["send_frame"] += 1

            timing_sums["loop"] += (time.perf_counter() - loop_started) * 1000
            timing_counts["loop"] += 1
            timing_window += 1

            if timing_window >= timing_report_every:
                parts = []
                for key in ("read", "estimate", "send_pose", "encode", "send_frame", "loop"):
                    count = timing_counts[key]
                    avg = timing_sums[key] / count if count else 0.0
                    parts.append(f"{key}={avg:6.1f}ms")
                loop_avg = timing_sums["loop"] / timing_counts["loop"] if timing_counts["loop"] else 0.0
                eff_fps = 1000.0 / loop_avg if loop_avg > 0 else 0.0
                logger.info("[TIMING] %s  => %.1f loop-FPS (sleep 제외 순수처리)", "  ".join(parts), eff_fps)
                for key in timing_sums:
                    timing_sums[key] = 0.0
                    timing_counts[key] = 0
                timing_window = 0

            frame_index += 1
            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        logger.info("Stopping camera worker.")
    finally:
        pose_estimator.close()
        camera_reader.close()
        server_client.close()


if __name__ == "__main__":
    main()
