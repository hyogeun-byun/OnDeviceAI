import unittest

from _helpers import assert_contains


class TestR26OfflineLanOperation(unittest.TestCase):
    def test_core_game_is_local_with_optional_network_tts_fallback(self):
        assert_contains(self, "server/.env.example", "LLM_ENABLED=false", "EDGE_TTS_ENABLED=true")
        assert_contains(self, "camera-worker/.env.example", "SERVER_URL=http://192.168.0.10:8000")
        assert_contains(
            self,
            "server/app/services/speech_audio.py",
            "network",
            "browser falls back",
            "except Exception",
        )
        assert_contains(
            self,
            "server/app/web/static/js/game.js",
            "SpeechSynthesisUtterance",
            "speakLine(text)",
        )
        assert_contains(
            self,
            "test-results/offline-lan/R-26-offline-lan-guide.md",
            "공유기",
            "인터넷 연결이 없는 상태",
            "5라운드",
        )


if __name__ == "__main__":
    unittest.main()
