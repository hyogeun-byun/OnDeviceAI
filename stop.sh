#!/usr/bin/env bash
# =============================================================
#  OnDeviceAI — 서버/카메라 워커 강제 종료
#
#  사용법:
#     ./stop.sh
#
#  옵션:
#     PORT=8000 ./stop.sh
#
#  이 스크립트는 현재 프로젝트의 uvicorn 서버와 camera-worker를
#  종료하고, 필요하면 지정 포트를 점유한 프로세스까지 정리합니다.
# =============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8000}"

echo "[stop] OnDeviceAI 관련 프로세스를 종료합니다."

terminate_pattern() {
  local label="$1"
  local pattern="$2"
  local pids

  pids="$(pgrep -f "$pattern" 2>/dev/null || true)"
  if [ -z "$pids" ]; then
    echo "[stop] ${label}: 실행 중인 프로세스 없음"
    return
  fi

  echo "[stop] ${label}: SIGTERM -> ${pids//$'\n'/ }"
  kill $pids 2>/dev/null || true
  sleep 1

  pids="$(pgrep -f "$pattern" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "[stop] ${label}: 아직 남아 있어 SIGKILL -> ${pids//$'\n'/ }"
    kill -9 $pids 2>/dev/null || true
  fi
}

terminate_port() {
  local port="$1"
  local pids=""

  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti :"$port" 2>/dev/null || true)"
  elif command -v fuser >/dev/null 2>&1; then
    pids="$(fuser "$port"/tcp 2>/dev/null || true)"
  fi

  if [ -z "$pids" ]; then
    echo "[stop] port ${port}: 점유 프로세스 없음"
    return
  fi

  echo "[stop] port ${port}: SIGTERM -> ${pids//$'\n'/ }"
  kill $pids 2>/dev/null || true
  sleep 1

  local still_running=""
  for pid in $pids; do
    if kill -0 "$pid" 2>/dev/null; then
      still_running="${still_running} ${pid}"
    fi
  done

  if [ -n "$still_running" ]; then
    echo "[stop] port ${port}: 아직 남아 있어 SIGKILL ->${still_running}"
    kill -9 $still_running 2>/dev/null || true
  fi
}

# start.sh가 띄운 서버와 예전 run_server.sh 방식 모두 정리합니다.
terminate_pattern "web server" "$ROOT/src/program_server/.venv/bin/python -m uvicorn app.main:app"
terminate_pattern "web server" "python3 -m uvicorn app.main:app"
terminate_pattern "web server" "uvicorn app.main:app"

# start-camera.sh와 src/program_camera_worker/scripts/run_worker.sh 방식 모두 정리합니다.
terminate_pattern "camera worker" "$ROOT/src/program_camera_worker/.venv/bin/python -m app.main"
terminate_pattern "camera worker" "python3 -m app.main"
terminate_pattern "camera worker" "python -m app.main"

# 서버 포트가 여전히 점유되어 있으면 마지막으로 정리합니다.
terminate_port "$PORT"

echo "[stop] 완료했습니다."
