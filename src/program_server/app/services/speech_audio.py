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
from typing import Iterable


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
    """Generates and caches MP3 audio for spoken lines, keyed by speech id.

    Audio is *also* cached by its text so the same line never has to hit the
    network twice. Static MC lines are pre-rendered at startup (``prewarm``) so
    short phases never wait on a runtime synthesis round-trip — that race used
    to leave the MC silent from the camera test onward when generation was slow
    or the network hiccuped.
    """

    def __init__(
        self,
        enabled: bool,
        voice: str = "ko-KR-InJoonNeural",
        rate: str = "+8%",
        max_items: int = 16,
        max_text_items: int = 96,
    ) -> None:
        self._configured = enabled
        self._voice = voice
        self._rate = rate
        self._max_items = max_items
        self._max_text_items = max_text_items
        self._store: "OrderedDict[int, bytes]" = OrderedDict()
        self._by_text: "OrderedDict[str, bytes]" = OrderedDict()

    @property
    def enabled(self) -> bool:
        return self._configured and _edge_available()

    def get(self, speech_id: int) -> bytes | None:
        return self._store.get(speech_id)

    def _remember(self, speech_id: int, data: bytes) -> None:
        self._store[speech_id] = data
        while len(self._store) > self._max_items:
            self._store.popitem(last=False)

    def _remember_text(self, key: str, data: bytes) -> None:
        self._by_text[key] = data
        while len(self._by_text) > self._max_text_items:
            self._by_text.popitem(last=False)

    async def generate(self, speech_id: int, text: str) -> None:
        if not self.enabled or not text or not text.strip():
            return
        key = text.strip()
        # Pre-rendered or previously spoken? Serve instantly, no network.
        cached = self._by_text.get(key)
        if cached is not None:
            self._remember(speech_id, cached)
            return
        try:
            data = await _synthesize(key, self._voice, self._rate)
        except Exception:
            return
        if not data:
            return
        self._remember_text(key, data)
        self._remember(speech_id, data)

    async def prewarm(self, texts: Iterable[str]) -> int:
        """Render the given static lines into the by-text cache. Returns how
        many were newly synthesized. Failures are skipped (best-effort).

        Lines are synthesized with bounded concurrency so the whole static set
        is ready in a few seconds (not one slow round-trip at a time). The
        caller should order the most time-critical lines first; even so, all
        are kicked off together here.
        """
        if not self.enabled:
            return 0
        # De-duplicate and drop anything already cached, preserving order.
        pending: list[str] = []
        seen: set[str] = set()
        for text in texts:
            if not text or not text.strip():
                continue
            key = text.strip()
            if key in seen or key in self._by_text:
                continue
            seen.add(key)
            pending.append(key)
        if not pending:
            return 0

        import asyncio

        count = 0
        semaphore = asyncio.Semaphore(4)

        async def _one(key: str) -> None:
            nonlocal count
            async with semaphore:
                try:
                    data = await _synthesize(key, self._voice, self._rate)
                except Exception:
                    return
            if data:
                self._remember_text(key, data)
                count += 1

        await asyncio.gather(*(_one(key) for key in pending))
        return count

