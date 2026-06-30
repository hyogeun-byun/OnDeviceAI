from __future__ import annotations

import asyncio
import time
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.camera_routes import debug_router
from app.api.camera_routes import router as camera_router
from app.api.game_routes import router as game_router
from app.api.health_routes import router as health_router
from app.api.leaderboard_routes import router as leaderboard_router
from app.config import load_config
from app.services import game_narrator
from app.services.game_hub import GameHub
from app.services.game_manager import GameManager
from app.services.leaderboard import Leaderboard
from app.services.llm_client import LLMClient
from app.services.speech_audio import SpeechAudioCache
from app.services.stream_manager import StreamManager
from app.services.traffic_metrics import TrafficMetrics
from app.services.tts import Speaker

GAME_TICK_HZ = 10.0

config = load_config()
stream_manager = StreamManager(camera_ids=config.camera_ids)
traffic_metrics = TrafficMetrics()
llm_client = LLMClient(
    base_url=config.llm_base_url,
    model=config.llm_model,
    timeout=config.llm_timeout,
    enabled=config.llm_enabled,
)
speaker = Speaker(
    enabled=config.tts_enabled,
    engine=config.tts_engine,
    voice=config.tts_voice,
    openai_model=config.tts_openai_model,
    piper_model=config.tts_piper_model,
    lang=config.tts_lang,
)
speech_audio = SpeechAudioCache(
    enabled=config.edge_tts_enabled,
    voice=config.edge_tts_voice,
    rate=config.edge_tts_rate,
)
leaderboard = Leaderboard(config.leaderboard_db)
game_manager = GameManager(
    camera_ids=config.camera_ids,
    stream_manager=stream_manager,
    llm_client=llm_client,
    default_theme=config.llm_default_theme,
    speaker=speaker,
    mc_name=config.tts_mc_name,
    team_name=config.tts_team_name,
    speech_audio=speech_audio,
    leaderboard=leaderboard,
)
game_hub = GameHub()


async def _game_loop() -> None:
    interval = 1.0 / GAME_TICK_HZ
    consecutive_errors = 0
    while True:
        await asyncio.sleep(interval)
        try:
            await game_manager.tick()
            await game_hub.broadcast(game_manager.snapshot())
            consecutive_errors = 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # A single bad tick (e.g. a malformed pose frame) must NEVER kill
            # the loop — that would freeze the whole game: no phase progress,
            # frozen skeleton, and a silent MC. Log it and keep ticking so the
            # game always recovers on the next frame.
            consecutive_errors += 1
            if consecutive_errors <= 5 or consecutive_errors % 50 == 0:
                print(f"[game_loop] tick error (continuing): {exc!r}")
                traceback.print_exc()


async def _warmup_llm() -> None:
    """Load the model into memory at startup so the first game has no cold start.

    Runs once in the background; any failure is non-fatal (the game falls back
    to static text as usual).
    """
    if not llm_client.enabled:
        return
    ok, _ = await llm_client.chat(
        [{"role": "user", "content": "안녕"}],
        max_tokens=1,
        temperature=0.0,
    )
    print(f"[llm] warmup {'ready' if ok else 'failed (will retry on first use)'}")


async def _warmup_speech() -> None:
    """Pre-render every static MC line into the neural-TTS cache at startup so
    short phases (camera test, confirm, give-up) never wait on a runtime
    synthesis round-trip. Best-effort: any failure is non-fatal (the browser
    falls back to its own Web Speech voice).
    """
    if not speech_audio.enabled:
        return
    try:
        count = await speech_audio.prewarm(game_narrator.prewarm_lines())
        print(f"[speech] prewarmed {count} MC lines")
    except Exception as exc:  # pragma: no cover - best-effort warmup
        print(f"[speech] prewarm failed (will synthesize on demand): {exc}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    loop_task = asyncio.create_task(_game_loop())
    warmup_task = asyncio.create_task(_warmup_llm())
    speech_task = asyncio.create_task(_warmup_speech())
    try:
        yield
    finally:
        warmup_task.cancel()
        try:
            await warmup_task
        except asyncio.CancelledError:
            pass
        speech_task.cancel()
        try:
            await speech_task
        except asyncio.CancelledError:
            pass
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
app.state.speech_audio = speech_audio
app.state.leaderboard = leaderboard

app.include_router(health_router)
app.include_router(camera_router)
app.include_router(debug_router)
app.include_router(game_router)
app.include_router(leaderboard_router)
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

templates = Jinja2Templates(directory="app/web/templates")

# Bust the browser cache for CSS/JS on every server (re)start so clients never
# run a stale build after an update. Appended as ?v=... to static asset URLs.
ASSET_VERSION = str(int(time.time()))


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
    response = templates.TemplateResponse(
        "game.html",
        {
            "request": request,
            "player_count": len(config.camera_ids),
            "themes": list(game_narrator.THEMES),
            "asset_version": ASSET_VERSION,
        },
    )
    # Never cache the HTML page itself, otherwise the browser keeps loading an
    # old page that points at stale ?v= assets and updates never show up.
    response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


@app.get("/stage", response_class=HTMLResponse)
async def stage(request: Request) -> HTMLResponse:
    response = templates.TemplateResponse(
        "stage.html",
        {
            "request": request,
            "camera_ids": config.camera_ids,
            "player_count": len(config.camera_ids),
            "asset_version": ASSET_VERSION,
        },
    )
    response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response
