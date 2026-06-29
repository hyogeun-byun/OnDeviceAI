import unittest

from _helpers import assert_contains, load_server_module


class TestR09FiveRandomPrompts(unittest.TestCase):
    def test_each_game_uses_five_prompts_from_selected_category(self):
        narrator = load_server_module("app.services.game_narrator")
        manager = assert_contains(self, "server/app/services/game_manager.py", "TOTAL_ROUNDS = 5")
        self.assertIn("default_prompts(theme=chosen, n=self._total_rounds)", manager)
        for category, prompts in narrator.CATEGORY_PROMPTS.items():
            self.assertGreaterEqual(len(prompts), 5, category)
            self.assertEqual(5, len(narrator.default_prompts(category, n=5)))


if __name__ == "__main__":
    unittest.main()
