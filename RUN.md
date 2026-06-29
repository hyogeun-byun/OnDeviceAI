# RUN.md

이 문서는 평가 Agent의 DevOps 및 실행 가능성 8개 기준을 기준으로, OnDeviceAI 프로젝트를 설치하고 실행하며 검증 로그를 남기는 방법을 정리한다.

## 1. 프로그램 구성

| 프로그램 | 위치 | 역할 |
|---|---|---|
| FastAPI 서버 | `server/` | 카메라 프레임/포즈 수신, 게임 상태머신, 브라우저 화면 제공 |
| 카메라 워커 | `camera-worker/` | OpenCV 카메라 캡처, MediaPipe Pose 추론, 서버 WebSocket 전송 |
| 브라우저 화면 | `server/app/web/` | `/`, `/game`, `/stage` 화면 |

## 2. 라이브러리와 버전

서버:

```bash
server/requirements.txt
```

카메라 워커:

```bash
camera-worker/requirements.txt
```

모든 Python 의존성은 `==` 버전 고정으로 관리한다.

## 3. 환경 변수와 설정

서버 예시:

```bash
cp server/.env.example server/.env
```

카메라 워커 예시:

```bash
cp camera-worker/.env.example camera-worker/.env
```

주요 설정:

| 변수 | 위치 | 설명 |
|---|---|---|
| `CAMERA_IDS` | server | 서버가 관리할 카메라 ID 목록 |
| `SERVER_URL` | camera-worker | 카메라 워커가 연결할 서버 LAN 주소 |
| `CAMERA_ID` | camera-worker | 워커 고유 ID |
| `FPS` | camera-worker | 영상 전송 FPS |
| `POSE_MODEL_COMPLEXITY` | camera-worker | MediaPipe Pose complexity, `0`은 Lite |
| `LLM_ENABLED` | server | 로컬 Ollama LLM 사용 여부 |
| `EDGE_TTS_ENABLED` | server | edge-tts 서버 합성 사용 여부 |

## 4. 외부 서비스 및 선택 자원

이 프로젝트의 핵심 게임 기능은 서버, 카메라 워커, 브라우저가 같은 LAN에 있으면 동작한다.

| 자원 | 필수 여부 | 설명 | 실패/미사용 시 동작 |
|---|---|---|---|
| Ollama | 선택 | 로컬 LLM 진행자 멘트 생성 | `LLM_ENABLED=false`이면 정적 멘트 사용 |
| edge-tts | 선택 | 자연스러운 한국어 mp3 음성 합성, 인터넷 필요 | 실패 시 브라우저 Web Speech 또는 텍스트 폴백 |
| OpenAI TTS | 선택 | 서버 보드 스피커 음성 선택 엔진 | 미설정 시 사용하지 않음 |
| Piper | 선택 | 오프라인 TTS 엔진 | 모델 경로 없으면 사용하지 않음 |
| espeak-ng | 선택 | 가장 가벼운 오프라인 TTS 엔진 | 없으면 화면 텍스트만 사용 |
| SQLite | 자동 | 리더보드 로컬 DB | `LEADERBOARD_DB` 경로에 자동 생성 |
| 공유기/LAN | 필수 | 서버, 카메라 워커, 브라우저 내부 통신 | 같은 LAN IP 대역 필요 |

오프라인 LAN 검증에서는 외부 네트워크 의존성을 끄는 설정을 권장한다.

```dotenv
LLM_ENABLED=false
TTS_ENABLED=false
EDGE_TTS_ENABLED=false
```

로컬 Ollama를 이미 설치한 경우에만 다음처럼 로컬 주소를 사용한다.

```dotenv
LLM_ENABLED=true
LLM_BASE_URL=http://127.0.0.1:11434/v1/chat/completions
LLM_MODEL=exaone3.5:2.4b
EDGE_TTS_ENABLED=false
```

## 5. 설치

서버:

```bash
cd server
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip check
```

카메라 워커:

```bash
cd camera-worker
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip check
```

## 6. 실행

서버:

```bash
cd server
. .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

카메라 워커:

```bash
cd camera-worker
. .venv/bin/activate
python -m app.main
```

브라우저:

```text
http://<SERVER_LAN_IP>:8000
http://<SERVER_LAN_IP>:8000/game
http://<SERVER_LAN_IP>:8000/stage
```

## 7. 자동 검증 및 로그 생성

평가용 설치/기동 검증 로그는 다음 명령으로 생성한다.

```bash
RECREATE_VENV=1 bash scripts/verify_devops.sh
```

생성되는 주요 로그:

| 로그 | 내용 |
|---|---|
| `log/00-environment.log` | Python, pip, OS, Git 정보 |
| `log/server-install.log` | 서버 venv 생성, requirements 설치, `pip check` |
| `log/camera-worker-install.log` | 카메라 워커 venv 생성, requirements 설치, `pip check` |
| `log/requirements-unittest.log` | R-01~R-27 요구사항 unittest 실행 결과 |
| `log/server-run.log` | FastAPI 서버 실기동 로그 |
| `log/server-health.log` | `/health` 응답 확인 |
| `log/server-game-state.log` | `/api/game/state` 응답 확인 |
| `log/camera-worker-run.log` | 카메라 워커 WebSocket smoke 실행 로그 |
| `log/camera-api-smoke.log` | 서버가 smoke pose/metrics를 수신했는지 확인 |
| `log/offline-lan-checklist.log` | R-26 오프라인 LAN 현장 검증 체크리스트 |
| `log/devops-summary.log` | DevOps 6~8 기준 충족 근거 요약 |

## 8. R-26 오프라인 LAN 검증

하나의 공유기를 내부 LAN으로 사용하고, WAN/인터넷 연결을 끊은 상태로 시연한다.

영상에 보여줄 순서:

1. 공유기 WAN 케이블이 빠져 있거나 인터넷 연결이 없는 상태를 보여준다.
2. 서버에서 `ping -c 3 8.8.8.8` 실패를 보여준다.
3. 서버의 LAN IP를 `hostname -I`로 확인한다.
4. 카메라 워커에서 `ping -c 3 <SERVER_LAN_IP>` 성공을 보여준다.
5. 카메라 워커 `.env`의 `SERVER_URL=http://<SERVER_LAN_IP>:8000`을 보여준다.
6. 서버와 카메라 워커를 실행한다.
7. 대시보드에서 카메라 Online, keypoint count, pose_fps를 보여준다.
8. `/game`, `/stage`에서 5라운드가 끝까지 진행되는 것을 보여준다.
9. edge-tts/Ollama를 끈 상태에서도 게임이 멈추지 않고 텍스트/브라우저 폴백으로 진행됨을 보여준다.

상세 체크리스트는 다음 파일에 있다.

```text
test-results/offline-lan/R-26-offline-lan-guide.md
```

## 9. 제출 전 점검

```bash
python3 -m unittest discover -s tests/requirements -p 'test_R_*.py'
```

최종 제출 ZIP에는 최소한 다음을 포함한다.

- `server/`
- `camera-worker/`
- `tests/`
- `test-results/`
- `log/`
- `README.md`
- `RUN.md`
- `server/requirements.txt`
- `camera-worker/requirements.txt`
- `.git/` 또는 `git_log.txt`
