import unittest

from _helpers import assert_contains


class TestR22SpeechIdDedup(unittest.TestCase):
    def test_speech_id_prevents_duplicate_voice_playback_and_falls_back(self):
        assert_contains(
            self,
            "server/app/services/game_manager.py",
            "speech_id",
            "self._speech_seq += 1",
        )
        assert_contains(self, "server/app/api/game_routes.py", '@router.get("/speech/{speech_id}.mp3")')
        assert_contains(
            self,
            "server/app/web/static/js/game.js",
            "lastSpokenId",
            "id <= tts.lastSpokenId",
            "playServerAudio",
            "speakLine(text)",
        )


if __name__ == "__main__":
    unittest.main()
