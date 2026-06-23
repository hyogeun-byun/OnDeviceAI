from __future__ import annotations

import logging
import time
from queue import Empty, Full, Queue
from threading import Event, Thread

import cv2

from app.camera.camera_reader import CameraReader
from app.camera.frame_encoder import FrameEncoder
from app.config import load_config
from app.inference.pose_estimator import PoseEstimator
from app.metrics import CameraWorkerMetrics
from app.network.websocket_client import WebSocketCameraClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)

FramePacket = tuple[cv2.typing.MatLike, float]


def put_latest(queue: Queue[FramePacket], packet: FramePacket) -> None:
    try:
        queue.put_nowait(packet)
    except Full:
        try:
            queue.get_nowait()
        except Empty:
            pass
        queue.put_nowait(packet)


def capture_loop(
    camera_reader: CameraReader,
    frame_queue: Queue[FramePacket],
    pose_queue: Queue[FramePacket],
    target_fps: float,
    stop_event: Event,
) -> None:
    sleep_seconds = 1.0 / target_fps if target_fps > 0 else 0.1

    while not stop_event.is_set():
        loop_started_at = time.perf_counter()
        capture_started_at = time.perf_counter()
        frame = camera_reader.read()
        capture_ms = (time.perf_counter() - capture_started_at) * 1000

        put_latest(frame_queue, (frame.copy(), capture_ms))
        put_latest(pose_queue, (frame.copy(), capture_ms))

        elapsed_seconds = time.perf_counter() - loop_started_at
        time.sleep(max(0.0, sleep_seconds - elapsed_seconds))


def frame_sender_loop(
    frame_queue: Queue[FramePacket],
    frame_encoder: FrameEncoder,
    websocket_client: WebSocketCameraClient,
    metrics: CameraWorkerMetrics,
    stop_event: Event,
) -> None:
    while not stop_event.is_set():
        try:
            frame, capture_ms = frame_queue.get(timeout=0.2)
        except Empty:
            continue

        encode_started_at = time.perf_counter()
        frame_bytes = frame_encoder.encode_to_jpeg(frame)
        encode_ms = (time.perf_counter() - encode_started_at) * 1000
        frame_upload_ms = websocket_client.send_frame(frame_bytes)

        metrics.record_frame(
            frame_bytes=len(frame_bytes),
            capture_ms=capture_ms,
            encode_ms=encode_ms,
            frame_upload_ms=frame_upload_ms,
        )

        metrics_payload = metrics.maybe_collect()
        if metrics_payload is not None:
            websocket_client.send_metrics(metrics_payload)


def pose_inference_loop(
    pose_queue: Queue[FramePacket],
    pose_estimator: PoseEstimator,
    websocket_client: WebSocketCameraClient,
    metrics: CameraWorkerMetrics,
    pose_enabled: bool,
    target_fps: float,
    stop_event: Event,
) -> None:
    inference_interval_seconds = 1.0 / target_fps if target_fps > 0 else 0.1

    while not stop_event.is_set():
        loop_started_at = time.perf_counter()
        try:
            frame, _capture_ms = pose_queue.get(timeout=0.2)
        except Empty:
            continue

        if pose_enabled:
            pose_started_at = time.perf_counter()
            pose_result = pose_estimator.estimate(frame)
            pose_ms = (time.perf_counter() - pose_started_at) * 1000
            pose_upload_ms = websocket_client.send_pose(pose_result)
            metrics.record_pose(pose_ms=pose_ms, pose_upload_ms=pose_upload_ms)

        elapsed_seconds = time.perf_counter() - loop_started_at
        time.sleep(max(0.0, inference_interval_seconds - elapsed_seconds))


def main() -> None:
    config = load_config()

    logger.info(
        (
            "Starting camera worker: camera_id=%s server=%s target_fps=%.2f "
            "pose_enabled=%s keypoint_inference_fps=%.2f pose_input_width=%s jpeg_quality=%s"
        ),
        config.camera_id,
        config.server_url,
        config.fps,
        config.pose_enabled,
        config.fps,
        config.pose_input_width,
        config.jpeg_quality,
    )

    camera_reader = CameraReader(
        camera_index=config.camera_index,
        frame_width=config.frame_width,
        frame_height=config.frame_height,
    )
    frame_encoder = FrameEncoder(jpeg_quality=config.jpeg_quality)
    websocket_client = WebSocketCameraClient(server_url=config.server_url, camera_id=config.camera_id)
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

    frame_queue: Queue[FramePacket] = Queue(maxsize=1)
    pose_queue: Queue[FramePacket] = Queue(maxsize=1)
    stop_event = Event()

    threads = [
        Thread(
            target=capture_loop,
            name="camera-capture",
            args=(camera_reader, frame_queue, pose_queue, config.fps, stop_event),
            daemon=True,
        ),
        Thread(
            target=frame_sender_loop,
            name="frame-sender",
            args=(frame_queue, frame_encoder, websocket_client, metrics, stop_event),
            daemon=True,
        ),
        Thread(
            target=pose_inference_loop,
            name="pose-inference",
            args=(pose_queue, pose_estimator, websocket_client, metrics, config.pose_enabled, config.fps, stop_event),
            daemon=True,
        ),
    ]

    try:
        camera_reader.open()
        for thread in threads:
            thread.start()

        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Stopping camera worker.")
    finally:
        stop_event.set()
        for thread in threads:
            thread.join(timeout=2.0)
        websocket_client.close()
        pose_estimator.close()
        camera_reader.close()


if __name__ == "__main__":
    main()
