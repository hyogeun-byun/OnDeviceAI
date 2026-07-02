import unittest

from _helpers import assert_contains, assert_not_contains


class TestR14GameScreenPrivacy(unittest.TestCase):
    def test_game_screen_hides_live_streams_except_temporary_hint(self):
        html = assert_not_contains(
            self,
            "src/program_server/app/web/templates/game.html",
            "/api/cameras/{{ camera_id }}/stream",
            'class="cast-cam-feed"',
        )
        playing_screen = html.split("<!-- PLAYING -->", 1)[1].split("<!-- RESULT -->", 1)[0]
        self.assertIn("cam-hint-overlay", playing_screen)
        self.assertIn("gauge-value", playing_screen)
        self.assertIn("coach-text", playing_screen)
        self.assertIn("timer-text", playing_screen)
        self.assertNotIn("/api/cameras/", playing_screen)
        assert_contains(
            self,
            "src/program_server/app/web/static/js/game.js",
            "function renderCamHint",
            "function refreshCamHintSnapshots",
            "function startCamHintSnapshots",
            "function stopCamHintSnapshots",
            'img.src = `/api/cameras/${id}/snapshot?t=${stamp}`',
            'img.removeAttribute("src")',
        )


if __name__ == "__main__":
    unittest.main()
