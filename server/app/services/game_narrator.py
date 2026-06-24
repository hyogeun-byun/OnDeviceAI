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

# Default / fallback prompts (also used when the LLM is off).
# Abstract single words: each player interprets them with their own pose,
# which produces far more variety (and funnier mismatches) than literal
# "raise one leg" style instructions.
DEFAULT_PROMPTS: tuple[str, ...] = (
    "사랑",
    "승리",
    "공포",
    "비밀",
    "자유",
)

# Selectable themes shown on the idle screen. "기본" uses the default prompts.
THEMES: tuple[str, ...] = ("기본", "좀비", "K-POP", "출근길", "동물원", "슈퍼히어로")


_INTRO_BANTER = (
    "자, 다들 손가락 풀고 어깨도 한번 돌려볼까요? 텔레파시는 몸이 먼저 기억하거든요!",
    "오늘 누가 가장 찰떡 호흡일지, 제가 두 눈 크게 뜨고 지켜보겠습니다!",
    "긴장되시죠? 괜찮아요, 어차피 서로 못 보니까 마음껏 망가져도 됩니다!",
    "준비되면 아래 버튼을 눌러주세요. 제가 카운트 들어갑니다!",
)


def intro_line(mc_name: str = "민수", team_name: str = "") -> str:
    """Short spoken greeting played (via TTS) when the intro screen opens."""
    audience = f"{team_name.strip()} 여러분" if team_name.strip() else "여러분"
    return (
        f"안녕하세요 {audience}! "
        f"저, 에이아이 엠씨 {mc_name}와 함께하는 텔레파시 게임. "
        "모두 준비 되셨나요! 서로의 동작은 볼 수 없습니다. 오직 텔레파시만 믿으세요! "
        + random.choice(_INTRO_BANTER)
    )


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
    """Generate ``n`` short Korean pose prompts for the given theme.

    Falls back to the default prompts on any failure.
    """
    if not llm.enabled or theme == "기본":
        return list(DEFAULT_PROMPTS[:n])

    system = (
        "너는 몸으로 표현하는 텔레파시 파티 게임의 출제자야. "
        "주어진 테마에 어울리는, 한 단어로 된 '추상적인 제시어'를 만든다. "
        "구체적인 동작 설명(예: '한 다리 들기')이 아니라, "
        "사람마다 자유롭게 다르게 해석해 몸짓을 만들 수 있는 단어여야 한다 "
        "(예: 사랑, 승리, 공포, 자유). 각 제시어는 한국어 1~4자."
    )
    user = (
        f"테마: {theme}\n"
        f"이 테마에 어울리는 한 단어 제시어 {n}개를 만들어줘.\n"
        '반드시 JSON만 출력: {"prompts": ["제시어1", "제시어2", ...]}'
    )
    result = await llm.chat_json(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=200,
        temperature=0.9,
    )
    prompts = _coerce_prompt_list(result)
    if len(prompts) >= n:
        return prompts[:n]
    # Pad with defaults if the model returned too few.
    padded = prompts + [p for p in DEFAULT_PROMPTS if p not in prompts]
    return padded[:n]


def _coerce_prompt_list(result: dict | None) -> list[str]:
    if not result:
        return []
    raw = result.get("prompts")
    if not isinstance(raw, list):
        return []
    cleaned: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            cleaned.append(item.strip()[:10])
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
