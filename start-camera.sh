#!/usr/bin/env bash
# =============================================================
#  이구동성 텔레파시 — 카메라 워커만 실행 (다른 노트북/PC용)
#  서버(보드) 주소를 .env 안 고치고 그때그때 입력/지정한다.
#
#  사용법 1) 물어보면 IP 입력:
#     ./start-camera.sh
#  사용법 2) 한 줄로 지정:
#     SERVER_IP=10.56.131.39 CAMERA_ID=camera_01 CAMERA_INDEX=0 ./start-camera.sh
#  종료: Ctrl+C
# =============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PORT="${PORT:-8000}"
CAMERA_ID="${CAMERA_ID:-camera_01}"
CAMERA_INDEX="${CAMERA_INDEX:-0}"
SERVER_IP="${SERVER_IP:-}"
SERVER_URL="${SERVER_URL:-}"

# 서버 주소 결정 (SERVER_URL 직접 지정 > SERVER_IP > 물어보기)
if [ -z "$SERVER_URL" ]; then
  if [ -z "$SERVER_IP" ]; then
    read -rp "서버(보드) IP 주소 [예: 10.56.131.39]: " SERVER_IP
  fi
  SERVER_URL="http://${SERVER_IP}:${PORT}"
fi
SERVER_URL="${SERVER_URL%/}"

WORKER_VENV="$ROOT/camera-worker/.venv"
if [ -x "$WORKER_VENV/bin/python" ]; then
  WORKER_PY="$WORKER_VENV/bin/python"
else
  WORKER_PY="python3"
fi

echo "[camera] ${CAMERA_ID} (index ${CAMERA_INDEX}) → ${SERVER_URL}"
echo "         종료하려면 Ctrl+C"
cd "$ROOT/camera-worker"
CAMERA_ID="$CAMERA_ID" CAMERA_INDEX="$CAMERA_INDEX" SERVER_URL="$SERVER_URL" \
  exec "$WORKER_PY" -m app.main
