from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from app.services import game_narrator as narrator
from app.services.game_narrator import DEFAULT_PROMPTS
from app.services.leaderboard import Leaderboard
from app.services.llm_client import LLMClient
from app.services.pose_similarity import analyze_group, detect_arm_raised, detect_cheer_pose, detect_ready_pose
from app.services.speech_audio import SpeechAudioCache
from app.services.stream_manager import StreamManager
from app.services.tts import Speaker

# --- Game timing (seconds) ---
COUNTDOWN_SECONDS = 3.0
GAME_TOTAL_SECONDS = 60.0    # whole game is a 60s sprint: clear as many as you can
PLAY_PASS_SCORE = 90.0       # reach this and the current prompt clears; next one loads
CLEAR_FLASH_SECONDS = 1.6    # brief celebration of the cleared prompt before the next
PROMPT_HINT_SECONDS = 10.0   # stuck on a prompt this long -> flash the big camera images
PROMPT_MAX_SECONDS = 20.0    # give up on a prompt after this long and load a fresh one
PEEK_DURATION_SECONDS = 1.5  # how long the camera-image hint stays on screen
RESULT_SECONDS = 6.0
PLAY_MAX_SECONDS = GAME_TOTAL_SECONDS  # legacy alias for hint timing math

# How long the MC opening (intro) screen shows before the countdown auto-starts.
INTRO_SECONDS = 6.0
# Estimated speaking pace so the intro waits for the MC to finish the opening
# line (instead of cutting off). Duration scales with the line length, clamped.
INTRO_CHAR_SECONDS = 0.19
INTRO_MIN_SECONDS = 6.0
INTRO_MAX_SECONDS = 50.0

TOTAL_ROUNDS = 5  # not used as a hard cap anymore; sprint runs until time is up

# How long (seconds) a player must hold the T pose (within the tolerance window)
# before the game auto-starts (prevents accidental triggers).
READY_POSE_HOLD_SECONDS = 1.5
# Keypoint jitter tolerance: brief dropouts shorter than this are ignored so
# intermittent keypoint loss does not reset the hold timer.
READY_POSE_GAP_TOLERANCE = 0.8

# Body-controlled category picker: raise one hand to step, hold T-pose to confirm.
# Cooldown between hand-raise steps so one raise = one move (not a fast scroll).
CATEGORY_STEP_COOLDOWN = 0.9
# Hold the T-pose this long in the picker to confirm the highlighted category.
CATEGORY_CONFIRM_SECONDS = 1.2

# Camera test (PHASE_CAMTEST): each player holds the test pose so they can see
# they're framed before the game. Hold this long per camera to mark it OK.
CAMTEST_HOLD_SECONDS = 0.8
# After every connected camera has passed, linger this long so the green
# "통과!" overlay is actually visible before moving on to the completion line.
CAMTEST_REVEAL_SECONDS = 1.4

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
PHASE_CATEGORY = "category"          # body-controlled category picker
PHASE_CATPICK = "catpick"           # spoken "you picked X" line before camtest
PHASE_INTRO = "intro"
PHASE_CAMTEST = "camtest"            # 3-camera framing check before the game
PHASE_CONFIRM = "confirm"          # spoken category-confirm lines before countdown
PHASE_WAITING_POSE = "waiting_pose"   # new: wait for T-pose gesture
PHASE_COUNTDOWN = "countdown"
PHASE_PLAYING = "playing"
PHASE_RESULT = "result"
PHASE_FINISHED = "finished"

_PHASE_DURATIONS = {
    PHASE_COUNTDOWN: COUNTDOWN_SECONDS,
    PHASE_PLAYING: PLAY_MAX_SECONDS,
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
    # --- 60s sprint state ---
    game_started_at: float = 0.0        # monotonic time the sprint clock started
    cleared_count: int = 0              # how many prompts matched (90+) so far
    clear_times: list[float] = field(default_factory=list)  # elapsed at each clear
    peek_until: float = 0.0             # while now < this, flash the big camera-image hint
    hint_cam_shown: bool = False        # camera-image hint already fired for this prompt
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
    intro_seconds: float = INTRO_SECONDS  # how long the intro waits (set per-line)
    # Guided intro tour state
    tour_steps: list[dict[str, str]] = field(default_factory=list)
    tour_index: int = 0
    tour_target: str = ""
    # Category-confirm spoken sequence
    confirm_lines: list[str] = field(default_factory=list)
    confirm_index: int = 0
    # Category picker (PHASE_CATEGORY) state
    category_index: int = 0
    category_step_at: float = 0.0       # monotonic time of the last hand-raise step
    category_confirm_since: float = 0.0  # monotonic time the T-pose hold started
    category_armed: bool = False        # True once the start T-pose was released
    category_step_neutral: bool = True  # arm must return to neutral before next step
    # Camera-test (PHASE_CAMTEST) state
    camtest_pose: str = "만세 포즈"
    camtest_pass: list[str] = field(default_factory=list)  # camera_ids that passed
    camtest_chime: int = 0                                 # bumps on each new pass (chime cue)
    camtest_hold: dict[str, float] = field(default_factory=dict)  # camera_id -> hold-start time
    camtest_all_passed_at: float = 0.0  # monotonic time every connected cam passed (0 = not yet)
    # Ready-pose detection state (used in PHASE_WAITING_POSE)
    ready_pose_hold_since: float = 0.0   # monotonic time when hold started (0 = not holding)
    ready_pose_last_seen: float = 0.0    # monotonic time of last successful T-pose detection
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


def sprint_title(cleared: int) -> str:
    if cleared >= 10:
        return "운명 공동체 텔레파시"
    if cleared >= 7:
        return "찰떡같은 텔레파시"
    if cleared >= 5:
        return "제법 통하는 사이"
    if cleared >= 3:
        return "가끔 통하는 사이"
    if cleared >= 1:
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
        # Team name / theme staged from the idle screen so the T-pose gesture can
        # auto-start the game without a button press.
        self._pending_team_name = team_name
        self._pending_theme = self._default_theme
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
        opening = narrator.intro_line(self._mc_name, team, chosen)
        self._state.tour_steps = narrator.intro_tour(chosen)
        self._state.tour_index = -1  # -1 = still on the opening greeting
        self._state.tour_target = "intro"
        self._state.intro_seconds = max(
            INTRO_MIN_SECONDS,
            min(INTRO_MAX_SECONDS, len(opening) * INTRO_CHAR_SECONDS + 2.0),
        )
        self._speak(opening)
        if self._llm.enabled and chosen != "기본":
            self._spawn(self._build_prompts(self._generation, chosen))

    def stage(self, team_name: str | None = None, theme: str | None = None) -> None:
        """Remember the team name / theme entered on the idle screen so the
        T-pose gesture can auto-start the game without any button."""
        if team_name is not None:
            self._pending_team_name = team_name.strip()[:40]
        if theme is not None and theme in narrator.THEMES:
            self._pending_theme = theme

    def begin(self) -> None:
        """Manually trigger game start (fallback for when gesture is unavailable)."""
        if self._state.phase not in (PHASE_INTRO, PHASE_WAITING_POSE):
            return
        self._enter_countdown(time.monotonic())

    def skip_intro(self) -> None:
        """Skip the MC explanation and go straight to the category picker.
        Triggered by a held T-pose during the intro, or the on-screen button."""
        if self._state.phase in (PHASE_INTRO, PHASE_WAITING_POSE):
            self._enter_category(time.monotonic())

    def _check_intro_skip_pose(self, now: float) -> None:
        """Hold a T-pose during the explanation to skip straight to category."""
        poses = [self._stream_manager.get_pose(cid) for cid in self._camera_ids]
        present = [p for p in poses if p and p.get("person_detected")]
        if present and any(detect_ready_pose(p) for p in present):
            self._state.ready_pose_last_seen = now
            if self._state.ready_pose_hold_since == 0.0:
                self._state.ready_pose_hold_since = now
            elif now - self._state.ready_pose_hold_since >= READY_POSE_HOLD_SECONDS:
                self.skip_intro()
        elif self._state.ready_pose_hold_since > 0.0:
            if (now - self._state.ready_pose_last_seen) > READY_POSE_GAP_TOLERANCE:
                self._state.ready_pose_hold_since = 0.0


    def confirm_category(self) -> None:
        """Lock in the highlighted category and start the confirm → countdown
        sequence. Shared by the T-pose gesture and the manual button."""
        if self._state.phase != PHASE_CATEGORY:
            return
        themes = list(narrator.THEMES)
        if not themes:
            self.start(self._pending_theme, self._pending_team_name)
            return
        chosen = themes[self._state.category_index % len(themes)]
        self._state.theme = chosen
        self._state.prompts = list(narrator.default_prompts(theme=chosen, n=self._total_rounds))
        self._state.prompt_source = "category_random_in_theme"
        self._enter_catpick(time.monotonic(), chosen)

    def _enter_catpick(self, now: float, theme: str) -> None:
        """Announce the chosen category and wait for the line to finish before
        moving to the camera test (so the MC isn't cut off mid-sentence)."""
        self._state.phase = PHASE_CATPICK
        self._state.phase_started_at = now
        self._state.theme = theme
        line = narrator.category_picked_line(theme)
        self._state.intro_seconds = max(
            INTRO_MIN_SECONDS, min(INTRO_MAX_SECONDS, len(line) * INTRO_CHAR_SECONDS + 1.0)
        )
        self._speak(line)

    def step_category(self, direction: int) -> None:
        """Move the category highlight (manual button fallback for hand-raise)."""
        if self._state.phase != PHASE_CATEGORY:
            return
        n = len(narrator.THEMES)
        if n:
            self._state.category_index = (self._state.category_index + direction) % n
            self._state.category_armed = True


    def _enter_waiting_pose(self, now: float) -> None:
        self._state.phase = PHASE_WAITING_POSE
        self._state.phase_started_at = now
        self._state.ready_pose_hold_since = 0.0
        self._state.ready_pose_last_seen = 0.0
        self._speak(narrator.ready_pose_wait_line())

    def _enter_category(self, now: float) -> None:
        """After the T-pose start, open the body-controlled category picker."""
        try:
            start_index = list(narrator.THEMES).index(self._pending_theme)
        except ValueError:
            start_index = 0
        self._state = GameState(
            phase=PHASE_CATEGORY,
            phase_started_at=now,
            theme=self._pending_theme,
            team_name=self._pending_team_name,
            category_index=start_index,
        )
        self._speak(narrator.category_select_line())

    def intro_done(self) -> None:
        """Frontend signal that the MC finished reading the current intro line.

        The opening greeting plays first, then the guided tour walks through
        each part of the screen (제시어 → 게이지 → 힌트 → 준비). When all the
        tour steps are done, the countdown begins."""
        if self._state.phase == PHASE_CONFIRM:
            self._advance_confirm(time.monotonic())
            return
        if self._state.phase != PHASE_INTRO:
            if self._state.phase == PHASE_WAITING_POSE:
                self._enter_countdown(time.monotonic())
            return
        next_index = self._state.tour_index + 1
        steps = self._state.tour_steps
        if 0 <= next_index < len(steps):
            step = steps[next_index]
            self._state.tour_index = next_index
            self._state.tour_target = step.get("target", "")
            line = step.get("text", "")
            self._state.intro_seconds = max(
                INTRO_MIN_SECONDS,
                min(INTRO_MAX_SECONDS, len(line) * INTRO_CHAR_SECONDS + 1.0),
            )
            self._state.phase_started_at = time.monotonic()
            self._speak(line)
        else:
            self._enter_category(time.monotonic())

    def _enter_camtest(self, now: float, theme: str) -> None:
        """After the category is locked in, run a 3-camera framing check so each
        player can confirm they're visible. Each camera passes when its player
        holds the test pose; once all cameras pass we move to the countdown."""
        self._state.phase = PHASE_CAMTEST
        self._state.phase_started_at = now
        self._state.theme = theme
        self._state.camtest_pass = []
        self._state.camtest_chime = 0
        self._state.camtest_hold = {}
        self._state.camtest_all_passed_at = 0.0
        self._speak(narrator.camtest_intro_line(theme))

    def _check_camtest(self, now: float) -> None:
        """Mark each camera as OK once its player holds the test pose, with a
        chime cue per new pass. When every CONNECTED camera has passed (cameras
        with no feed are ignored), proceed."""
        passed = set(self._state.camtest_pass)
        connected: list[str] = []
        for cid in self._camera_ids:
            pose = self._stream_manager.get_pose(cid)
            present = bool(pose and pose.get("person_detected"))
            if present:
                connected.append(cid)
            if cid in passed:
                continue
            if present and detect_cheer_pose(pose):
                start = self._state.camtest_hold.get(cid)
                if start is None:
                    self._state.camtest_hold[cid] = now
                elif now - start >= CAMTEST_HOLD_SECONDS:
                    self._state.camtest_pass.append(cid)
                    self._state.camtest_chime += 1
            else:
                self._state.camtest_hold.pop(cid, None)
        # Proceed once every currently-connected camera has passed (at least 1),
        # but linger briefly first so the green "통과!" overlay is actually seen
        # (otherwise the phase would flip in the same tick the last cam passes).
        if connected and all(cid in self._state.camtest_pass for cid in connected):
            if self._state.camtest_all_passed_at <= 0.0:
                self._state.camtest_all_passed_at = now
            elif now - self._state.camtest_all_passed_at >= CAMTEST_REVEAL_SECONDS:
                self._enter_confirm(now, self._state.theme)
        else:
            # A camera dropped out before the reveal finished — reset the timer.
            self._state.camtest_all_passed_at = 0.0

    def skip_camtest(self) -> None:
        """Manual fallback: mark all cameras OK and move straight to countdown."""
        if self._state.phase != PHASE_CAMTEST:
            return
        self._enter_confirm(time.monotonic(), self._state.theme)

    def _enter_countdown(self, now: float, speak: bool = True) -> None:
        self._state.phase = PHASE_COUNTDOWN
        self._state.round_index = 0
        self._state.phase_started_at = now
        self._state.gauge = 0.0
        self._state.raw_gauge = 0.0
        self._state.coach = ""
        self._state.coach_key = ""
        self._state.coach_changed_at = 0.0
        if speak:
            self._speak(narrator.ready_pose_detected_line())

    def _enter_confirm(self, now: float, theme: str) -> None:
        """Play the two confirm lines one after another, then count down."""
        self._state.phase = PHASE_CONFIRM
        self._state.phase_started_at = now
        self._state.confirm_lines = narrator.category_confirm_lines(theme)
        self._state.confirm_index = 0
        line = self._state.confirm_lines[0]
        self._state.intro_seconds = max(
            INTRO_MIN_SECONDS, min(INTRO_MAX_SECONDS, len(line) * INTRO_CHAR_SECONDS + 1.0)
        )
        self._speak(line)

    def _advance_confirm(self, now: float) -> None:
        next_index = self._state.confirm_index + 1
        if next_index < len(self._state.confirm_lines):
            self._state.confirm_index = next_index
            line = self._state.confirm_lines[next_index]
            self._state.phase_started_at = now
            self._state.intro_seconds = max(
                INTRO_MIN_SECONDS, min(INTRO_MAX_SECONDS, len(line) * INTRO_CHAR_SECONDS + 1.0)
            )
            self._speak(line)
        else:
            self._enter_countdown(now, speak=False)


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


    async def tick(self) -> None:
        state = self._state
        now = time.monotonic()
        elapsed = now - state.phase_started_at

        if state.phase == PHASE_IDLE:
            # On the idle screen, holding the T-pose (after a team name is
            # entered) auto-starts the game — no button needed.
            self._check_idle_ready_pose(now)
        elif state.phase == PHASE_CATEGORY:
            self._check_category_gesture(now)
        elif state.phase == PHASE_CATPICK:
            # Hold on the category screen until the "you picked X" line finishes.
            if elapsed >= state.intro_seconds:
                self._enter_camtest(now, state.theme)
        elif state.phase == PHASE_CAMTEST:
            self._check_camtest(now)
        elif state.phase in (PHASE_INTRO, PHASE_WAITING_POSE):
            # The MC plays the opening; the browser signals when speech ends
            # (intro_done). intro_seconds is only a fallback cap so it can never
            # get stuck if the audio fails.
            self._check_intro_skip_pose(now)
            if elapsed >= state.intro_seconds:
                self.intro_done()
        elif state.phase == PHASE_CONFIRM:
            if elapsed >= state.intro_seconds:
                self._advance_confirm(now)
        elif state.phase == PHASE_COUNTDOWN:
            if elapsed >= COUNTDOWN_SECONDS:
                self._enter_playing(now)
        elif state.phase == PHASE_PLAYING:
            await self._update_gauge(now)
            game_elapsed = now - state.game_started_at
            prompt_elapsed = now - state.phase_started_at
            # Stuck on this prompt for 10s? Flash the big camera images once as a
            # hint so the team can see each other and sync up.
            if (
                not state.hint_cam_shown
                and prompt_elapsed >= PROMPT_HINT_SECONDS
                and game_elapsed < GAME_TOTAL_SECONDS
            ):
                state.hint_cam_shown = True
                state.peek_until = now + PEEK_DURATION_SECONDS
            # 60s sprint clock: when it runs out, the game is over.
            if game_elapsed >= GAME_TOTAL_SECONDS:
                self._advance_round(now)
            elif state.gauge >= PLAY_PASS_SCORE:
                self._finish_round(now)
            elif prompt_elapsed >= PROMPT_MAX_SECONDS:
                # Couldn't match within 20s — give up and load a fresh prompt
                # (not counted as a clear) so the sprint keeps moving.
                self._next_prompt(now)
        elif state.phase == PHASE_RESULT:
            if (now - state.game_started_at) >= GAME_TOTAL_SECONDS:
                self._advance_round(now)
            elif elapsed >= CLEAR_FLASH_SECONDS:
                self._next_prompt(now)


    def _check_idle_ready_pose(self, now: float) -> None:
        """On the idle screen, detect the T-pose and auto-start the game.

        Requires a staged (entered) team name so the game never starts by
        accident before the players have set themselves up. Once a team name is
        set, ANY single present player holding the T-pose for the hold window
        triggers the start (gap-tolerant against brief keypoint dropouts).
        """
        if not self._pending_team_name:
            self._state.ready_pose_hold_since = 0.0
            return
        poses = [self._stream_manager.get_pose(cid) for cid in self._camera_ids]
        present = [p for p in poses if p and p.get("person_detected")]
        if not present:
            if (now - self._state.ready_pose_last_seen) > READY_POSE_GAP_TOLERANCE:
                self._state.ready_pose_hold_since = 0.0
            return
        if any(detect_ready_pose(p) for p in present):
            self._state.ready_pose_last_seen = now
            if self._state.ready_pose_hold_since == 0.0:
                self._state.ready_pose_hold_since = now
            elif now - self._state.ready_pose_hold_since >= READY_POSE_HOLD_SECONDS:
                self.start(self._pending_theme, self._pending_team_name)
        else:
            if self._state.ready_pose_hold_since > 0.0:
                if (now - self._state.ready_pose_last_seen) > READY_POSE_GAP_TOLERANCE:
                    self._state.ready_pose_hold_since = 0.0

    def _check_category_gesture(self, now: float) -> None:
        """Body-controlled category picker: one raised hand steps the highlight,
        a held T-pose confirms and starts the game."""
        themes = list(narrator.THEMES)
        if not themes:
            self.start(self._pending_theme, self._pending_team_name)
            return
        poses = [self._stream_manager.get_pose(cid) for cid in self._camera_ids]
        present = [p for p in poses if p and p.get("person_detected")]
        if not present:
            self._state.category_confirm_since = 0.0
            self._state.category_armed = True
            return
        # Confirm: any player holds the T-pose for the confirm window. The start
        # T-pose must be released first (armed) so the picker doesn't instantly
        # confirm the moment it opens.
        if any(detect_ready_pose(p) for p in present):
            if not self._state.category_armed:
                self._state.category_confirm_since = 0.0
                return
            if self._state.category_confirm_since == 0.0:
                self._state.category_confirm_since = now
            elif now - self._state.category_confirm_since >= CATEGORY_CONFIRM_SECONDS:
                self.confirm_category()
            return
        self._state.category_confirm_since = 0.0
        self._state.category_armed = True
        # Step: one raised hand moves the highlight by exactly one per raise.
        # Edge-triggered: the arm must drop back to neutral before it can step
        # again, so holding it out doesn't scroll runaway through the list.
        direction = next((d for d in (detect_arm_raised(p) for p in present) if d), None)
        if direction is None:
            self._state.category_step_neutral = True
            return
        if not self._state.category_step_neutral:
            return
        if now - self._state.category_step_at < CATEGORY_STEP_COOLDOWN:
            return
        if direction == "right":
            self._state.category_index = (self._state.category_index + 1) % len(themes)
        elif direction == "left":
            self._state.category_index = (self._state.category_index - 1) % len(themes)
        self._state.category_step_at = now
        self._state.category_step_neutral = False

    def _check_ready_pose(self, now: float) -> None:
        """Detect T-pose from any present player; start when at least one holds it.

        Gap-tolerant: keypoint dropouts shorter than READY_POSE_GAP_TOLERANCE
        seconds do not reset the hold timer, so intermittent frame loss does not
        block the start trigger.
        Only called when a team name is already set.  The start button
        (begin()) is always an alternative — this is the gesture path.
        """
        poses = [self._stream_manager.get_pose(cid) for cid in self._camera_ids]
        present = [p for p in poses if p and p.get("person_detected")]
        if not present:
            # No person in frame at all — only reset if gap exceeds tolerance.
            if (now - self._state.ready_pose_last_seen) > READY_POSE_GAP_TOLERANCE:
                self._state.ready_pose_hold_since = 0.0
            return

        any_ready = any(detect_ready_pose(p) for p in present)
        if any_ready:
            self._state.ready_pose_last_seen = now
            if self._state.ready_pose_hold_since == 0.0:
                self._state.ready_pose_hold_since = now
            elif now - self._state.ready_pose_hold_since >= READY_POSE_HOLD_SECONDS:
                self._enter_countdown(now)
        else:
            # T-pose not detected this tick — tolerate brief gaps.
            if self._state.ready_pose_hold_since > 0.0:
                if (now - self._state.ready_pose_last_seen) > READY_POSE_GAP_TOLERANCE:
                    self._state.ready_pose_hold_since = 0.0

    def _enter_playing(self, now: float) -> None:
        self._state.phase = PHASE_PLAYING
        self._state.phase_started_at = now
        self._state.gauge = 0.0
        self._state.raw_gauge = 0.0
        self._state.coach = ""
        self._state.coach_key = ""
        self._state.coach_changed_at = 0.0
        # Each prompt gets a fresh camera-hint timer.
        self._state.hint_cam_shown = False
        self._state.peek_until = 0.0
        # Kick off the 60s sprint clock the first time we start playing.
        if self._state.game_started_at <= 0.0:
            self._state.game_started_at = now
            self._state.cleared_count = 0
            self._state.clear_times = []

    def _next_prompt(self, now: float) -> None:
        """After clearing a prompt, advance to the next one and resume playing."""
        next_index = self._state.round_index + 1
        # Cycle prompts so the 60s sprint never runs out of cards.
        if self._state.prompts and next_index >= len(self._state.prompts):
            next_index = 0
        self._state.round_index = next_index
        self._state.result_poses = []
        self._state.hint = ""
        self._state.hint_given_early = False
        self._state.hint_given_late = False
        self._state.hint_changed_at = 0.0
        self._enter_playing(now)


    async def _update_gauge(self, now: float) -> None:
        poses = [self._stream_manager.get_pose(camera_id) for camera_id in self._camera_ids]
        loop = asyncio.get_event_loop()
        analysis = await loop.run_in_executor(None, analyze_group, poses)
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
            # Speak coaching in the same MC voice (edge-tts) as the intro/result
            # lines. This only fires on category changes (throttled), so it stays
            # off the real-time path while keeping one consistent host voice.
            self._speak(coaching["text"])

        # Hints
        self._update_hint(now, analysis)

    def _update_hint(self, now: float, analysis: dict) -> None:
        """Fire early/late hints based on gauge and time remaining."""
        elapsed = now - self._state.phase_started_at
        time_left = max(0.0, PLAY_MAX_SECONDS - elapsed)
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

        # Find which bone contributes most to the outlier's deviation.
        # We compare the outlier's bone directions to the others' bone directions.
        outlier_idx = int(outlier["index"])
        outlier_pose = self._stream_manager.get_pose(self._camera_ids[outlier_idx])
        other_poses = [
            self._stream_manager.get_pose(self._camera_ids[int(p["index"])])
            for p in present if p is not outlier
        ]

        from app.services.pose_similarity import (
            bone_vector_angle_difference_degrees,
            compute_bone_vectors,
        )
        if not outlier_pose:
            return narrator.hint_for_player(player_number, "팔 동작")

        outlier_vectors = compute_bone_vectors(outlier_pose)
        other_vectors_list = [compute_bone_vectors(p) for p in other_poses if p]
        if not other_vectors_list:
            return narrator.hint_for_player(player_number, "팔 동작")

        bone_diffs: dict[str, float] = {}
        for bone, vector in outlier_vectors.items():
            others = [v[bone] for v in other_vectors_list if bone in v]
            if others:
                diffs = [
                    bone_vector_angle_difference_degrees(vector, other)
                    for other in others
                ]
                bone_diffs[bone] = sum(diffs) / len(diffs)

        if not bone_diffs:
            return narrator.hint_for_player(player_number, "자세")

        worst_bone = max(bone_diffs, key=lambda bone: bone_diffs[bone])
        return narrator.hint_for_player(player_number, worst_bone)

    def _set_hint(self, text: str, now: float) -> None:
        self._state.hint = text
        self._state.hint_changed_at = now
        self._speak(text)

    def _finish_round(self, now: float) -> None:
        self._state.round_scores.append(round(self._state.gauge, 1))
        # A prompt was cleared: count it and remember how fast (sprint clock).
        self._state.cleared_count += 1
        self._state.clear_times.append(round(now - self._state.game_started_at, 1))
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
        # In sprint mode this is only called when the 60s clock runs out.
        self._state.phase = PHASE_FINISHED
        self._state.phase_started_at = now
        # Persist the final team score to the leaderboard (once per game).
        self._record_result()
        # C. Final telepathy report — generated in the background.
        self._state.final_report = ""
        self._state.final_status = "pending"
        self._speak(narrator.report_wait_line())
        self._spawn(self._build_final_report(self._generation))

    def _average_score(self) -> float:
        # Sprint score = number of prompts cleared in 60s.
        return float(self._state.cleared_count)

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
        # Tie-break: time of the last clear (faster = better); 0 if no clears.
        total_time = self._state.clear_times[-1] if self._state.clear_times else 0.0
        try:
            self._state.leaderboard_id = self._leaderboard.add(
                team_name=self._state.team_name,
                score=total,
                title=sprint_title(int(total)),
                theme=self._state.theme,
                round_scores=list(self._state.round_scores),
                total_time=total_time,
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
        now = time.monotonic()
        # 60s sprint clock (only meaningful once playing has started).
        game_time_left: float | None = None
        if state.game_started_at > 0.0:
            game_time_left = max(0.0, GAME_TOTAL_SECONDS - (now - state.game_started_at))
        show_hint_cams = state.phase == PHASE_PLAYING and now < state.peek_until

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
            "game_time_left": game_time_left,
            "game_total": GAME_TOTAL_SECONDS,
            "cleared_count": state.cleared_count,
            "show_hint_cams": show_hint_cams,
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
            "tour_target": state.tour_target if state.phase == PHASE_INTRO else "",
            "tour_index": state.tour_index if state.phase == PHASE_INTRO else 0,
            "tour_total": len(state.tour_steps) if state.phase == PHASE_INTRO else 0,
            "final_title": sprint_title(int(total_score)) if state.phase == PHASE_FINISHED else None,
            "team_name": state.team_name,
            "leaderboard_id": state.leaderboard_id,
            "ready_pose_instruction": state.ready_pose_instruction,
            "category_options": list(narrator.THEMES),
            "category_index": state.category_index,
            "category_confirm_progress": (
                min(1.0, (time.monotonic() - state.category_confirm_since) / CATEGORY_CONFIRM_SECONDS)
                if state.phase == PHASE_CATEGORY and state.category_confirm_since > 0
                else 0.0
            ),
            "ready_pose_hold_progress": (
                min(1.0, (time.monotonic() - state.ready_pose_hold_since) / READY_POSE_HOLD_SECONDS)
                if state.phase in (PHASE_IDLE, PHASE_WAITING_POSE) and state.ready_pose_hold_since > 0
                else 0.0
            ),
            "camtest_pose": state.camtest_pose if state.phase == PHASE_CAMTEST else "",
            "camtest_pass": list(state.camtest_pass) if state.phase == PHASE_CAMTEST else [],
            "camtest_chime": state.camtest_chime if state.phase == PHASE_CAMTEST else 0,
        }
