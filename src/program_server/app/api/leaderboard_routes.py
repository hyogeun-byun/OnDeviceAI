from __future__ import annotations

from fastapi import APIRouter, Request

from app.services.leaderboard import Leaderboard

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


def get_leaderboard(request: Request) -> Leaderboard:
    return request.app.state.leaderboard


@router.get("")
async def list_leaderboard(request: Request, limit: int = 50) -> dict[str, object]:
    board = get_leaderboard(request)
    limit = max(1, min(int(limit), 200))
    return {"entries": board.top(limit), "count": board.count()}


@router.post("/reset")
async def reset_leaderboard(request: Request) -> dict[str, object]:
    """Wipe every saved score so the next demo starts from an empty board."""
    board = get_leaderboard(request)
    removed = board.clear()
    return {"ok": True, "removed": removed}
