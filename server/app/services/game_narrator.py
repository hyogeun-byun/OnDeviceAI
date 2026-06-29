"""LLM-backed game narration: dynamic prompts (B), MC commentary (A), and the
final telepathy report (C).

Every function degrades gracefully: if the LLM is disabled or fails, a static
fallback is returned so the game always has something to show.
"""

from __future__ import annotations

import random
import re

from app.services.llm_client import LLMClient

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002190-\U000021FF\U00002B00-\U00002BFF\uFE0F]"
)


def _strip_emoji(text: str) -> str:
    """Remove emoji/pictographs so the TTS engine doesn't read them oddly."""
    return _EMOJI_RE.sub("", text).strip()

# Fixed game categories and prompts (요청사항 반영).
CATEGORY_PROMPTS: dict[str, tuple[str, ...]] = {
    "상황": (
        "팀장님하면 떠오르는 포즈",
        "현 시점 LG 상황을 바라보는 나의 자세",
        "벌레 발견했을 때 내 반응",
        "사진 찍을 때 갑자기 예쁜 척 하는 나",
        "무궁화꽃이 피었습니다",
    ),
    "운동": (
        "헬스",
        "미스코리아",
        "무에타이",
        "스키점프",
        "농구",
    ),
    "감정": (
        "아련",
        "섹시",
        "졸림",
        "분노",
        "사랑",
    ),
    "영화 혹은 애니메이션": (
        "아이언맨",
        "진격의거인",
        "주술회전",
        "드래곤볼",
        "부산행",
    ),
    "인물(for 2,30대)": (
        "코르티스",
        "미나미",
        "페이커",
        "신봉선",
        "호날두",
    ),
    "인물(for 4,50대)": (
        "안정환",
        "핑클",
        "구광모",
        "이정현",
        "싸이",
    ),
}

THEMES: tuple[str, ...] = tuple(CATEGORY_PROMPTS.keys())
DEFAULT_PROMPTS: tuple[str, ...] = tuple(CATEGORY_PROMPTS[THEMES[0]][:5])


def default_prompts(theme: str | None = None, n: int = 5) -> tuple[str, ...]:
    """Return ``n`` random prompts from one selected category."""
    selected_theme = theme if theme in CATEGORY_PROMPTS else THEMES[0]
    pool = list(CATEGORY_PROMPTS[selected_theme])
    random.shuffle(pool)
    return tuple(pool[: min(n, len(pool))])


_INTRO_BANTER = (
    "자, 다들 손가락 풀고 어깨도 한번 돌려볼까요? 텔레파시는 몸이 먼저 기억하거든요!",
    "오늘 누가 가장 찰떡 호흡일지, 제가 두 눈 크게 뜨고 지켜보겠습니다!",
    "긴장되시죠? 괜찮아요, 어차피 서로 못 보니까 마음껏 망가져도 됩니다!",
)

# Instruction shown on the intro screen while waiting for the ready pose.
READY_POSE_INSTRUCTION = "양팔을 옆으로 쭉 펴서 T자를 만들어주세요!"
READY_POSE_DESCRIPTION = "T자 포즈"

_READY_POSE_WAIT = (
    "다들 양팔을 옆으로 뻗어 T자를 만들어주세요!",
    "팔을 수평으로 쭉 펴면 게임이 시작됩니다!",
    "T자 포즈! 어깨 높이로 양팔을 벌려주세요!",
)

_READY_POSE_DETECTED = (
    "자, 게임 시작!",
    "지금부터 시작!",
    "자, 갑니다!",
)


def ready_pose_wait_line() -> str:
    """Shown/spoken while waiting for all players to hold the T pose."""
    return random.choice(_READY_POSE_WAIT)


def ready_pose_detected_line() -> str:
    """Spoken the moment the ready pose is confirmed and the game begins."""
    return random.choice(_READY_POSE_DETECTED)


def category_select_line() -> str:
    """Spoken when the body-controlled category picker opens."""
    return (
        "이제 카테고리를 골라볼까요! "
        "왼손을 들면 이전, 오른손을 들면 다음 카테고리. "
        "마음에 드는 카테고리에서 T자로 팔을 벌리면 확정됩니다!"
    )


def intro_line(mc_name: str = "민수", team_name: str = "", theme: str = "") -> str:
    """Short spoken greeting played (via TTS) when the intro screen opens."""
    audience = f"{team_name.strip()} 여러분" if team_name.strip() else "여러분"
    category = f"오, '{theme.strip()}' 카테고리를 선택하셨네요! " if theme.strip() else ""
    return (
        f"안녕하세요 {audience}! "
        f"저, 에이아이 엠씨 {mc_name}와 함께하는 텔레파시 게임. "
        f"{category}"
        "제가 화면을 돌아다니면서 어떻게 하는지 설명해 드릴게요!"
    )


# Guided intro tour: the MC flies to each part of the play screen and explains
# it. Each step is (target, spoken line); the browser positions the MC next to
# that target and signals when the line finishes so the next step plays.
def intro_tour(theme: str = "") -> list[dict[str, str]]:
    return [
        {
            "target": "prompt",
            "text": "보세요! 여기 위에 이렇게 제시어가 뜹니다. 이 단어를 보고, 머릿속에 떠오르는 동작을 똑같이 취해주세요!",
        },
        {
            "target": "gauge",
            "text": "그리고 가운데 이 게이지! 여러분의 동작이 얼마나 똑같은지, 텔레파시가 얼마나 통했는지 실시간으로 보여주는 점수예요. 높을수록 좋습니다!",
        },
        {
            "target": "hint",
            "text": "여기 아래! 동작이 많이 다르면 이 스켈레톤 힌트가 겹쳐서, 누가 다르게 하고 있는지 보여줘요. 서로 못 보니까 이걸 믿으세요!",
        },
        {
            "target": "ready",
            "text": "총 다섯 라운드, 라운드마다 십 초! 다들 준비 되셨나요? 그럼 시작합니다!",
        },
    ]


_START_LINES = (
    "좋습니다! 그럼 바로 첫 번째 제시어 갑니다. 집중하세요!",
    "자 시작할게요! 머릿속에 떠오르는 그 동작, 믿고 가는 겁니다!",
    "준비 끝! 텔레파시 게임, 지금 시작합니다!",
)


def start_line(mc_name: str = "민수") -> str:
    """Spoken when the host triggers the first round from the intro screen."""
    return random.choice(_START_LINES)


# --------------------------------------------------------------------------- #
# B. Dynamic prompt generation
# --------------------------------------------------------------------------- #
async def generate_prompts(llm: LLMClient, theme: str, n: int) -> list[str]:
    """Generate prompts list from the selected category (LLM not used for this mode)."""
    return list(default_prompts(theme=theme, n=n))


def _coerce_prompt_list(result: dict | None) -> list[str]:
    if not result:
        return []
    raw = result.get("prompts")
    if not isinstance(raw, list):
        return []
    cleaned: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            cleaned.append(item.strip()[:24])
    return cleaned


# --------------------------------------------------------------------------- #
# A. MC commentary per round result
# --------------------------------------------------------------------------- #
_STATIC_MC = {
    "low": [
        "음… 세 분이 각자 다른 우주에 사셨네요? ㅋㅋ",
        "텔레파시 신호 끊김! 전혀 다른 동작이에요.",
        "이건 뭐… 서로 모르는 사이 인증입니다.",
    ],
    "mid": [
        "오! 조금씩 통하는데요? 절반의 성공!",
        "비슷한 듯 다른 듯… 애매한 텔레파시!",
        "감 잡았어요? 거의 맞아가는 중!",
    ],
    "high": [
        "찰떡같이 통했어요! 소름 돋는 호흡!",
        "완벽에 가까워요! 한 몸처럼 움직였네요!",
        "이 정도면 텔레파시 인정! 대단해요!",
    ],
}


def static_mc_comment(score: float, ready_count: int) -> str:
    if ready_count < 2:
        return "플레이어를 기다리는 중… 다 같이 동작을 취해주세요!"
    bucket = "low" if score < 45 else "mid" if score < 75 else "high"
    return random.choice(_STATIC_MC[bucket])


# --------------------------------------------------------------------------- #
# A2. Live in-round coaching (no LLM — runs every tick during PLAYING).
# Spoken by the browser's instant Web Speech voice so it never blocks the board.
# --------------------------------------------------------------------------- #
_COACH_WAIT = ("다 같이 카메라 앞에 서주세요!",)
_COACH_STILL = (
    "다들 너무 가만히 있어요! 동작을 더 크게!",
    "차렷 자세 말고, 몸으로 표현해 봐요!",
    "정지 화면인가요? 좀 더 과감하게!",
)
_COACH_GREAT = (
    "완벽해요! 그대로 유지!",
    "소름! 한 몸처럼 움직이네요!",
    "이대로 가면 만점이에요!",
)
_COACH_GOOD = (
    "좋아요! 조금만 더 맞춰봐요!",
    "느낌 오죠? 거의 다 왔어요!",
    "호흡이 살아나는데요?",
)
_COACH_KEEP = (
    "음, 생각이 다른데요? 서로 맞춰봐요!",
    "아직 제각각이에요. 대표 동작을 떠올려요!",
    "텔레파시 신호가 약해요. 집중!",
)


def coach(
    players: list[dict[str, object]],
    expressiveness: float,
    ready_count: int,
    gauge: float,
    round_index: int = 0,
) -> dict[str, str]:
    """Return ``{"key": ..., "text": ...}`` live coaching for the playing phase.

    ``key`` is a stable category id so the caller can detect when the message
    really changes (and only then re-speak it). The text is varied but stable
    within a given ``(key, round)`` so it doesn't flicker every tick.
    """
    if ready_count < 2:
        return _coach_pick("wait", _COACH_WAIT, round_index)
    if expressiveness < 0.18:
        return _coach_pick("still", _COACH_STILL, round_index)

    # Single clear outlier? Nudge that player by number.
    present = [p for p in players if p.get("present") and p.get("sync") is not None]
    if len(present) >= 3:
        ordered = sorted(present, key=lambda p: float(p["sync"]))  # type: ignore[arg-type]
        low = ordered[0]
        others_avg = sum(float(p["sync"]) for p in ordered[1:]) / (len(ordered) - 1)
        if others_avg - float(low["sync"]) > 22.0:
            n = int(low["index"]) + 1  # type: ignore[arg-type]
            return {"key": f"outlier:{n}", "text": f"{n}번님! 다른 분들과 동작이 좀 달라요. 맞춰볼까요?"}

    if gauge >= 80:
        return _coach_pick("great", _COACH_GREAT, round_index)
    if gauge >= 50:
        return _coach_pick("good", _COACH_GOOD, round_index)
    return _coach_pick("keep", _COACH_KEEP, round_index)


def _coach_pick(key: str, options: tuple[str, ...], round_index: int) -> dict[str, str]:
    rng = random.Random(f"{key}:{round_index}")
    return {"key": key, "text": rng.choice(options)}


# --------------------------------------------------------------------------- #
# A3. Hint lines — shown when score is too low
# --------------------------------------------------------------------------- #
# hint_for_player(n, joint) returns a hint targeting player n (1-based) about
# a specific joint area. Called from game_manager when the hint conditions are
# met (score ≤ 50 at start, or score ≤ 70 with 5s left).

_HINT_JOINT_LABEL: dict[str, str] = {
    "left_upper_arm": "왼쪽 윗팔",
    "left_forearm": "왼쪽 아래팔",
    "right_upper_arm": "오른쪽 윗팔",
    "right_forearm": "오른쪽 아래팔",
    "left_thigh": "왼쪽 허벅지",
    "left_shin": "왼쪽 정강이",
    "right_thigh": "오른쪽 허벅지",
    "right_shin": "오른쪽 정강이",
    "left_shoulder":  "왼팔 각도",
    "right_shoulder": "오른팔 각도",
    "left_elbow":     "왼쪽 팔꿈치",
    "right_elbow":    "오른쪽 팔꿈치",
    "left_hip":       "왼쪽 허리",
    "right_hip":      "오른쪽 허리",
    "left_knee":      "왼쪽 무릎",
    "right_knee":     "오른쪽 무릎",
}

_HINT_TEMPLATES = (
    "{n}번님, {joint} 부분이 다른 분들과 조금 달라요!",
    "{n}번님! {joint}를 살짝 맞춰보세요!",
    "{n}번 선수, {joint} 확인해봐요!",
)


def hint_for_player(player_number: int, joint_name: str) -> str:
    """Return a hint line targeting a specific player and joint."""
    label = _HINT_JOINT_LABEL.get(joint_name, joint_name)
    template = random.choice(_HINT_TEMPLATES)
    return template.format(n=player_number, joint=label)


def hint_group_low() -> str:
    """Generic hint when overall score is very low (≤50) right after start."""
    return random.choice((
        "모두 동작이 많이 달라요! 제시어를 다시 생각해봐요!",
        "텔레파시 신호 미약! 대표 동작을 떠올려 보세요!",
        "다들 다른 동작이에요. 서로 맞춰봐요!",
    ))


async def generate_mc_comment(
    llm: LLMClient,
    prompt: str,
    score: float,
    ready_count: int,
    player_count: int,
) -> str:
    if not llm.enabled or ready_count < 2:
        return static_mc_comment(score, ready_count)

    system = (
        "너는 활기찬 한국 예능 프로그램의 진행자(MC)야. "
        "방금 끝난 '몸으로 텔레파시 맞추기' 라운드 결과를 보고 "
        "재치 있는 한 줄 멘트를 한국어로 말한다. "
        "반드시 한 문장, 30자 이내로 짧게. 이모지·특수기호·설명 없이 멘트만."
    )
    user = (
        f"제시어: {prompt}\n"
        f"참가자 수: {player_count}, 동작을 취한 사람: {ready_count}\n"
        f"텔레파시 점수(0~100): {round(score)}\n"
        "한 문장 멘트만 출력해."
    )
    ok, text = await llm.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=64,
        temperature=0.9,
    )
    if not ok or not text:
        return static_mc_comment(score, ready_count)
    cleaned = _strip_emoji(_first_line(text))
    return cleaned or static_mc_comment(score, ready_count)


# --------------------------------------------------------------------------- #
# C. Final telepathy report
# --------------------------------------------------------------------------- #
def static_final_report(total_score: float) -> str:
    if total_score >= 90:
        return "운명 공동체 텔레파시! 다섯 라운드 내내 한 몸처럼 움직인 환상의 팀워크였어요."
    if total_score >= 75:
        return "찰떡같은 텔레파시! 대부분의 라운드에서 척척 맞아떨어졌네요."
    if total_score >= 60:
        return "제법 통하는 사이! 몇몇 라운드에서 멋진 호흡을 보여줬어요."
    if total_score >= 40:
        return "가끔 통하는 사이. 손발은 조금 안 맞아도 즐거운 한 판이었어요."
    if total_score >= 20:
        return "데면데면한 사이. 서로의 동작을 더 상상해볼 필요가 있겠어요!"
    return "서로 모르는 사이?! 다음 판엔 분명 더 잘 통할 거예요."


async def generate_final_report(
    llm: LLMClient,
    prompts: list[str],
    round_scores: list[float],
    total_score: float,
) -> str:
    if not llm.enabled or not round_scores:
        return static_final_report(total_score)

    rounds_desc = "\n".join(
        f"{i + 1}라운드 '{prompt}': {round(score)}점"
        for i, (prompt, score) in enumerate(zip(prompts, round_scores))
    )
    system = (
        "너는 재치 있는 '텔레파시 궁합 분석가'야. "
        "라운드별 점수를 보고 참가자들의 호흡을 재미있게 분석하는 "
        "2~3문장의 한국어 총평을 쓴다. 점수가 높았던/낮았던 라운드를 자연스럽게 언급해."
    )
    user = (
        f"라운드별 결과:\n{rounds_desc}\n"
        f"평균 텔레파시 점수: {round(total_score)}\n"
        "2~3문장 총평만 출력해."
    )
    ok, text = await llm.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=200,
        temperature=0.85,
    )
    if not ok or not text:
        return static_final_report(total_score)
    return _strip_emoji(text.strip()) or static_final_report(total_score)


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return text.strip()
