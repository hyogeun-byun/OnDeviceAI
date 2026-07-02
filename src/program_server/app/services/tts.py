"""Text-to-speech output for the AI MC.

Runs entirely on a background daemon thread fed by a thread-safe queue, so
``say()`` is non-blocking and never stalls the asyncio game loop or pose
inference. Synthesis + playback happen sequentially in the worker thread.

Engine priority (``TTS_ENGINE=auto``): OpenAI TTS -> Piper -> espeak-ng.
Any failure falls through to the next engine; if none work, audio is simply
skipped and the game continues with on-screen text only.

TTS is only ever enqueued during non-real-time phases (start intro, round
result, final report) by the caller — never during the playing phase.
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading

_MAX_QUEUE = 4  # drop stale lines instead of letting audio pile up


class Speaker:
    def __init__(
        self,
        enabled: bool,
        engine: str = "auto",
        voice: str = "coral",
        openai_model: str = "gpt-4o-mini-tts",
        piper_model: str = "",
        lang: str = "ko",
    ) -> None:
        self._voice = voice
        self._openai_model = openai_model
        self._piper_model = piper_model
        self._lang = lang
        self._engine = self._resolve_engine(engine) if enabled else None
        self._enabled = enabled and self._engine is not None
        self._queue: queue.Queue[str] = queue.Queue(maxsize=_MAX_QUEUE)

        if self._enabled:
            print(f"[tts] enabled (engine={self._engine}, voice={self._voice})")
            thread = threading.Thread(target=self._worker, daemon=True)
            thread.start()
        elif enabled:
            print("[tts] no usable engine found -> voice disabled")

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def engine(self) -> str | None:
        return self._engine

    def say(self, text: str) -> None:
        """Enqueue text for speech. Non-blocking; drops the line if busy."""
        if not self._enabled or not text or not text.strip():
            return
        try:
            self._queue.put_nowait(text.strip())
        except queue.Full:
            pass  # too many queued -> skip rather than block the game

    # ------------------------------------------------------------------ #
    # Worker thread
    # ------------------------------------------------------------------ #
    def _worker(self) -> None:
        while True:
            text = self._queue.get()
            try:
                self._speak_with_fallback(text)
            except Exception as error:  # noqa: BLE001
                print(f"[tts] speak failed: {error}")
            finally:
                self._queue.task_done()

    def _speak_with_fallback(self, text: str) -> None:
        order = self._engine_order()
        for engine in order:
            try:
                if engine == "openai" and self._speak_openai(text):
                    return
                if engine == "piper" and self._speak_piper(text):
                    return
                if engine == "espeak" and self._speak_espeak(text):
                    return
            except Exception as error:  # noqa: BLE001
                print(f"[tts] engine '{engine}' failed: {error}")
        print("[tts] all engines failed -> skipping audio")

    def _engine_order(self) -> list[str]:
        if self._engine == "openai":
            return ["openai", "piper", "espeak"]
        if self._engine == "piper":
            return ["piper", "espeak"]
        return ["espeak"]

    # ------------------------------------------------------------------ #
    # Engine implementations
    # ------------------------------------------------------------------ #
    def _speak_openai(self, text: str) -> bool:
        if not os.getenv("OPENAI_API_KEY"):
            return False
        try:
            from openai import OpenAI
        except Exception:
            return False

        client = OpenAI()
        out = "/tmp/mc_tts.mp3"
        instructions = (
            "밝고 친근한 한국 예능 게임 진행자처럼, 빠르지만 또렷하게 신나게 말해줘. "
            "특정 실존 인물의 목소리나 말투는 따라 하지 마."
        )
        with client.audio.speech.with_streaming_response.create(
            model=self._openai_model,
            voice=self._voice,
            input=text,
            instructions=instructions,
        ) as response:
            response.stream_to_file(out)
        return self._play_file(out)

    def _speak_piper(self, text: str) -> bool:
        if not self._piper_model or not os.path.exists(self._piper_model):
            return False
        if shutil.which("piper") is None:
            return False
        out = "/tmp/mc_tts.wav"
        subprocess.run(
            ["piper", "--model", self._piper_model, "--output_file", out],
            input=text.encode("utf-8"),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return self._play_file(out)

    def _speak_espeak(self, text: str) -> bool:
        binary = shutil.which("espeak-ng") or shutil.which("espeak")
        if binary is None:
            return False
        subprocess.run(
            [binary, "-v", self._lang, "-s", "165", text],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _play_file(self, path: str) -> bool:
        if path.endswith(".mp3") and shutil.which("mpg123"):
            subprocess.run(
                ["mpg123", "-q", path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        if path.endswith(".wav") and shutil.which("aplay"):
            subprocess.run(
                ["aplay", "-q", path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        return False

    def _resolve_engine(self, requested: str) -> str | None:
        requested = (requested or "auto").strip().lower()
        has_espeak = (shutil.which("espeak-ng") or shutil.which("espeak")) is not None
        has_piper = bool(self._piper_model) and os.path.exists(self._piper_model) and (
            shutil.which("piper") is not None
        )
        has_openai = bool(os.getenv("OPENAI_API_KEY")) and shutil.which("mpg123") is not None

        if requested == "openai":
            return "openai" if has_openai else self._first_available(has_piper, has_espeak)
        if requested == "piper":
            return "piper" if has_piper else ("espeak" if has_espeak else None)
        if requested == "espeak":
            return "espeak" if has_espeak else None

        # auto: best available quality first
        if has_openai:
            return "openai"
        if has_piper:
            return "piper"
        if has_espeak:
            return "espeak"
        return None

    @staticmethod
    def _first_available(has_piper: bool, has_espeak: bool) -> str | None:
        if has_piper:
            return "piper"
        if has_espeak:
            return "espeak"
        return None
