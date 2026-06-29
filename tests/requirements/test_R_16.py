import unittest

from _helpers import assert_contains


class TestR16AudienceStage(unittest.TestCase):
    def test_stage_screen_shows_all_feeds_and_game_hud(self):
        assert_contains(
            self,
            "server/app/web/templates/stage.html",
            'class="cast-cam-feed"',
            "/api/cameras/{{ camera_id }}/stream",
            "gauge-value",
            "coach-text",
            "timer-text",
            "cast-scores",
        )
        assert_contains(
            self,
            "server/app/web/static/js/stage.js",
            "new WebSocket",
            "/api/game/ws",
            "renderScores",
            "setGauge",
        )


if __name__ == "__main__":
    unittest.main()
