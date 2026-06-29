import unittest

from _helpers import assert_contains


class TestR01MultiCameraWebSocket(unittest.TestCase):
    def test_camera_workers_connect_independently_by_id(self):
        assert_contains(
            self,
            "server/app/api/camera_routes.py",
            '@router.websocket("/{camera_id}/ws")',
            "stream_manager.update_frame(camera_id=camera_id",
            'message_type == "pose"',
        )
        assert_contains(
            self,
            "server/app/main.py",
            "StreamManager(camera_ids=config.camera_ids)",
            "camera_ids=config.camera_ids",
        )


if __name__ == "__main__":
    unittest.main()
