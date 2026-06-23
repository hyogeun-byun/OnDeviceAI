from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.services.pose_similarity import group_telepathy_score
from app.services.stream_manager import StreamManager

# --- Game timing (seconds) ---
COUNTDOWN_SECONDS = 3.0
PLAY_SECONDS = 15.0
RESULT_SECONDS = 6.0

TOTAL_ROUNDS = 5

# Exponential moving average factor for smoothing the live gauge (0~1, higher = snappier).
GAUGE_EMA_ALPHA = 0.25

DEFAULT_PROMPTS: tuple[str, ...] = (
    "두 팔 번쩍! 만세 자세",
    "두 손으로 머리 위 하트",
    "권투 가드 자세",
    "생각하는 사람 (턱에 손)",
    "한 다리 들고 슈퍼맨 비행",
)

PHASE_IDLE = "idle"
PHASE_COUNTDOWN = "countdown"
PHASE_PLAYING = "playing"
PHASE_RESULT = "result"
PHASE_FINISHED = "finished"

_PHASE_DURATIONS = {
    PHASE_COUNTDOWN: COUNTDOWN_SECONDS,
    PHASE_PLAYING: PLAY_SECONDS,
    PHASE_RESULT: RESULT_SECONDS,
}


@dataclass
class GameState:
    phase: str = PHASE_IDLE
    round_index: int = 0
    phase_started_at: float = field(default_factory=time.monotonic)
    gauge: float = 0.0
    raw_gauge: float = 0.0
    ready_count: int = 0
    round_scores: list[float] = field(default_factory=list)


def telepathy_title(score: float) -> str:
    if score >= 90:
        return "운명 공동체 텔레파시"
    if score >= 75:
        return "찰떡같은 텔레파시"
    if score >= 60:
        return "제법 통하는 사이"
    if score >= 40:
        return "가끔 통하는 사이"
    if score >= 20:
        return "데면데면한 사이"
    return "서로 모르는 사이"


class GameManager:
    def __init__(
        self,
        camera_ids: tuple[str, ...],
        stream_manager: StreamManager,
        prompts: tuple[str, ...] = DEFAULT_PROMPTS,
    ) -> None:
        self._camera_ids = camera_ids
        self._stream_manager = stream_manager
        self._prompts = prompts
        self._total_rounds = min(TOTAL_ROUNDS, len(prompts))
        self._state = GameState()

    def start(self) -> None:
        self._state = GameState(
            phase=PHASE_COUNTDOWN,
            round_index=0,
            phase_started_at=time.monotonic(),
        )

    def tick(self) -> None:
        state = self._state
        now = time.monotonic()
        elapsed = now - state.phase_started_at

        if state.phase == PHASE_COUNTDOWN:
            if elapsed >= COUNTDOWN_SECONDS:
                self._enter_playing(now)
        elif state.phase == PHASE_PLAYING:
            self._update_gauge()
            if elapsed >= PLAY_SECONDS:
                self._finish_round(now)
        elif state.phase == PHASE_RESULT:
            if elapsed >= RESULT_SECONDS:
                self._advance_round(now)

    def _enter_playing(self, now: float) -> None:
        self._state.phase = PHASE_PLAYING
        self._state.phase_started_at = now
        self._state.gauge = 0.0
        self._state.raw_gauge = 0.0

    def _update_gauge(self) -> None:
        poses = [self._stream_manager.get_pose(camera_id) for camera_id in self._camera_ids]
        raw, ready = group_telepathy_score(poses)
        self._state.raw_gauge = raw
        self._state.ready_count = ready
        self._state.gauge += (raw - self._state.gauge) * GAUGE_EMA_ALPHA

    def _finish_round(self, now: float) -> None:
        self._state.round_scores.append(round(self._state.gauge, 1))
        self._state.phase = PHASE_RESULT
        self._state.phase_started_at = now

    def _advance_round(self, now: float) -> None:
        next_index = self._state.round_index + 1
        if next_index >= self._total_rounds:
            self._state.phase = PHASE_FINISHED
            self._state.phase_started_at = now
            return

        self._state.round_index = next_index
        self._state.phase = PHASE_COUNTDOWN
        self._state.phase_started_at = now
        self._state.gauge = 0.0
        self._state.raw_gauge = 0.0

    def _current_prompt(self) -> str | None:
        if self._state.phase in {PHASE_COUNTDOWN, PHASE_PLAYING, PHASE_RESULT}:
            return self._prompts[self._state.round_index]
        return None

    def _time_left(self) -> float | None:
        duration = _PHASE_DURATIONS.get(self._state.phase)
        if duration is None:
            return None
        elapsed = time.monotonic() - self._state.phase_started_at
        return max(0.0, duration - elapsed)

    def _player_status(self) -> list[dict[str, object]]:
        players: list[dict[str, object]] = []
        for index, camera_id in enumerate(self._camera_ids):
            pose = self._stream_manager.get_pose(camera_id)
            players.append(
                {
                    "camera_id": camera_id,
                    "label": f"Player {index + 1}",
                    "ready": bool(pose and pose.get("person_detected")),
                }
            )
        return players

    def snapshot(self) -> dict[str, object]:
        state = self._state
        total_score = (
            round(sum(state.round_scores) / len(state.round_scores), 1)
            if state.round_scores
            else 0.0
        )

        return {
            "phase": state.phase,
            "round_number": state.round_index + 1,
            "total_rounds": self._total_rounds,
            "prompt": self._current_prompt(),
            "gauge": round(state.gauge, 1),
            "ready_count": state.ready_count,
            "player_count": len(self._camera_ids),
            "players": self._player_status(),
            "time_left": self._time_left(),
            "phase_duration": _PHASE_DURATIONS.get(state.phase),
            "round_scores": list(state.round_scores),
            "total_score": total_score,
            "final_title": telepathy_title(total_score) if state.phase == PHASE_FINISHED else None,
        }
