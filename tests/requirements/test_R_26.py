import unittest

from _helpers import assert_contains, write_requirement_log


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
            "60초 스프린트",
        )
        assert_contains(
            self,
            "scripts/verify_devops.sh",
            "R-26-offline-lan-server.log",
            "R-01-multi-camera-websocket-camera-01.log",
            "R-01-R-27-requirements-unittest.log",
        )
        write_requirement_log(
            "R-26",
            "offline-lan-operation",
            "unit_status=offline_configuration_and_fallback_paths_verified",
            "field_evidence_required=true",
            "field_success_criteria=WAN disconnected, server/camera/browser on same LAN, /game and /stage finish one 60-second sprint",
            "expected_runtime_logs=test-results/requirements/R-26-offline-lan-server.log",
            "expected_camera_logs=test-results/requirements/R-26-offline-lan-camera-<CAMERA_NO>.log",
            "guide=test-results/offline-lan/R-26-offline-lan-guide.md",
        )


if __name__ == "__main__":
    unittest.main()
