from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from app.services import game_narrator as narrator
from app.services.game_narrator import DEFAULT_PROMPTS
from app.services.leaderboard import Leaderboard
from app.services.llm_client import LLMClient
from app.services.pose_similarity import analyze_group, detect_ready_pose
from app.services.speech_audio import SpeechAudioCache
from app.services.stream_manager import StreamManager
from app.services.tts import Speaker

# --- Game timing (seconds) ---
COUNTDOWN_SECONDS = 3.0
PLAY_SECONDS = 10.0
RESULT_SECONDS = 4.0

TOTAL_ROUNDS = 5

# How long (seconds) a player must *continuously* hold the T pose before the
# game auto-starts (prevents accidental triggers).
READY_POSE_HOLD_SECONDS = 1.5

# Hint thresholds
# Low-score hint: shown once at the START of a round when gauge <= this value
# after HINT_EARLY_AFTER_SECONDS have elapsed.
HINT_EARLY_THRESHOLD = 50.0
HINT_EARLY_AFTER_SECONDS = 3.0   # wait a bit before judging
# Late hint: shown when time_left <= this value AND gauge <= threshold.
HINT_LATE_THRESHOLD = 70.0
HINT_LATE_TIME_LEFT = 5.0
# Minimum gap (seconds) between consecutive hints so they don't spam.
HINT_MIN_GAP_SECONDS = 4.0

# Exponential moving average factor for smoothing the live gauge (0~1, higher =
# snappier). Kept moderate so the *last-moment* pose still dominates the score
# but the needle doesn't jitter every frame.
GAUGE_EMA_ALPHA = 0.3

# Minimum seconds a coaching line stays on screen before it may change, so the
# AI MC doesn't rattle off a brand-new line every tick (calmer pacing).
COACH_MIN_HOLD_SECONDS = 4.0

PHASE_IDLE = "idle"
PHASE_INTRO = "intro"
PHASE_WAITING_POSE = "waiting_pose"   # new: wait for T-pose gesture
PHASE_COUNTDOWN = "countdown"
PHASE_PLAYING = "playing"
PHASE_RESULT = "result"
PHASE_FINISHED = "finished"

_PHASE_DURATIONS = {
    PHASE_COUNTDOWN: COUNTDOWN_SECONDS,
    PHASE_PLAYING: PLAY_SECONDS,
    PHASE_RESULT: RESULT_SECONDS,
    PHASE_WAITING_POSE: None,   # open-ended; no fixed duration
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
    team_name: str = ""
    leaderboard_id: int = 0
    recorded: bool = False
    # Ready-pose detection state (used in PHASE_WAITING_POSE)
    ready_pose_hold_since: float = 0.0   # monotonic time when hold started (0 = not holding)
    ready_pose_instruction: str = narrator.READY_POSE_INSTRUCTION
    # Hint state
    hint: str = ""              # current hint text (empty = no active hint)
    hint_given_early: bool = False   # early hint already fired this round
    hint_given_late: bool = False    # late hint already fired this round
    hint_changed_at: float = 0.0     # monotonic time of last hint update


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
        leaderboard: Leaderboard | None = None,
    ) -> None:
        self._camera_ids = camera_ids
        self._stream_manager = stream_manager
        self._llm = llm_client
        self._default_theme = default_theme if default_theme in narrator.THEMES else narrator.THEMES[0]
        self._tts = speaker
        self._mc_name = mc_name
        self._team_name = team_name
        self._speech_audio = speech_audio
        self._leaderboard = leaderboard
        self._total_rounds = TOTAL_ROUNDS
        self._state = GameState(theme=self._default_theme)
        # JPEG frame captured at the exact moment each round was scored, keyed by
        # round number (1-based) -> one frame per camera. Used to reveal the real
        # photo (with the on-device pose overlaid) on the result/report screens.
        self._result_frames: dict[int, list[bytes | None]] = {}
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

    def start(self, theme: str | None = None, team_name: str | None = None) -> None:
        """Enter the MC intro screen, then transition to waiting-for-T-pose."""
        self._generation += 1
        chosen = theme if theme in narrator.THEMES else self._default_theme
        team = (team_name or "").strip() or self._team_name
        selected_prompts = list(narrator.default_prompts(theme=chosen, n=self._total_rounds))
        self._result_frames = {}
        self._state = GameState(
            phase=PHASE_INTRO,
            round_index=0,
            phase_started_at=time.monotonic(),
            theme=chosen,
            prompts=selected_prompts,
            prompt_source="category_random_in_theme",
            team_name=team,
        )
        self._speak(narrator.intro_line(self._mc_name, team))
        if self._llm.enabled and chosen != "기본":
            self._spawn(self._build_prompts(self._generation, chosen))

    def begin(self) -> None:
        """Manually trigger game start (fallback for when gesture is unavailable)."""
        if self._state.phase not in (PHASE_INTRO, PHASE_WAITING_POSE):
            return
        self._enter_countdown(time.monotonic())

    def _enter_waiting_pose(self, now: float) -> None:
        self._state.phase = PHASE_WAITING_POSE
        self._state.phase_started_at = now
        self._state.ready_pose_hold_since = 0.0
        self._speak(narrator.ready_pose_wait_line())

    def _enter_countdown(self, now: float) -> None:
        self._state.phase = PHASE_COUNTDOWN
        self._state.round_index = 0
        self._state.phase_started_at = now
        self._state.gauge = 0.0
        self._state.raw_gauge = 0.0
        self._state.coach = ""
        self._state.coach_key = ""
        self._state.coach_changed_at = 0.0
        self._speak(narrator.ready_pose_detected_line())

    def reset(self) -> None:
        """Abort whatever is happening and go all the way back to the idle
        screen so the host can re-pick the category and start over."""
        # Bump the generation so any in-flight background LLM/TTS work from the
        # aborted game is discarded instead of bleeding into the fresh state.
        self._generation += 1
        self._result_frames = {}
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

        if state.phase == PHASE_INTRO:
            # After a short greeting window, move to waiting-for-T-pose.
            if elapsed >= 2.0:
                self._enter_waiting_pose(now)
        elif state.phase == PHASE_WAITING_POSE:
            self._check_ready_pose(now)
        elif state.phase == PHASE_COUNTDOWN:
            if elapsed >= COUNTDOWN_SECONDS:
                self._enter_playing(now)
        elif state.phase == PHASE_PLAYING:
            self._update_gauge(now)
            if elapsed >= PLAY_SECONDS:
                self._finish_round(now)
        elif state.phase == PHASE_RESULT:
            if elapsed >= RESULT_SECONDS:
                self._advance_round(now)

    def _check_ready_pose(self, now: float) -> None:
        """Detect T-pose from all present players; start when all hold it."""
        poses = [self._stream_manager.get_pose(cid) for cid in self._camera_ids]
        present = [p for p in poses if p and p.get("person_detected")]
        if not present:
            self._state.ready_pose_hold_since = 0.0
            return

        all_ready = all(detect_ready_pose(p) for p in present)
        if all_ready:
            if self._state.ready_pose_hold_since == 0.0:
                self._state.ready_pose_hold_since = now
            elif now - self._state.ready_pose_hold_since >= READY_POSE_HOLD_SECONDS:
                self._enter_countdown(now)
        else:
            self._state.ready_pose_hold_since = 0.0

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
        # Live coaching
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

        # Hints
        self._update_hint(now, analysis)

    def _update_hint(self, now: float, analysis: dict) -> None:
        """Fire early/late hints based on gauge and time remaining."""
        elapsed = now - self._state.phase_started_at
        time_left = max(0.0, PLAY_SECONDS - elapsed)
        gauge = self._state.gauge
        players = analysis.get("players", [])
        hint_gap_ok = (now - self._state.hint_changed_at) >= HINT_MIN_GAP_SECONDS

        # Early hint: score still ≤50 after 3 seconds
        if (
            not self._state.hint_given_early
            and elapsed >= HINT_EARLY_AFTER_SECONDS
            and gauge <= HINT_EARLY_THRESHOLD
            and hint_gap_ok
        ):
            self._state.hint_given_early = True
            hint_text = self._build_hint_text(players) or narrator.hint_group_low()
            self._set_hint(hint_text, now)
            return

        # Late hint: 5s remaining and score still ≤70
        if (
            not self._state.hint_given_late
            and time_left <= HINT_LATE_TIME_LEFT
            and gauge <= HINT_LATE_THRESHOLD
            and hint_gap_ok
        ):
            self._state.hint_given_late = True
            hint_text = self._build_hint_text(players)
            if hint_text:
                self._set_hint(hint_text, now)

    def _build_hint_text(self, players: list[dict]) -> str:
        """Find the player with the lowest sync score and the most-deviant joint."""
        # Pick the outlier player (lowest sync vs the rest)
        present = [p for p in players if p.get("present") and p.get("sync") is not None]
        if len(present) < 2:
            return ""
        outlier = min(present, key=lambda p: float(p["sync"]))
        others_avg = sum(float(p["sync"]) for p in present if p is not outlier) / (len(present) - 1)
        if others_avg - float(outlier["sync"]) < 10.0:
            return ""  # everyone is close enough, no specific hint

        player_number = int(outlier["index"]) + 1

        # Find which joint contributes most to the outlier's deviation.
        # We compare the outlier's pose angles to the others' average angles.
        outlier_idx = int(outlier["index"])
        outlier_pose = self._stream_manager.get_pose(self._camera_ids[outlier_idx])
        other_poses = [
            self._stream_manager.get_pose(self._camera_ids[int(p["index"])])
            for p in present if p is not outlier
        ]

        from app.services.pose_similarity import compute_joint_angles
        if not outlier_pose:
            return narrator.hint_for_player(player_number, "팔 동작")

        outlier_angles = compute_joint_angles(outlier_pose)
        other_angles_list = [compute_joint_angles(p) for p in other_poses if p]
        if not other_angles_list:
            return narrator.hint_for_player(player_number, "팔 동작")

        # Average the other players' angles per joint
        joint_diffs: dict[str, float] = {}
        for joint, angle in outlier_angles.items():
            others = [a[joint] for a in other_angles_list if joint in a]
            if others:
                avg_other = sum(others) / len(others)
                joint_diffs[joint] = abs(angle - avg_other)

        if not joint_diffs:
            return narrator.hint_for_player(player_number, "자세")

        worst_joint = max(joint_diffs, key=lambda j: joint_diffs[j])
        return narrator.hint_for_player(player_number, worst_joint)

    def _set_hint(self, text: str, now: float) -> None:
        self._state.hint = text
        self._state.hint_changed_at = now
        self._speak(text)

    def _finish_round(self, now: float) -> None:
        self._state.round_scores.append(round(self._state.gauge, 1))
        self._state.result_poses = [
            self._stream_manager.get_pose(camera_id) for camera_id in self._camera_ids
        ]
        # Freeze the live camera frame at the scored instant so the result screen
        # can reveal the real photo (the pose snapshot above was taken from the
        # same frame, so the overlaid skeleton lines up exactly).
        round_number = self._state.round_index + 1
        self._result_frames[round_number] = [
            self._stream_manager.get_frame(camera_id) for camera_id in self._camera_ids
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
            # Persist the final team score to the leaderboard (once per game).
            self._record_result()
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
        self._state.hint = ""
        self._state.hint_given_early = False
        self._state.hint_given_late = False
        self._state.hint_changed_at = 0.0

    def _average_score(self) -> float:
        scores = self._state.round_scores
        return round(sum(scores) / len(scores), 1) if scores else 0.0

    def get_result_frame(self, round_number: int, player_index: int) -> bytes | None:
        """Return the JPEG frame captured when ``round_number`` (1-based) was
        scored for the given player, or ``None`` if it is unavailable."""
        frames = self._result_frames.get(round_number)
        if not frames or not 0 <= player_index < len(frames):
            return None
        return frames[player_index]

    def _record_result(self) -> None:
        """Save the finished game's team score to the leaderboard exactly once."""
        if self._leaderboard is None or self._state.recorded:
            return
        self._state.recorded = True
        total = self._average_score()
        try:
            self._state.leaderboard_id = self._leaderboard.add(
                team_name=self._state.team_name,
                score=total,
                title=telepathy_title(total),
                theme=self._state.theme,
                round_scores=list(self._state.round_scores),
            )
        except Exception as exc:  # pragma: no cover - DB failure must not crash the game
            print(f"[leaderboard] failed to record result: {exc}")

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
            "hint": state.hint,
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
            "team_name": state.team_name,
            "leaderboard_id": state.leaderboard_id,
            "ready_pose_instruction": state.ready_pose_instruction,
            "ready_pose_hold_progress": (
                min(1.0, (time.monotonic() - state.ready_pose_hold_since) / READY_POSE_HOLD_SECONDS)
                if state.phase == PHASE_WAITING_POSE and state.ready_pose_hold_since > 0
                else 0.0
            ),
        }
