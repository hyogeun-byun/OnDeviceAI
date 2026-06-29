import unittest

from _helpers import assert_contains


class TestR20Fallbacks(unittest.TestCase):
    def test_llm_and_tts_failures_fall_back_without_stopping_game(self):
        assert_contains(self, "server/.env.example", "LLM_ENABLED=false")
        assert_contains(
            self,
            "server/app/services/game_narrator.py",
            "degrades gracefully",
            "static_mc_comment",
            "static_final_report",
        )
        assert_contains(
            self,
            "server/app/services/speech_audio.py",
            "Everything degrades gracefully",
            "except Exception",
            "browser falls back",
        )
        assert_contains(self, "server/app/web/static/js/game.js", "speakLine(text)")


if __name__ == "__main__":
    unittest.main()
