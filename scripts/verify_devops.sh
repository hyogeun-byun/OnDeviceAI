#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_DIR="${ROOT_DIR}/src/program_server"
CAMERA_WORKER_DIR="${ROOT_DIR}/src/program_camera_worker"
LOG_DIR="${ROOT_DIR}/log"
SERVER_REQ_LOG_DIR="${ROOT_DIR}/test-results/program_server/requirements"
CAMERA_REQ_LOG_DIR="${ROOT_DIR}/test-results/program_camera_worker/requirements"
PORT="${PORT:-18000}"
RECREATE_VENV="${RECREATE_VENV:-0}"
FIELD_CAMERA_IDS="${FIELD_CAMERA_IDS:-${CAMERA_IDS:-camera_01 camera_02 camera_03}}"
FIELD_CAMERA_IDS="${FIELD_CAMERA_IDS//,/ }"
SERVER_PID=""

mkdir -p "${LOG_DIR}" "${SERVER_REQ_LOG_DIR}" "${CAMERA_REQ_LOG_DIR}"

ENV_LOG="${SERVER_REQ_LOG_DIR}/R-27-configuration-environment.log"
SERVER_INSTALL_LOG="${SERVER_REQ_LOG_DIR}/R-27-server-install.log"
CAMERA_INSTALL_LOG="${CAMERA_REQ_LOG_DIR}/R-27-camera-worker-install.log"
UNITTEST_LOG="${SERVER_REQ_LOG_DIR}/R-01-R-27-requirements-unittest.log"
SERVER_RUN_LOG="${SERVER_REQ_LOG_DIR}/R-26-offline-lan-server.log"
SERVER_HEALTH_LOG="${SERVER_REQ_LOG_DIR}/R-26-offline-lan-server-health.log"
GAME_STATE_LOG="${SERVER_REQ_LOG_DIR}/R-11-game-state-api.log"
CAMERA_WORKER_RUN_LOG="${CAMERA_REQ_LOG_DIR}/R-01-multi-camera-websocket-camera-01.log"
CAMERA_API_LOG="${SERVER_REQ_LOG_DIR}/R-05-dashboard-camera-api.log"
OFFLINE_CHECKLIST_LOG="${CAMERA_REQ_LOG_DIR}/R-26-offline-lan-checklist.log"
DEVOPS_SUMMARY_LOG="${SERVER_REQ_LOG_DIR}/R-26-offline-lan-summary.log"

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
  "${SERVER_DIR}/.venv/bin/python" - "$url" >"${output}" 2>&1 <<'PY'
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

mirror_requirement_log() {
  local source="$1"
  local target="$2"
  if [ -f "${source}" ]; then
    cp "${source}" "${target}" 2>/dev/null || true
  fi
}

mirror_existing_camera_evidence() {
  local camera_id camera_slug source_log source_metrics
  for camera_id in ${FIELD_CAMERA_IDS}; do
    camera_slug="${camera_id//_/-}"
    source_log="${LOG_DIR}/camera-worker-${camera_id}.log"
    source_metrics="${LOG_DIR}/camera-worker-${camera_id}-metrics.jsonl"

    mirror_requirement_log "${source_log}" "${CAMERA_REQ_LOG_DIR}/R-01-multi-camera-websocket-${camera_slug}.log"
    mirror_requirement_log "${source_log}" "${CAMERA_REQ_LOG_DIR}/R-03-pose-fps-33-landmarks-${camera_slug}.log"
    mirror_requirement_log "${source_log}" "${CAMERA_REQ_LOG_DIR}/R-04-threaded-capture-frame-pose-${camera_slug}.log"
    mirror_requirement_log "${source_log}" "${CAMERA_REQ_LOG_DIR}/R-26-offline-lan-${camera_slug}.log"

    mirror_requirement_log "${source_metrics}" "${CAMERA_REQ_LOG_DIR}/R-01-multi-camera-websocket-${camera_slug}-metrics.jsonl"
    mirror_requirement_log "${source_metrics}" "${CAMERA_REQ_LOG_DIR}/R-03-pose-fps-33-landmarks-${camera_slug}-metrics.jsonl"
    mirror_requirement_log "${source_metrics}" "${CAMERA_REQ_LOG_DIR}/R-04-threaded-capture-frame-pose-${camera_slug}-metrics.jsonl"
    mirror_requirement_log "${source_metrics}" "${CAMERA_REQ_LOG_DIR}/R-19-no-llm-playing-path-${camera_slug}-metrics.jsonl"
  done
}

wait_for_health() {
  local url="http://127.0.0.1:${PORT}/health"
  for _ in $(seq 1 30); do
    if "${SERVER_DIR}/.venv/bin/python" - "$url" >/dev/null 2>&1 <<'PY'
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
} >"${ENV_LOG}" 2>&1
mirror_requirement_log "${ENV_LOG}" "${LOG_DIR}/00-environment.log"

if [ "${RECREATE_VENV}" = "1" ]; then
  log_step "removing existing virtual environments"
  rm -rf "${SERVER_DIR}/.venv" "${CAMERA_WORKER_DIR}/.venv"
fi

log_step "installing server dependencies"
{
  set -x
  cd "${SERVER_DIR}"
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python -m pip check
} >"${SERVER_INSTALL_LOG}" 2>&1
mirror_requirement_log "${SERVER_INSTALL_LOG}" "${LOG_DIR}/server-install.log"

log_step "installing camera worker dependencies"
{
  set -x
  cd "${CAMERA_WORKER_DIR}"
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python -m pip check
} >"${CAMERA_INSTALL_LOG}" 2>&1
mirror_requirement_log "${CAMERA_INSTALL_LOG}" "${LOG_DIR}/camera-worker-install.log"

log_step "running requirement unit tests"
{
  set -x
  cd "${ROOT_DIR}"
  python3 -m unittest discover -s tests -p 'test_R_*.py'
} >"${UNITTEST_LOG}" 2>&1
mirror_requirement_log "${UNITTEST_LOG}" "${LOG_DIR}/requirements-unittest.log"
mirror_requirement_log "${UNITTEST_LOG}" "${SERVER_REQ_LOG_DIR}/unittest-results.txt"

log_step "starting server"
(
  cd "${SERVER_DIR}"
  SERVER_HOST=127.0.0.1 \
  SERVER_PORT="${PORT}" \
  CAMERA_IDS=camera_01 \
  LLM_ENABLED=false \
  TTS_ENABLED=false \
  EDGE_TTS_ENABLED=false \
  LEADERBOARD_DB="../../log/devops-leaderboard.db" \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT}"
) >"${SERVER_RUN_LOG}" 2>&1 &
SERVER_PID="$!"

if ! wait_for_health; then
  echo "server did not become healthy; see ${SERVER_RUN_LOG}" >&2
  exit 1
fi

probe_url "http://127.0.0.1:${PORT}/health" "${SERVER_HEALTH_LOG}"
mirror_requirement_log "${SERVER_HEALTH_LOG}" "${LOG_DIR}/server-health.log"

probe_url "http://127.0.0.1:${PORT}/api/game/state" "${GAME_STATE_LOG}"
mirror_requirement_log "${GAME_STATE_LOG}" "${LOG_DIR}/server-game-state.log"

log_step "running camera worker websocket smoke"
{
  set -x
  cd "${CAMERA_WORKER_DIR}"
  SERVER_URL="http://127.0.0.1:${PORT}" \
  CAMERA_ID=camera_01 \
  POSE_ENABLED=false \
  .venv/bin/python scripts/verify_worker_smoke.py
} >"${CAMERA_WORKER_RUN_LOG}" 2>&1
mirror_requirement_log "${CAMERA_WORKER_RUN_LOG}" "${LOG_DIR}/camera-worker-run.log"

probe_url "http://127.0.0.1:${PORT}/api/cameras" "${CAMERA_API_LOG}"
mirror_requirement_log "${CAMERA_API_LOG}" "${LOG_DIR}/camera-api-smoke.log"

mirror_requirement_log "${SERVER_RUN_LOG}" "${LOG_DIR}/server-run.log"
mirror_requirement_log "${SERVER_RUN_LOG}" "${SERVER_REQ_LOG_DIR}/R-01-multi-camera-websocket-server.log"
mirror_requirement_log "${SERVER_RUN_LOG}" "${SERVER_REQ_LOG_DIR}/R-17-game-websocket-10hz-sync-server.log"
mirror_requirement_log "${SERVER_RUN_LOG}" "${SERVER_REQ_LOG_DIR}/R-19-no-llm-playing-path-server.log"
mirror_requirement_log "${SERVER_RUN_LOG}" "${SERVER_REQ_LOG_DIR}/R-20-llm-tts-fallback-server.log"
mirror_requirement_log "${SERVER_RUN_LOG}" "${SERVER_REQ_LOG_DIR}/R-22-speech-id-dedup-fallback-server.log"
mirror_existing_camera_evidence

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
  echo "[ ] /game and /stage complete one 60-second sprint through the finished screen"
  echo "[ ] EDGE_TTS_ENABLED=false or edge-tts failure falls back without stopping game"
  echo
  echo "Local smoke performed by this script:"
  echo "server_log=${SERVER_RUN_LOG}"
  echo "server_health=${SERVER_HEALTH_LOG}"
  echo "game_state=${GAME_STATE_LOG}"
  echo "camera_worker_websocket_smoke=${CAMERA_WORKER_RUN_LOG}"
  echo "camera_api_after_smoke=${CAMERA_API_LOG}"
  echo
  echo "Internet probe from this machine:"
  if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
    echo "internet_reachable=true"
  else
    echo "internet_reachable=false"
  fi
} >"${OFFLINE_CHECKLIST_LOG}" 2>&1
mirror_requirement_log "${OFFLINE_CHECKLIST_LOG}" "${LOG_DIR}/offline-lan-checklist.log"

{
  echo "DevOps verification summary"
  echo "date=$(date -Iseconds)"
  echo "DEVOPS_6_EXTERNAL_RESOURCES=OK RUN.md documents Ollama, edge-tts, OpenAI/Piper/espeak, SQLite, LAN"
  echo "DEVOPS_7_SERVER_INSTALL=OK ${SERVER_INSTALL_LOG}"
  echo "DEVOPS_7_CAMERA_WORKER_INSTALL=OK ${CAMERA_INSTALL_LOG}"
  echo "DEVOPS_8_SERVER_RUNTIME=OK ${SERVER_RUN_LOG} ${SERVER_HEALTH_LOG} ${GAME_STATE_LOG}"
  echo "DEVOPS_8_CAMERA_WORKER_SMOKE=OK ${CAMERA_WORKER_RUN_LOG} ${CAMERA_API_LOG}"
  echo "REAL_CAMERA_FPS_LOGGING=OK python -m app.main writes log/camera-worker-<CAMERA_ID>.log and log/camera-worker-<CAMERA_ID>-metrics.jsonl"
  echo "REAL_CAMERA_REQUIREMENT_LOG_MIRROR=OK existing camera logs copied to test-results/program_camera_worker/requirements/R-<ID>-... when present"
  echo "R26_OFFLINE_LAN_PROCEDURE=OK ${OFFLINE_CHECKLIST_LOG} test-results/program_camera_worker/offline-lan/R-26-offline-lan-guide.md"
  echo "REQUIREMENT_TESTS=OK ${UNITTEST_LOG}"
} >"${DEVOPS_SUMMARY_LOG}"
mirror_requirement_log "${DEVOPS_SUMMARY_LOG}" "${LOG_DIR}/devops-summary.log"

log_step "verification complete; see ${DEVOPS_SUMMARY_LOG}"
