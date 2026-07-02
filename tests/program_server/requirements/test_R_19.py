import unittest

from _helpers import assert_contains, function_body, read, write_requirement_log


class TestR19NoLlmInPlayingPath(unittest.TestCase):
    def test_playing_gauge_update_does_not_call_llm_generation(self):
        manager = read("src/program_server/app/services/game_manager.py")
        body = function_body(manager, "_update_gauge")
        self.assertIn("analyze_group", body)
        self.assertIn("narrator.coach", body)
        self.assertNotIn("generate_prompts", body)
        self.assertNotIn("generate_mc_comment", body)
        self.assertNotIn("generate_final_report", body)
        self.assertNotIn("self._llm", body)
        assert_contains(
            self,
            "src/program_server/app/services/game_manager.py",
            "# Background LLM task helpers (never awaited from tick/playing)",
        )
        write_requirement_log(
            "R-19",
            "no-llm-playing-path",
            "unit_status=playing_path_static_verified",
            "field_evidence_required=optional",
            "field_success_criteria=server log has no LLM request during playing phase and pose_fps remains stable",
            "expected_runtime_logs=test-results/program_server/requirements/R-19-no-llm-playing-path-server.log, test-results/program_server/requirements/R-19-no-llm-playing-path-camera-<CAMERA_NO>-metrics.jsonl",
        )


if __name__ == "__main__":
    unittest.main()
