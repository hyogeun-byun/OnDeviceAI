import unittest

from _helpers import assert_contains


class TestR25ResultPhotoAndPngReport(unittest.TestCase):
    def test_result_frame_overlay_and_png_download_are_available(self):
        assert_contains(
            self,
            "src/program_server/app/api/game_routes.py",
            '@router.get("/result-frame/{round_number}/{player_index}.jpg")',
            "media_type=\"image/jpeg\"",
        )
        assert_contains(
            self,
            "src/program_server/app/web/static/js/game.js",
            "function drawVisionCard",
            "revealResultFrames",
            "buildReportImage",
            "1080",
            "1350",
            "link.download",
            ".png",
        )


if __name__ == "__main__":
    unittest.main()
