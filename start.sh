#!/usr/bin/env bash
# =============================================================
#  이구동성 텔레파시 — 서버 실행 (서버만! 카메라는 따로)
#  사용법:
#     ./start.sh
#  옵션:
#     PORT=8000 ./start.sh
#  특징: 서버가 비정상 종료되어도 자동으로 다시 띄웁니다 (끊김 방지).
#  카메라는 이 보드/다른 노트북 모두  ./start-camera.sh  로 붙이세요.
#  종료: Ctrl+C
# =============================================================
set -uo pipefail

# 스크립트가 있는 폴더 = 프로젝트 루트 (어디서 실행해도 동작)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

SERVER_VENV="$ROOT/server/.venv"
if [ -x "$SERVER_VENV/bin/python" ]; then
  SERVER_PY="$SERVER_VENV/bin/python"
else
  SERVER_PY="python3"
fi

# ── 종료 처리: Ctrl+C 누르면 깔끔히 멈추고 자동 재시작도 끔 ──
STOP=0
SRV_PID=""
on_stop() {
  STOP=1
  echo
  echo "[stop] 종료합니다…"
  [ -n "$SRV_PID" ] && kill "$SRV_PID" 2>/dev/null || true
}
trap on_stop INT TERM

# 혹시 떠 있던 기존 인스턴스 정리 (포트 충돌 + 중복 감시 루프 방지)
SELF_PID=$$
# 1) 나(이 스크립트)와 부모 셸을 제외한 다른 start.sh 감시 프로세스 종료
for pid in $(pgrep -f "[s]tart\.sh" 2>/dev/null || true); do
  [ "$pid" = "$SELF_PID" ] && continue
  [ "$pid" = "${PPID:-0}" ] && continue
  kill "$pid" 2>/dev/null || true
done
# 2) 떠 있던 uvicorn 서버 종료
pkill -f "uvicorn app.main:app" 2>/dev/null || true
# 3) 포트가 실제로 비워질 때까지 잠깐 대기 (address already in use 방지)
for _ in $(seq 1 20); do
  if ! ss -ltn 2>/dev/null | grep -q ":${PORT} "; then
    break
  fi
  sleep 0.5
done

# 접속 주소 안내
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -z "${IP:-}" ] && IP="<이 보드 IP>"
cat <<EOF

  ────────────────────────────────────────────
   참가자 화면 : http://${IP}:${PORT}/game
   관객 화면   : http://${IP}:${PORT}/stage
   대시보드    : http://${IP}:${PORT}/
  ────────────────────────────────────────────
   카메라는  ./start-camera.sh  로 붙이세요.
   종료하려면 Ctrl+C
  ────────────────────────────────────────────

EOF

cd "$ROOT/server"

# 서버가 죽어도 자동으로 다시 띄움 (Ctrl+C 누르기 전까지)
while [ "$STOP" != "1" ]; do
  echo "[server] http://${HOST}:${PORT} 시작…"
  "$SERVER_PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT" &
  SRV_PID=$!
  wait "$SRV_PID"
  code=$?
  [ "$STOP" = "1" ] && break
  echo "[server] 서버가 종료됨(code ${code}). 2초 후 자동 재시작합니다…"
  sleep 2
done

echo "[stop] 서버를 종료했습니다."
