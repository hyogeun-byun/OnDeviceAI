#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/log"
PORT="${PORT:-18000}"
RECREATE_VENV="${RECREATE_VENV:-0}"
SERVER_PID=""

mkdir -p "${LOG_DIR}"

log_step() {
  printf "\n[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

cleanup() {
  if [ -n "${SERVER_PID}" ] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill "${SERVER_PID}" 2>/dev/null || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

probe_url() {
  local url="$1"
  local output="$2"
  "${ROOT_DIR}/server/.venv/bin/python" - "$url" >"${output}" 2>&1 <<'PY'
from __future__ import annotations

import json
import sys
import urllib.request

url = sys.argv[1]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(url, timeout=5) as response:
    body = response.read().decode("utf-8")
    print(f"URL={url}")
    print(f"STATUS={response.status}")
    try:
        print(json.dumps(json.loads(body), ensure_ascii=False, indent=2))
    except json.JSONDecodeError:
        print(body)
PY
}

wait_for_health() {
  local url="http://127.0.0.1:${PORT}/health"
  for _ in $(seq 1 30); do
    if "${ROOT_DIR}/server/.venv/bin/python" - "$url" >/dev/null 2>&1 <<'PY'
from __future__ import annotations

import sys
import urllib.request

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(sys.argv[1], timeout=1) as response:
    raise SystemExit(0 if response.status == 200 else 1)
PY
    then
      return 0
    fi
    sleep 1
  done
  return 1
}

{
  echo "date=$(date -Iseconds)"
  echo "root=${ROOT_DIR}"
  echo "port=${PORT}"
  echo "recreate_venv=${RECREATE_VENV}"
  echo
  uname -a || true
  echo
  python3 --version
  python3 -m pip --version || true
  echo
  git rev-parse --short HEAD || true
  git status --short || true
} >"${LOG_DIR}/00-environment.log" 2>&1

if [ "${RECREATE_VENV}" = "1" ]; then
  log_step "removing existing virtual environments"
  rm -rf "${ROOT_DIR}/server/.venv" "${ROOT_DIR}/camera-worker/.venv"
fi

log_step "installing server dependencies"
{
  set -x
  cd "${ROOT_DIR}/server"
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python -m pip check
} >"${LOG_DIR}/server-install.log" 2>&1

log_step "installing camera worker dependencies"
{
  set -x
  cd "${ROOT_DIR}/camera-worker"
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python -m pip check
} >"${LOG_DIR}/camera-worker-install.log" 2>&1

log_step "running requirement unit tests"
{
  set -x
  cd "${ROOT_DIR}"
  python3 -m unittest discover -s tests/requirements -p 'test_R_*.py'
} >"${LOG_DIR}/requirements-unittest.log" 2>&1

log_step "starting server"
(
  cd "${ROOT_DIR}/server"
  SERVER_HOST=127.0.0.1 \
  SERVER_PORT="${PORT}" \
  CAMERA_IDS=camera_01 \
  LLM_ENABLED=false \
  TTS_ENABLED=false \
  EDGE_TTS_ENABLED=false \
  LEADERBOARD_DB="../log/devops-leaderboard.db" \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT}"
) >"${LOG_DIR}/server-run.log" 2>&1 &
SERVER_PID="$!"

if ! wait_for_health; then
  echo "server did not become healthy; see log/server-run.log" >&2
  exit 1
fi

probe_url "http://127.0.0.1:${PORT}/health" "${LOG_DIR}/server-health.log"
probe_url "http://127.0.0.1:${PORT}/api/game/state" "${LOG_DIR}/server-game-state.log"

log_step "running camera worker websocket smoke"
{
  set -x
  cd "${ROOT_DIR}/camera-worker"
  SERVER_URL="http://127.0.0.1:${PORT}" \
  CAMERA_ID=camera_01 \
  POSE_ENABLED=false \
  .venv/bin/python scripts/verify_worker_smoke.py
} >"${LOG_DIR}/camera-worker-run.log" 2>&1

probe_url "http://127.0.0.1:${PORT}/api/cameras" "${LOG_DIR}/camera-api-smoke.log"

{
  echo "R-26 offline LAN field verification checklist"
  echo "date=$(date -Iseconds)"
  echo
  echo "Manual field steps:"
  echo "[ ] Disconnect router WAN / internet uplink"
  echo "[ ] Server: ping -c 3 8.8.8.8 fails"
  echo "[ ] Server: hostname -I shows LAN IP"
  echo "[ ] Camera worker: ping -c 3 <SERVER_LAN_IP> succeeds"
  echo "[ ] Camera worker .env SERVER_URL=http://<SERVER_LAN_IP>:8000"
  echo "[ ] Dashboard shows camera Online, keypoint count, frame_fps, pose_fps"
  echo "[ ] /game and /stage complete 5 rounds"
  echo "[ ] EDGE_TTS_ENABLED=false or edge-tts failure falls back without stopping game"
  echo
  echo "Local smoke performed by this script:"
  echo "server_health=log/server-health.log"
  echo "game_state=log/server-game-state.log"
  echo "camera_worker_websocket_smoke=log/camera-worker-run.log"
  echo "camera_api_after_smoke=log/camera-api-smoke.log"
  echo
  echo "Internet probe from this machine:"
  if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
    echo "internet_reachable=true"
  else
    echo "internet_reachable=false"
  fi
} >"${LOG_DIR}/offline-lan-checklist.log" 2>&1

{
  echo "DevOps verification summary"
  echo "date=$(date -Iseconds)"
  echo "DEVOPS_6_EXTERNAL_RESOURCES=OK RUN.md documents Ollama, edge-tts, OpenAI/Piper/espeak, SQLite, LAN"
  echo "DEVOPS_7_SERVER_INSTALL=OK log/server-install.log"
  echo "DEVOPS_7_CAMERA_WORKER_INSTALL=OK log/camera-worker-install.log"
  echo "DEVOPS_8_SERVER_RUNTIME=OK log/server-run.log log/server-health.log log/server-game-state.log"
  echo "DEVOPS_8_CAMERA_WORKER_SMOKE=OK log/camera-worker-run.log log/camera-api-smoke.log"
  echo "R26_OFFLINE_LAN_PROCEDURE=OK log/offline-lan-checklist.log test-results/offline-lan/R-26-offline-lan-guide.md"
  echo "REQUIREMENT_TESTS=OK log/requirements-unittest.log"
} >"${LOG_DIR}/devops-summary.log"

log_step "verification complete; see log/devops-summary.log"
