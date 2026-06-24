#!/usr/bin/env bash
# =============================================================
#  이구동성 텔레파시 — 서버 + (이 보드의) 카메라 워커 한 번에 실행
#  사용법:
#     ./start.sh
#  옵션(환경변수로 덮어쓰기, .env 안 건드림):
#     PORT=8000  CAMERA_ID=camera_03  CAMERA_INDEX=0  ./start.sh
#     NO_CAMERA=1 ./start.sh          # 서버만 띄우기 (카메라 워커 생략)
#  종료: Ctrl+C  →  서버·카메라 둘 다 같이 정리됨
# =============================================================
set -uo pipefail

# 스크립트가 있는 폴더 = 프로젝트 루트 (어디서 실행해도 동작)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 설정 (필요하면 환경변수로 덮어쓰기) ──────────────────────
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
CAMERA_ID="${CAMERA_ID:-camera_03}"     # 이 보드에 달린 USB 카메라
CAMERA_INDEX="${CAMERA_INDEX:-0}"       # /dev/video0
SERVER_URL="${SERVER_URL:-http://127.0.0.1:${PORT}}"  # 로컬 워커는 항상 localhost
NO_CAMERA="${NO_CAMERA:-0}"

SERVER_VENV="$ROOT/server/.venv"
WORKER_VENV="$ROOT/camera-worker/.venv"

pick_python() {  # venv 있으면 그걸로, 없으면 시스템 python3
  if [ -x "$1/bin/python" ]; then echo "$1/bin/python"; else echo "python3"; fi
}
SERVER_PY="$(pick_python "$SERVER_VENV")"
WORKER_PY="$(pick_python "$WORKER_VENV")"

# ── 종료 처리: Ctrl+C 한 번에 서버·카메라 모두 정리 ──────────
SERVER_PID=""
WORKER_PID=""
CLEANED=0
cleanup() {
  [ "$CLEANED" = 1 ] && return
  CLEANED=1
  echo
  echo "[stop] 종료 중…"
  [ -n "$WORKER_PID" ] && kill "$WORKER_PID" 2>/dev/null || true
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  echo "[stop] 모두 종료됐어요."
}
trap cleanup INT TERM EXIT

# 혹시 떠 있던 기존 서버/카메라 워커 정리 (포트·카메라 충돌 방지)
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "camera-worker.*app.main" 2>/dev/null || true
sleep 1

# ── 1) 서버 ──────────────────────────────────────────────────
echo "[server] http://${HOST}:${PORT} 시작…"
(
  cd "$ROOT/server"
  exec "$SERVER_PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
) &
SERVER_PID=$!

# 서버가 응답할 때까지 대기 (최대 ~20초)
echo -n "[server] 준비 대기"
ready=0
for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then ready=1; echo " ✓"; break; fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then echo " ✗ (서버가 죽었어요)"; break; fi
  echo -n "."
  sleep 0.5
done
[ "$ready" = 1 ] || echo "[server] 아직 응답이 없지만 계속 진행합니다."

# ── 2) 이 보드의 카메라 워커 ─────────────────────────────────
if [ "$NO_CAMERA" != "1" ]; then
  echo "[camera] ${CAMERA_ID} (index ${CAMERA_INDEX}) → ${SERVER_URL}"
  (
    cd "$ROOT/camera-worker"
    CAMERA_ID="$CAMERA_ID" CAMERA_INDEX="$CAMERA_INDEX" SERVER_URL="$SERVER_URL" \
      exec "$WORKER_PY" -m app.main
  ) &
  WORKER_PID=$!
else
  echo "[camera] NO_CAMERA=1 → 카메라 워커 생략"
fi

# 접속 주소 안내
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -z "${IP:-}" ] && IP="<이 보드 IP>"
cat <<EOF

  ────────────────────────────────────────────
   참가자 화면 : http://${IP}:${PORT}/game
   관객 화면   : http://${IP}:${PORT}/stage
   대시보드    : http://${IP}:${PORT}/
  ────────────────────────────────────────────
   다른 노트북의 카메라는  ./start-camera.sh  로 붙이세요.
   종료하려면 Ctrl+C
  ────────────────────────────────────────────

EOF

# 서버가 살아있는 동안 유지 (카메라 워커가 죽어도 서버는 계속 돌아감)
wait "$SERVER_PID"
