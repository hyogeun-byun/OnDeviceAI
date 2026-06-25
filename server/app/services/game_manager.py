from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from app.services import game_narrator as narrator
from app.services.game_narrator import DEFAULT_PROMPTS
from app.services.llm_client import LLMClient
from app.services.pose_similarity import analyze_group
from app.services.speech_audio import SpeechAudioCache
from app.services.stream_manager import StreamManager
from app.services.tts import Speaker

# --- Game timing (seconds) ---
COUNTDOWN_SECONDS = 3.0
PLAY_SECONDS = 10.0
RESULT_SECONDS = 4.0

TOTAL_ROUNDS = 5

# Exponential moving average factor for smoothing the live gauge (0~1, higher =
# snappier). Kept moderate so the *last-moment* pose still dominates the score
# but the needle doesn't jitter every frame.
GAUGE_EMA_ALPHA = 0.3

# Minimum seconds a coaching line stays on screen before it may change, so the
# AI MC doesn't rattle off a brand-new line every tick (calmer pacing).
COACH_MIN_HOLD_SECONDS = 4.0

PHASE_IDLE = "idle"
PHASE_INTRO = "intro"
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
    expressiveness: float = 0.0
    coach: str = ""
    coach_key: str = ""
    coach_changed_at: float = 0.0
    players_analysis: list[dict] = field(default_factory=list)
    round_scores: list[float] = field(default_factory=list)
    result_poses: list[dict[str, object] | None] = field(default_factory=list)
    theme: str = narrator.THEMES[0]
    prompts: list[str] = field(default_factory=lambda: list(DEFAULT_PROMPTS))
    prompt_source: str = "default"
    mc_comment: str = ""
    mc_status: str = "idle"  # idle | pending | ready
    final_report: str = ""
    final_status: str = "idle"  # idle | pending | ready
    speech: str = ""
    speech_id: int = 0


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
        llm_client: LLMClient,
        default_theme: str = narrator.THEMES[0],
        speaker: Speaker | None = None,
        mc_name: str = "민수",
        team_name: str = "",
        speech_audio: SpeechAudioCache | None = None,
    ) -> None:
        self._camera_ids = camera_ids
        self._stream_manager = stream_manager
        self._llm = llm_client
        self._default_theme = default_theme if default_theme in narrator.THEMES else narrator.THEMES[0]
        self._tts = speaker
        self._mc_name = mc_name
        self._team_name = team_name
        self._speech_audio = speech_audio
        self._total_rounds = TOTAL_ROUNDS
        self._state = GameState(theme=self._default_theme)
        # Keep references to background LLM tasks so they are not garbage collected,
        # and a generation counter to discard stale results from a previous game.
        self._tasks: set[asyncio.Task] = set()
        self._generation = 0
        # Monotonic id for spoken lines (survives across games) so the browser
        # can detect and speak each new line exactly once.
        self._speech_seq = 0

    def _speak(self, text: str) -> None:
        if not text or not text.strip():
            return
        self._speech_seq += 1
        self._state.speech = text
        self._state.speech_id = self._speech_seq
        if self._tts is not None:
            self._tts.say(text)
        # Natural neural audio for the browser (generated off the real-time path).
        if self._speech_audio is not None and self._speech_audio.enabled:
            self._spawn(self._speech_audio.generate(self._speech_seq, text))

    def start(self, theme: str | None = None) -> None:
        """Enter the MC intro screen. The actual rounds don't begin until
        :meth:`begin` is called (a separate user trigger), so the host can
        greet the players and build hype first."""
        self._generation += 1
        chosen = theme if theme in narrator.THEMES else self._default_theme
        selected_prompts = list(narrator.default_prompts(theme=chosen, n=self._total_rounds))
        self._state = GameState(
            phase=PHASE_INTRO,
            round_index=0,
            phase_started_at=time.monotonic(),
            theme=chosen,
            prompts=selected_prompts,
            prompt_source="category_random_in_theme",
        )
        # Spoken intro greeting (non-real-time: nothing is being scored yet).
        self._speak(narrator.intro_line(self._mc_name, self._team_name))
        # B. Dynamic prompts — generated in the background; until ready the
        # default prompts are used so the game can start immediately.
        if self._llm.enabled and chosen != "기본":
            self._spawn(self._build_prompts(self._generation, chosen))

    def begin(self) -> None:
        """Trigger the first round after the intro screen (separate gesture)."""
        if self._state.phase != PHASE_INTRO:
            return
        self._state.phase = PHASE_COUNTDOWN
        self._state.round_index = 0
        self._state.phase_started_at = time.monotonic()
        self._state.gauge = 0.0
        self._state.raw_gauge = 0.0
        self._state.coach = ""
        self._state.coach_key = ""
        self._state.coach_changed_at = 0.0
        self._speak(narrator.start_line(self._mc_name))

    def reset(self) -> None:
        """Abort whatever is happening and go all the way back to the idle
        screen so the host can re-pick the category and start over."""
        # Bump the generation so any in-flight background LLM/TTS work from the
        # aborted game is discarded instead of bleeding into the fresh state.
        self._generation += 1
        self._state = GameState(theme=self._default_theme)

    # ------------------------------------------------------------------ #
    # Background LLM task helpers (never awaited from tick/playing)
    # ------------------------------------------------------------------ #
    def _spawn(self, coro) -> None:
        try:
            task = asyncio.create_task(coro)
        except RuntimeError:
            # No running event loop (e.g. called outside the server). Drop the
            # background work rather than crashing the game.
            coro.close()
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _build_prompts(self, generation: int, theme: str) -> None:
        prompts = await narrator.generate_prompts(self._llm, theme, self._total_rounds)
        if generation != self._generation:
            return
        # Only apply while still on the intro screen, so the displayed prompt
        # never changes in the middle of a round once the game has begun.
        if prompts and self._state.phase == PHASE_INTRO:
            self._state.prompts = prompts
            self._state.prompt_source = "llm"

    async def _build_mc_comment(self, generation: int, round_index: int) -> None:
        state = self._state
        prompt = state.prompts[round_index] if round_index < len(state.prompts) else ""
        score = state.round_scores[round_index] if round_index < len(state.round_scores) else 0.0
        comment = await narrator.generate_mc_comment(
            self._llm,
            prompt=prompt,
            score=score,
            ready_count=state.ready_count,
            player_count=len(self._camera_ids),
        )
        # Only upgrade the on-screen text if we're still showing this round's
        # result. We do NOT re-speak: the static line was already spoken at
        # round end, and a late LLM line could otherwise bleed into the next
        # round's playing phase.
        if generation != self._generation or self._state.round_index != round_index:
            return
        if self._state.phase != PHASE_RESULT:
            return
        self._state.mc_comment = comment
        self._state.mc_status = "ready"

    async def _build_final_report(self, generation: int) -> None:
        state = self._state
        report = await narrator.generate_final_report(
            self._llm,
            prompts=list(state.prompts),
            round_scores=list(state.round_scores),
            total_score=self._average_score(),
        )
        if generation != self._generation:
            return
        self._state.final_report = report
        self._state.final_status = "ready"
        self._speak(report)


    def tick(self) -> None:
        state = self._state
        now = time.monotonic()
        elapsed = now - state.phase_started_at

        if state.phase == PHASE_COUNTDOWN:
            if elapsed >= COUNTDOWN_SECONDS:
                self._enter_playing(now)
        elif state.phase == PHASE_PLAYING:
            self._update_gauge(now)
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
        self._state.coach = ""
        self._state.coach_key = ""
        self._state.coach_changed_at = 0.0

    def _update_gauge(self, now: float) -> None:
        poses = [self._stream_manager.get_pose(camera_id) for camera_id in self._camera_ids]
        analysis = analyze_group(poses)
        self._state.raw_gauge = analysis["score"]
        self._state.ready_count = analysis["ready_count"]
        self._state.expressiveness = analysis["expressiveness"]
        self._state.players_analysis = analysis["players"]
        self._state.gauge += (analysis["score"] - self._state.gauge) * GAUGE_EMA_ALPHA
        # Live, LLM-free coaching shown on the participants' screen and read out
        # by the browser's instant voice. To keep the MC calm, a line stays put
        # for at least COACH_MIN_HOLD_SECONDS before a different category may
        # replace it (the very first line of a round shows immediately).
        coaching = narrator.coach(
            analysis["players"],
            analysis["expressiveness"],
            analysis["ready_count"],
            self._state.gauge,
            self._state.round_index,
        )
        first_line = not self._state.coach
        category_changed = coaching["key"] != self._state.coach_key
        held_long_enough = (now - self._state.coach_changed_at) >= COACH_MIN_HOLD_SECONDS
        if first_line or (category_changed and held_long_enough):
            self._state.coach = coaching["text"]
            self._state.coach_key = coaching["key"]
            self._state.coach_changed_at = now

    def _finish_round(self, now: float) -> None:
        self._state.round_scores.append(round(self._state.gauge, 1))
        self._state.result_poses = [
            self._stream_manager.get_pose(camera_id) for camera_id in self._camera_ids
        ]
        self._state.phase = PHASE_RESULT
        self._state.phase_started_at = now
        # A. Show + speak a static reaction immediately so the result screen is
        # never empty and the audio lands inside the result phase (CPU LLM is
        # too slow to reliably finish within the 6s window). If the LLM comment
        # arrives in time, it upgrades the on-screen text silently.
        score = self._state.round_scores[self._state.round_index]
        static = narrator.static_mc_comment(score, self._state.ready_count)
        self._state.mc_comment = static
        self._state.mc_status = "ready"
        self._speak(static)
        if self._llm.enabled:
            self._spawn(self._build_mc_comment(self._generation, self._state.round_index))

    def _advance_round(self, now: float) -> None:
        next_index = self._state.round_index + 1
        if next_index >= self._total_rounds:
            self._state.phase = PHASE_FINISHED
            self._state.phase_started_at = now
            # C. Final telepathy report — generated in the background.
            self._state.final_report = ""
            self._state.final_status = "pending"
            self._spawn(self._build_final_report(self._generation))
            return

        self._state.round_index = next_index
        self._state.phase = PHASE_COUNTDOWN
        self._state.phase_started_at = now
        self._state.gauge = 0.0
        self._state.raw_gauge = 0.0
        self._state.coach = ""
        self._state.coach_key = ""
        self._state.coach_changed_at = 0.0
        self._state.mc_comment = ""
        self._state.mc_status = "idle"
        self._state.result_poses = []

    def _average_score(self) -> float:
        scores = self._state.round_scores
        return round(sum(scores) / len(scores), 1) if scores else 0.0

    def _current_prompt(self) -> str | None:
        if self._state.phase in {PHASE_COUNTDOWN, PHASE_PLAYING, PHASE_RESULT}:
            prompts = self._state.prompts
            if self._state.round_index < len(prompts):
                return prompts[self._state.round_index]
        return None

    def _time_left(self) -> float | None:
        duration = _PHASE_DURATIONS.get(self._state.phase)
        if duration is None:
            return None
        elapsed = time.monotonic() - self._state.phase_started_at
        return max(0.0, duration - elapsed)

    def _player_status(self) -> list[dict[str, object]]:
        analysis = {int(p["index"]): p for p in self._state.players_analysis}
        players: list[dict[str, object]] = []
        for index, camera_id in enumerate(self._camera_ids):
            pose = self._stream_manager.get_pose(camera_id)
            info = analysis.get(index, {})
            players.append(
                {
                    "camera_id": camera_id,
                    "label": f"Player {index + 1}",
                    "ready": bool(pose and pose.get("person_detected")),
                    "sync": info.get("sync"),
                    "expressiveness": info.get("expressiveness"),
                }
            )
        return players

    def snapshot(self) -> dict[str, object]:
        state = self._state
        total_score = self._average_score()

        return {
            "phase": state.phase,
            "round_number": state.round_index + 1,
            "total_rounds": self._total_rounds,
            "prompt": self._current_prompt(),
            "gauge": round(state.gauge, 1),
            "ready_count": state.ready_count,
            "expressiveness": round(state.expressiveness, 3),
            "coach": state.coach,
            "player_count": len(self._camera_ids),
            "players": self._player_status(),
            "time_left": self._time_left(),
            "phase_duration": _PHASE_DURATIONS.get(state.phase),
            "round_scores": list(state.round_scores),
            "result_poses": list(state.result_poses) if state.phase == PHASE_RESULT else [],
            "total_score": total_score,
            "theme": state.theme,
            "prompt_source": state.prompt_source,
            "prompts": list(state.prompts[: self._total_rounds]),
            "mc_comment": state.mc_comment,
            "mc_status": state.mc_status,
            "final_report": state.final_report,
            "final_status": state.final_status,
            "speech": state.speech,
            "speech_id": state.speech_id,
            "speech_audio": bool(self._speech_audio and self._speech_audio.enabled),
            "final_title": telepathy_title(total_score) if state.phase == PHASE_FINISHED else None,
        }
