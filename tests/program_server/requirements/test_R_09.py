import unittest

from _helpers import assert_contains, load_server_module


class TestR09SprintPromptPool(unittest.TestCase):
    def test_selected_category_loads_prompt_pool_for_60s_sprint(self):
        narrator = load_server_module("app.services.game_narrator")
        manager = assert_contains(
            self,
            "src/program_server/app/services/game_manager.py",
            "GAME_TOTAL_SECONDS = 60.0",
            "PROMPT_POOL_LIMIT = 99",
            "PLAY_PASS_SCORE = 90.0",
            "selected_prompts = list(narrator.default_prompts(theme=chosen, n=PROMPT_POOL_LIMIT))",
            'prompt_source="category_random_in_theme"',
            "if self._state.prompts and next_index >= len(self._state.prompts):",
        )
        self.assertIn("state.gauge >= PLAY_PASS_SCORE", manager)
        for category, prompts in narrator.CATEGORY_PROMPTS.items():
            self.assertGreaterEqual(len(prompts), 5, category)
            selected = narrator.default_prompts(category, n=99)
            self.assertEqual(prompts[0], selected[0], category)
            self.assertEqual(len(prompts), len(selected), category)
            self.assertLessEqual(set(selected), set(prompts), category)


if __name__ == "__main__":
    unittest.main()
