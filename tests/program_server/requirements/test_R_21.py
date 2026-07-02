import unittest

from _helpers import assert_contains


class TestR21EdgeTtsAndAvatar(unittest.TestCase):
    def test_edge_tts_mp3_and_avatar_talking_animation_are_wired(self):
        assert_contains(
            self,
            "src/program_server/app/services/speech_audio.py",
            "edge_tts.Communicate",
            "ko-KR-InJoonNeural",
        )
        assert_contains(self, "src/program_server/app/api/game_routes.py", "audio/mpeg")
        assert_contains(
            self,
            "src/program_server/app/web/static/js/game.js",
            "new Audio",
            "setMcTalking(true",
            "is-talking",
            "mcLiveBubble",
        )
        assert_contains(self, "src/program_server/app/web/templates/game.html", "mc-mouth", "mc-live-bubble")


if __name__ == "__main__":
    unittest.main()
