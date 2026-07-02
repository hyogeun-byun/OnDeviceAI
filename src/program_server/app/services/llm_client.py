"""Lightweight async client for an Ollama / llama.cpp OpenAI-compatible endpoint.

Uses only the standard library (urllib) and runs the blocking call inside a
worker thread via ``asyncio.to_thread`` so the event loop is never blocked.
If the LLM is disabled, unreachable, or slow, every call fails gracefully and
the caller falls back to static text — the game keeps working regardless.

Pattern adapted from ``06_Pharaohs_Body_Dungeon/game/llm/client.py``.
"""

from __future__ import annotations

import asyncio
import json
import urllib.request


class LLMClient:
    def __init__(self, base_url: str, model: str, timeout: float, enabled: bool) -> None:
        self._base_url = base_url
        self._model = model
        self._timeout = timeout
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _chat_blocking(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> tuple[bool, str]:
        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self._base_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            text = body["choices"][0]["message"]["content"].strip()
            return True, text
        except Exception as error:  # noqa: BLE001 - any failure -> graceful fallback
            print(f"[llm] call failed -> fallback: {error}")
            return False, ""

    async def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 128,
        temperature: float = 0.8,
    ) -> tuple[bool, str]:
        """Return ``(ok, text)``. ``ok`` is False when disabled or on any error."""
        if not self._enabled:
            return False, ""
        return await asyncio.to_thread(
            self._chat_blocking, messages, max_tokens, temperature
        )

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.8,
    ) -> dict | None:
        """Return the first JSON object found in the response, or None on failure."""
        ok, text = await self.chat(messages, max_tokens=max_tokens, temperature=temperature)
        if not ok:
            return None
        return _extract_json(text)


def _extract_json(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except Exception:  # noqa: BLE001
        return None
    return parsed if isinstance(parsed, dict) else None
