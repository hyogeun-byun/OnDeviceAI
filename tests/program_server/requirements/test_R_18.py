import unittest

from _helpers import assert_contains


class TestR18AiMcNarration(unittest.TestCase):
    def test_llm_narration_hooks_exist_for_intro_result_and_final(self):
        assert_contains(
            self,
            "src/program_server/app/services/game_narrator.py",
            "async def generate_prompts",
            "async def generate_mc_comment",
            "async def generate_final_report",
            "한국어",
        )
        assert_contains(
            self,
            "src/program_server/app/services/game_manager.py",
            "_build_prompts",
            "_build_mc_comment",
            "_build_final_report",
            "intro_line",
        )


if __name__ == "__main__":
    unittest.main()
