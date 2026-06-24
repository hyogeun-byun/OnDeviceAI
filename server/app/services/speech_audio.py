"""Natural neural TTS audio for the browser (edge-tts).

The MC's spoken lines are synthesized server-side with Microsoft Edge's free
neural voices and cached by ``speech_id`` so the browser can fetch and play
them on a laptop/headphones. This gives a far more natural Korean voice than
the OS-bundled Web Speech voices.

Everything degrades gracefully: if ``edge-tts`` isn't installed or the network
is unavailable, generation simply yields nothing and the browser falls back to
its own Web Speech voice.
"""

from __future__ import annotations

import importlib.util
from collections import OrderedDict


def _edge_available() -> bool:
    return importlib.util.find_spec("edge_tts") is not None


async def _synthesize(text: str, voice: str, rate: str) -> bytes | None:
    import edge_tts  # lazy import; only when actually generating

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    audio = bytearray()
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio" and chunk.get("data"):
            audio.extend(chunk["data"])
    return bytes(audio) if audio else None


class SpeechAudioCache:
    """Generates and caches MP3 audio for spoken lines, keyed by speech id."""

    def __init__(
        self,
        enabled: bool,
        voice: str = "ko-KR-InJoonNeural",
        rate: str = "+8%",
        max_items: int = 16,
    ) -> None:
        self._configured = enabled
        self._voice = voice
        self._rate = rate
        self._max_items = max_items
        self._store: "OrderedDict[int, bytes]" = OrderedDict()

    @property
    def enabled(self) -> bool:
        return self._configured and _edge_available()

    def get(self, speech_id: int) -> bytes | None:
        return self._store.get(speech_id)

    async def generate(self, speech_id: int, text: str) -> None:
        if not self.enabled or not text or not text.strip():
            return
        try:
            data = await _synthesize(text.strip(), self._voice, self._rate)
        except Exception:
            return
        if not data:
            return
        self._store[speech_id] = data
        while len(self._store) > self._max_items:
            self._store.popitem(last=False)
