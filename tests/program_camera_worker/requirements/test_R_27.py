import unittest

from _helpers import assert_contains


class TestR27ConfigurationExamples(unittest.TestCase):
    def test_server_and_worker_settings_are_documented_in_env_or_config_examples(self):
        assert_contains(
            self,
            "src/program_server/.env.example",
            "CAMERA_IDS=",
            "LLM_ENABLED=",
            "TTS_ENABLED=",
            "EDGE_TTS_ENABLED=",
        )
        assert_contains(
            self,
            "src/program_camera_worker/.env.example",
            "CAMERA_ID=",
            "SERVER_URL=",
            "FPS=",
            "LOG_DIR=../../log",
            "METRICS_LOG_ENABLED=true",
            "POSE_MODEL_COMPLEXITY=",
            "POSE_INPUT_WIDTH=192",
        )
        assert_contains(self, "config/server.example.yaml", "camera_ids", "visualize_metrics")
        assert_contains(
            self,
            "config/camera-worker.example.yaml",
            "pose_model_complexity",
            "pose_input_width",
            "metrics_log_enabled",
        )


if __name__ == "__main__":
    unittest.main()
