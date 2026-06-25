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
    try:
        body = await request.json()
        if isinstance(body, dict):
            value = body.get("theme")
            if isinstance(value, str) and value.strip():
                theme = value.strip()
    except Exception:
        theme = None
    game_manager.start(theme)
    return game_manager.snapshot()


@router.post("/begin")
async def begin_game(request: Request) -> dict[str, object]:
    game_manager = get_game_manager(request)
    game_manager.begin()
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
