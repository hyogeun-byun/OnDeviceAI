"""Camera recorder with keyboard toggle.

Usage:
    python record_camera.py [--camera 0] [--output output.mp4] [--fps 20] [--width 640] [--height 480]

Controls:
    R  - Start / Stop recording
    Q  - Quit
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record camera video with R to toggle.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--output", type=str, default="", help="Output file path (default: auto-named .mp4)")
    parser.add_argument("--fps", type=float, default=20.0, help="Recording FPS (default: 20)")
    parser.add_argument("--width", type=int, default=640, help="Frame width (default: 640)")
    parser.add_argument("--height", type=int, default=480, help="Frame height (default: 480)")
    return parser.parse_args()


def make_output_path(requested: str) -> Path:
    if requested:
        return Path(requested)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return Path(f"recording_{timestamp}.mp4")


def draw_overlay(frame: cv2.typing.MatLike, recording: bool, elapsed: float) -> cv2.typing.MatLike:
    h, w = frame.shape[:2]
    overlay = frame.copy()

    if recording:
        # Red recording indicator dot
        cv2.circle(overlay, (30, 30), 12, (0, 0, 220), -1)
        mins = int(elapsed) // 60
        secs = int(elapsed) % 60
        time_str = f"{mins:02d}:{secs:02d}"
        cv2.putText(overlay, f"REC  {time_str}", (50, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 220), 2, cv2.LINE_AA)
    else:
        cv2.putText(overlay, "STANDBY", (20, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 180, 180), 2, cv2.LINE_AA)

    # Bottom hint bar
    hint = "[R] Start/Stop Recording    [Q] Quit"
    cv2.rectangle(overlay, (0, h - 32), (w, h), (30, 30, 30), -1)
    cv2.putText(overlay, hint, (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)

    return overlay


def main() -> None:
    args = parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {args.camera}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter.fourcc(*"mp4v")

    writer: cv2.VideoWriter | None = None
    recording = False
    rec_started_at = 0.0
    output_path: Path | None = None

    print("Camera opened. Press R to start/stop recording, Q to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame.")
            break

        elapsed = time.perf_counter() - rec_started_at if recording else 0.0

        if recording and writer is not None:
            writer.write(frame)

        display = draw_overlay(frame, recording, elapsed)
        cv2.imshow("Camera Recorder", display)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("r") or key == ord("R"):
            if not recording:
                # Start recording
                output_path = make_output_path(args.output)
                writer = cv2.VideoWriter(str(output_path), fourcc, args.fps, (actual_w, actual_h))
                recording = True
                rec_started_at = time.perf_counter()
                print(f"[REC] Started → {output_path}")
            else:
                # Stop recording
                recording = False
                if writer is not None:
                    writer.release()
                    writer = None
                print(f"[REC] Stopped → saved to {output_path}")

        elif key == ord("q") or key == ord("Q"):
            break

    # Cleanup
    if recording and writer is not None:
        writer.release()
        print(f"[REC] Auto-saved to {output_path}")

    cap.release()
    cv2.destroyAllWindows()
    print("Done.")


if __name__ == "__main__":
    main()
