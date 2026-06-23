from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.services.stream_manager import StreamManager

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


def get_stream_manager(request: Request) -> StreamManager:
    return request.app.state.stream_manager


@router.get("")
async def list_cameras(request: Request) -> dict[str, object]:
    stream_manager = get_stream_manager(request)
    return {"cameras": stream_manager.list_camera_statuses()}


@router.post("/{camera_id}/frame")
async def receive_frame(
    camera_id: str,
    request: Request,
    frame: UploadFile = File(...),
) -> dict[str, object]:
    if frame.content_type not in {"image/jpeg", "image/jpg"}:
        raise HTTPException(status_code=400, detail="Only JPEG frames are supported.")

    frame_bytes = await frame.read()
    if not frame_bytes:
        raise HTTPException(status_code=400, detail="Frame is empty.")

    stream_manager = get_stream_manager(request)
    stream_manager.update_frame(camera_id=camera_id, frame_bytes=frame_bytes)
    return {"camera_id": camera_id, "received_bytes": len(frame_bytes)}


@router.get("/{camera_id}/snapshot")
async def snapshot(camera_id: str, request: Request) -> Response:
    stream_manager = get_stream_manager(request)
    frame_bytes = stream_manager.get_frame(camera_id)
    if frame_bytes is None:
        raise HTTPException(status_code=404, detail="No frame has been received yet.")
    return Response(content=frame_bytes, media_type="image/jpeg")


@router.get("/{camera_id}/stream")
async def stream(camera_id: str, request: Request) -> StreamingResponse:
    stream_manager = get_stream_manager(request)

    async def generate_frames() -> AsyncIterator[bytes]:
        last_version = -1
        while True:
            frame = stream_manager.get_frame_with_version(camera_id)
            if frame is not None:
                version, frame_bytes = frame
                if version != last_version:
                    last_version = version
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + frame_bytes
                        + b"\r\n"
                    )
            await asyncio.sleep(0.05)

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

