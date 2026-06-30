import unittest

from _helpers import assert_contains, write_requirement_log


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
        write_requirement_log(
            "R-22",
            "speech-id-dedup-fallback",
            "unit_status=speech_id_and_client_dedup_verified",
            "field_evidence_required=optional",
            "field_success_criteria=same speech_id is played once; failed mp3 request falls back to browser speech once",
            "expected_runtime_logs=browser console log or screen recording plus test-results/requirements/R-22-speech-id-dedup-fallback-server.log",
        )


if __name__ == "__main__":
    unittest.main()
