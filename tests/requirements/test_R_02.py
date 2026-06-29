import unittest

from _helpers import assert_contains


class TestR02JpegStreaming(unittest.TestCase):
    def test_worker_encodes_jpeg_and_server_serves_mjpeg(self):
        assert_contains(self, "camera-worker/app/camera/frame_encoder.py", "encode_to_jpeg", ".jpg")
        assert_contains(self, "camera-worker/app/network/websocket_client.py", "send_frame", "send_binary")
        assert_contains(
            self,
            "server/app/api/camera_routes.py",
            '@router.get("/{camera_id}/stream")',
            "multipart/x-mixed-replace; boundary=frame",
            "Content-Type: image/jpeg",
        )


if __name__ == "__main__":
    unittest.main()
