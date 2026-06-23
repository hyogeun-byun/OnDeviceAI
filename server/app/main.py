from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.camera_routes import router as camera_router
from app.api.health_routes import router as health_router
from app.config import load_config
from app.services.stream_manager import StreamManager
from app.services.traffic_metrics import TrafficMetrics

config = load_config()
stream_manager = StreamManager(camera_ids=config.camera_ids)
traffic_metrics = TrafficMetrics()

app = FastAPI(title="OnDeviceAI Server")
app.state.stream_manager = stream_manager
app.state.traffic_metrics = traffic_metrics

app.include_router(health_router)
app.include_router(camera_router)
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
