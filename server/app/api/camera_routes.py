from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.services.stream_manager import StreamManager
from app.services.traffic_metrics import TrafficMetrics

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


class Keypoint(BaseModel):
    name: str
    x: float
    y: float
    z: float | None = None
    visibility: float | None = None


class PoseResult(BaseModel):
    camera_id: str
    person_detected: bool
    keypoints: list[Keypoint] = Field(default_factory=list)
    inference_ms: float | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    backend: str = "unknown"


class WorkerMetrics(BaseModel):
    camera_id: str
    elapsed_seconds: float
    frame_fps: float
    pose_fps: float
    avg_capture_ms: float
    avg_pose_ms: float
    avg_encode_ms: float
    avg_frame_upload_ms: float
    avg_pose_upload_ms: float
    avg_frame_kb: float
    upload_kb_s: float
    sent_frames: int
    failed_frames: int
    sent_poses: int
    failed_poses: int


def get_stream_manager(request: Request) -> StreamManager:
    return request.app.state.stream_manager


def get_traffic_metrics(request: Request) -> TrafficMetrics:
    return request.app.state.traffic_metrics


def update_pose_result(
    camera_id: str,
    pose_result: PoseResult,
    stream_manager: StreamManager,
    traffic_metrics: TrafficMetrics,
) -> dict[str, object]:
    if pose_result.camera_id != camera_id:
        raise HTTPException(status_code=400, detail="Camera ID in path and body must match.")

    stream_manager.update_pose(camera_id=camera_id, pose_result=pose_result.model_dump())
    traffic_metrics.record_pose(camera_id=camera_id)
    return {
        "camera_id": camera_id,
        "keypoint_count": len(pose_result.keypoints),
        "person_detected": pose_result.person_detected,
    }


def update_worker_metrics(
    camera_id: str,
    metrics: WorkerMetrics,
    stream_manager: StreamManager,
) -> dict[str, object]:
    if metrics.camera_id != camera_id:
        raise HTTPException(status_code=400, detail="Camera ID in path and body must match.")

    stream_manager.update_worker_metrics(camera_id=camera_id, metrics=metrics.model_dump())
    return {"camera_id": camera_id, "received": True}


@router.get("")
async def list_cameras(request: Request) -> dict[str, object]:
    stream_manager = get_stream_manager(request)
    traffic_metrics = get_traffic_metrics(request)
    cameras = []

    for camera in stream_manager.list_camera_statuses():
        camera_id = str(camera["camera_id"])
        cameras.append(
            {
                **camera,
                "worker_metrics": stream_manager.get_worker_metrics(camera_id),
                "server_metrics": traffic_metrics.get_latest(camera_id),
            }
        )

    return {"cameras": cameras}


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
    get_traffic_metrics(request).record_frame(camera_id=camera_id, frame_bytes=len(frame_bytes))
    return {"camera_id": camera_id, "received_bytes": len(frame_bytes)}


@router.post("/{camera_id}/pose")
async def receive_pose(
    camera_id: str,
    request: Request,
    pose_result: PoseResult,
) -> dict[str, object]:
    return update_pose_result(
        camera_id=camera_id,
        pose_result=pose_result,
        stream_manager=get_stream_manager(request),
        traffic_metrics=get_traffic_metrics(request),
    )


@router.post("/{camera_id}/metrics")
async def receive_metrics(
    camera_id: str,
    request: Request,
    metrics: WorkerMetrics,
) -> dict[str, object]:
    return update_worker_metrics(
        camera_id=camera_id,
        metrics=metrics,
        stream_manager=get_stream_manager(request),
    )


@router.websocket("/{camera_id}/ws")
async def camera_websocket(camera_id: str, websocket: WebSocket) -> None:
    await websocket.accept()
    stream_manager: StreamManager = websocket.app.state.stream_manager
    traffic_metrics: TrafficMetrics = websocket.app.state.traffic_metrics

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return

            frame_bytes = message.get("bytes")
            message_text = message.get("text")

            if frame_bytes is not None:
                stream_manager.update_frame(camera_id=camera_id, frame_bytes=frame_bytes)
                traffic_metrics.record_frame(camera_id=camera_id, frame_bytes=len(frame_bytes))
                continue

            if message_text is None:
                continue

            try:
                payload = json.loads(message_text)
            except json.JSONDecodeError:
                continue

            message_type = payload.get("type")
            message_payload = payload.get("payload", {})

            if message_type == "pose":
                update_pose_result(
                    camera_id=camera_id,
                    pose_result=PoseResult.model_validate(message_payload),
                    stream_manager=stream_manager,
                    traffic_metrics=traffic_metrics,
                )
            elif message_type == "metrics":
                update_worker_metrics(
                    camera_id=camera_id,
                    metrics=WorkerMetrics.model_validate(message_payload),
                    stream_manager=stream_manager,
                )
    except WebSocketDisconnect:
        return


@router.get("/{camera_id}/pose")
async def pose(camera_id: str, request: Request) -> dict[str, object]:
    stream_manager = get_stream_manager(request)
    pose_result = stream_manager.get_pose(camera_id)
    if pose_result is None:
        raise HTTPException(status_code=404, detail="No pose result has been received yet.")
    return pose_result


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
