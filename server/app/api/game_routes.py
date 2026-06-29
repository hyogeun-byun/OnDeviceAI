from __future__ import annotations

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect

from app.services.game_hub import GameHub
from app.services.game_manager import GameManager

router = APIRouter(prefix="/api/game", tags=["game"])


def get_game_manager(request: Request) -> GameManager:
    return request.app.state.game_manager


def get_game_hub(request: Request) -> GameHub:
    return request.app.state.game_hub


@router.get("/state")
async def game_state(request: Request) -> dict[str, object]:
    return get_game_manager(request).snapshot()


@router.post("/start")
async def start_game(request: Request) -> dict[str, object]:
    game_manager = get_game_manager(request)
    theme: str | None = None
    team_name: str | None = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            value = body.get("theme")
            if isinstance(value, str) and value.strip():
                theme = value.strip()
            name = body.get("team_name")
            if isinstance(name, str) and name.strip():
                team_name = name.strip()[:40]
    except Exception:
        theme = None
    game_manager.start(theme, team_name)
    return game_manager.snapshot()


@router.post("/stage")
async def stage_game(request: Request) -> dict[str, object]:
    """Remember the team name / theme entered on the idle screen so the T-pose
    gesture can auto-start the game without any button."""
    game_manager = get_game_manager(request)
    team_name: str | None = None
    theme: str | None = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            name = body.get("team_name")
            if isinstance(name, str):
                team_name = name.strip()[:40]
            value = body.get("theme")
            if isinstance(value, str) and value.strip():
                theme = value.strip()
    except Exception:
        pass
    game_manager.stage(team_name, theme)
    return {"ok": True}


@router.post("/begin")
async def begin_game(request: Request) -> dict[str, object]:
    game_manager = get_game_manager(request)
    game_manager.begin()
    return game_manager.snapshot()


@router.post("/skip-intro")
async def skip_intro(request: Request) -> dict[str, object]:
    """Manual fallback for the T-pose skip: jump from the explanation to the
    category picker."""
    game_manager = get_game_manager(request)
    game_manager.skip_intro()
    return game_manager.snapshot()


@router.post("/confirm-category")
async def confirm_category(request: Request) -> dict[str, object]:
    """Manual fallback for the T-pose confirm: lock in the highlighted category."""
    game_manager = get_game_manager(request)
    game_manager.confirm_category()
    return game_manager.snapshot()


@router.post("/category-step/{direction}")
async def category_step(direction: str, request: Request) -> dict[str, object]:
    """Manual fallback for the hand-raise: step the highlighted category."""
    game_manager = get_game_manager(request)
    game_manager.step_category(1 if direction == "next" else -1)
    return game_manager.snapshot()


@router.post("/intro-done")
async def intro_done(request: Request) -> dict[str, object]:
    """Browser reports the MC finished reading the opening line, so the
    countdown can start exactly when speech ends (no early cut-off)."""
    game_manager = get_game_manager(request)
    game_manager.intro_done()
    return game_manager.snapshot()


@router.post("/reset")
async def reset_game(request: Request) -> dict[str, object]:
    game_manager = get_game_manager(request)
    game_manager.reset()
    return game_manager.snapshot()


@router.get("/speech/{speech_id}.mp3")
async def game_speech(speech_id: int, request: Request) -> Response:
    cache = getattr(request.app.state, "speech_audio", None)
    data = cache.get(speech_id) if cache is not None else None
    if not data:
        # Not generated yet (or unavailable): browser retries / falls back.
        return Response(status_code=404)
    return Response(content=data, media_type="audio/mpeg")


@router.get("/result-frame/{round_number}/{player_index}.jpg")
async def result_frame(
    round_number: int, player_index: int, request: Request
) -> Response:
    """Real camera photo captured at the moment the round was scored, used for
    the "AI Vision" reveal. 404 until a frame exists (browser falls back)."""
    data = get_game_manager(request).get_result_frame(round_number, player_index)
    if not data:
        return Response(status_code=404)
    # Never cache: the same round/player slot holds a different photo next game.
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.websocket("/ws")
async def game_websocket(websocket: WebSocket) -> None:
    hub: GameHub = websocket.app.state.game_hub
    game_manager: GameManager = websocket.app.state.game_manager

    await hub.connect(websocket)
    try:
        await websocket.send_json(game_manager.snapshot())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(websocket)
