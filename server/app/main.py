from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.camera_routes import router as camera_router
from app.api.game_routes import router as game_router
from app.api.health_routes import router as health_router
from app.config import load_config
from app.services.game_hub import GameHub
from app.services.game_manager import GameManager
from app.services.stream_manager import StreamManager
from app.services.traffic_metrics import TrafficMetrics

GAME_TICK_HZ = 10.0

config = load_config()
stream_manager = StreamManager(camera_ids=config.camera_ids)
traffic_metrics = TrafficMetrics()
game_manager = GameManager(camera_ids=config.camera_ids, stream_manager=stream_manager)
game_hub = GameHub()


async def _game_loop() -> None:
    interval = 1.0 / GAME_TICK_HZ
    while True:
        await asyncio.sleep(interval)
        game_manager.tick()
        await game_hub.broadcast(game_manager.snapshot())


@asynccontextmanager
async def lifespan(_: FastAPI):
    loop_task = asyncio.create_task(_game_loop())
    try:
        yield
    finally:
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="OnDeviceAI Server", lifespan=lifespan)
app.state.stream_manager = stream_manager
app.state.traffic_metrics = traffic_metrics
app.state.game_manager = game_manager
app.state.game_hub = game_hub

app.include_router(health_router)
app.include_router(camera_router)
app.include_router(game_router)
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

templates = Jinja2Templates(directory="app/web/templates")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "camera_ids": config.camera_ids,
            "visualize_metrics": config.visualize_metrics,
        },
    )


@app.get("/game", response_class=HTMLResponse)
async def game(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "game.html",
        {
            "request": request,
            "player_count": len(config.camera_ids),
        },
    )
