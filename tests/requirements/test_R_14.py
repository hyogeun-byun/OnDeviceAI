import unittest

from _helpers import assert_contains, assert_not_contains


class TestR14GameScreenPrivacy(unittest.TestCase):
    def test_game_screen_has_no_live_camera_streams(self):
        html = assert_not_contains(
            self,
            "server/app/web/templates/game.html",
            "/api/cameras/{{ camera_id }}/stream",
            'class="cast-cam-feed"',
        )
        self.assertNotIn("<img", html.lower())
        assert_contains(
            self,
            "server/app/web/templates/game.html",
            "gauge-value",
            "coach-text",
            "timer-text",
            "merged-skel-canvas",
        )


if __name__ == "__main__":
    unittest.main()
