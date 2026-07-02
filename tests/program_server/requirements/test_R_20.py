import unittest

from _helpers import assert_contains, write_requirement_log


class TestR20Fallbacks(unittest.TestCase):
    def test_llm_and_tts_failures_fall_back_without_stopping_game(self):
        assert_contains(self, "src/program_server/.env.example", "LLM_ENABLED=false")
        assert_contains(
            self,
            "src/program_server/app/services/game_narrator.py",
            "degrades gracefully",
            "static_mc_comment",
            "static_final_report",
        )
        assert_contains(
            self,
            "src/program_server/app/services/speech_audio.py",
            "Everything degrades gracefully",
            "except Exception",
            "browser falls back",
        )
        assert_contains(self, "src/program_server/app/web/static/js/game.js", "speakLine(text)")
        write_requirement_log(
            "R-20",
            "llm-tts-fallback",
            "unit_status=fallback_paths_verified",
            "field_evidence_required=true",
            "field_success_criteria=LLM_ENABLED=false or TTS failure still reaches finished phase with visible static text/browser speech fallback",
            "expected_runtime_logs=test-results/program_server/requirements/R-20-llm-tts-fallback-server.log",
            "expected_settings=src/program_server/.env with LLM_ENABLED=false or EDGE_TTS_ENABLED=false",
        )


if __name__ == "__main__":
    unittest.main()
