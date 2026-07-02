import unittest

from _helpers import load_server_module


class TestR08SixCategories(unittest.TestCase):
    def test_six_fixed_categories_are_available(self):
        narrator = load_server_module("app.services.game_narrator")
        self.assertEqual(6, len(narrator.THEMES))
        self.assertEqual(
            {
                "상황",
                "운동",
                "감정",
                "영화 혹은 애니메이션",
                "인물(for 2,30대)",
                "인물(for 4,50대)",
            },
            set(narrator.THEMES),
        )


if __name__ == "__main__":
    unittest.main()
