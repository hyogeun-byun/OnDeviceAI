from __future__ import annotations

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

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
    game_manager.start()
    return game_manager.snapshot()


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
