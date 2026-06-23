from __future__ import annotations

import logging
import time

from app.camera.camera_reader import CameraReader
from app.camera.frame_encoder import FrameEncoder
from app.config import load_config
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

    try:
        camera_reader.open()
        while True:
            frame = camera_reader.read()
            frame_bytes = frame_encoder.encode_to_jpeg(frame)
            server_client.send_frame(frame_bytes)
            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        logger.info("Stopping camera worker.")
    finally:
        camera_reader.close()


if __name__ == "__main__":
    main()

