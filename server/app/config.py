from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    camera_ids: tuple[str, ...]
    visualize_metrics: bool
    llm_enabled: bool
    llm_base_url: str
    llm_model: str
    llm_timeout: float
    llm_default_theme: str
    tts_enabled: bool
    tts_engine: str
    tts_voice: str
    tts_openai_model: str
    tts_piper_model: str
    tts_lang: str
    tts_team_name: str
    tts_mc_name: str
    edge_tts_enabled: bool
    edge_tts_voice: str
    edge_tts_rate: str


def read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> ServerConfig:
    load_dotenv()

    camera_ids = tuple(
        camera_id.strip()
        for camera_id in os.getenv("CAMERA_IDS", "camera_01,camera_02,camera_03").split(",")
        if camera_id.strip()
    )

    return ServerConfig(
        host=os.getenv("SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("SERVER_PORT", "8000")),
        camera_ids=camera_ids,
        visualize_metrics=read_bool("VISUALIZE_METRICS", True),
        llm_enabled=read_bool("LLM_ENABLED", False),
        llm_base_url=os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1/chat/completions"),
        llm_model=os.getenv("LLM_MODEL", "exaone3.5:2.4b"),
        llm_timeout=float(os.getenv("LLM_TIMEOUT", "12")),
        llm_default_theme=os.getenv("LLM_DEFAULT_THEME", "기본"),
        tts_enabled=read_bool("TTS_ENABLED", False),
        tts_engine=os.getenv("TTS_ENGINE", "auto"),
        tts_voice=os.getenv("TTS_VOICE", "coral"),
        tts_openai_model=os.getenv("TTS_OPENAI_MODEL", "gpt-4o-mini-tts"),
        tts_piper_model=os.getenv("TTS_PIPER_MODEL", ""),
        tts_lang=os.getenv("TTS_LANG", "ko"),
        tts_team_name=os.getenv("TTS_TEAM_NAME", ""),
        tts_mc_name=os.getenv("TTS_MC_NAME", "민수"),
        edge_tts_enabled=read_bool("EDGE_TTS_ENABLED", True),
        edge_tts_voice=os.getenv("EDGE_TTS_VOICE", "ko-KR-InJoonNeural"),
        edge_tts_rate=os.getenv("EDGE_TTS_RATE", "+8%"),
    )
