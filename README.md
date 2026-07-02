# 이구동성 텔레파시

라즈베리파이 카메라 워커와 FastAPI 서버로 동작하는 온디바이스 AI 파티 게임이다.  
참가자는 서로의 카메라 화면을 평상시 볼 수 없고, 제시어와 텔레파시 게이지, AI MC 코칭만 보고 같은 동작을 맞춘다. 한 제시어에서 오래 막히면 짧은 카메라 힌트가 표시된다.

## 핵심 흐름

- 시작 화면에서 팀명을 입력한다.
- T자 포즈를 유지하면 AI MC 인트로가 시작된다. 버튼 수동 시작도 같은 흐름으로 동작한다.
- 인트로 이후 6개 카테고리 중 하나를 몸동작 또는 버튼으로 선택한다.
- 카메라 테스트를 통과하면 3초 카운트다운 뒤 제시어가 공개된다.
- 게임은 60초 스프린트 방식으로 진행된다.
- 같은 동작을 취해 텔레파시 게이지가 90점 이상이 되면 해당 제시어를 클리어하고 다음 제시어로 넘어간다.
- 제시어별 제한 시간은 20초다. 10초 동안 클리어하지 못하면 약 2.5초 동안 카메라 스냅샷 힌트가 표시된다.
- 60초가 끝나면 클리어 수, 소요 시간, 라운드별 결과, 최종 등급, AI 최종 리포트가 표시된다.

현재 서버 상태머신은 다음 단계를 사용한다.

```text
idle -> intro -> category -> catpick -> camtest -> confirm -> countdown
-> reveal -> playing -> result/giveup/timeup -> finished
```

## 화면

| 화면 | 경로 | 용도 |
|---|---|---|
| 대시보드 | `/` | 카메라별 연결 상태, 사람 감지, keypoint 수, FPS, 업로드량, 스켈레톤 오버레이 확인 |
| 참가자 화면 | `/game` | 플레이어용 화면. 평상시 카메라를 숨기고 제시어, 게이지, 타이머, AI MC 코칭만 표시 |
| 관객 화면 | `/stage` | 발표/프로젝터용 화면. 전체 카메라, 게이지, 타이머, 점수, 진행 멘트를 함께 표시 |

참가자 화면은 프라이버시형 게임 화면이다. `/game`의 기본 playing 구간에는 다른 플레이어의 실시간 영상이 나오지 않는다. 힌트가 켜질 때만 최신 카메라 스냅샷을 짧은 주기로 갱신해 보여주고, 힌트가 끝나면 이미지 `src`를 해제한다.

## 시스템 구조

```text
[카메라 워커 N대] -- WebSocket(JPEG + pose keypoints) --> [FastAPI 서버] -- WebSocket --> [브라우저]
 program_camera_worker                                    src/program_server/app        /, /game, /stage
 - OpenCV 카메라 캡처                                      - 카메라/포즈 수신  - 대시보드
 - MediaPipe Pose Lite                                     - 게임 상태머신    - 참가자 화면
 - 33 landmarks 추정                                       - 게이지 계산      - 관객 화면
 - 프레임 전송/포즈 추정 스레드 분리                        - LLM/TTS 폴백      - MC 아바타/음성
```

카메라 워커 1개는 카메라 1대와 플레이어 1명을 의미한다. 각 워커는 `CAMERA_ID`로 서버에 독립 연결한다.

## 기술 스택

| 영역 | 기술 |
|---|---|
| 서버 | FastAPI, Uvicorn, Jinja2, WebSocket, SQLite |
| 카메라 워커 | OpenCV, MediaPipe Pose Lite, websocket-client |
| 포즈 추정 | MediaPipe Pose Lite, `model_complexity=0`, 33 landmarks |
| 점수 계산 | 얼굴 방향 + 상체 6개 bone vector 코사인 유사도 + 활동성 게이트 |
| 게임 UI | Vanilla JavaScript, HTML Canvas, CSS |
| AI MC | Ollama OpenAI 호환 API 또는 정적 폴백 |
| 음성 | edge-tts mp3 브라우저 재생, 실패 시 Web Speech 또는 텍스트 폴백 |

## 포즈와 점수 계산

카메라 워커는 MediaPipe Pose Lite로 한 사람당 33개 landmark를 추정한다. 각 keypoint는 `name`, `x`, `y`, `z`, `visibility`를 포함한다.

관련 위치:

- `src/program_camera_worker/app/inference/pose_estimator.py`: MediaPipe Pose 실행 및 33 landmarks를 keypoint 배열로 변환
- `src/program_camera_worker/app/constants.py`: `KEYPOINT_INFERENCE_FPS = 10.0`
- `src/program_server/app/services/pose_similarity.py`: 얼굴 방향, 상체 bone vector, 활동성 게이트 계산
- `src/program_server/app/services/stream_manager.py`: 카메라별 `keypoint_count` 집계

서버는 여러 플레이어의 얼굴 방향과 상체 6개 bone vector 유사도를 계산하고, 활동성 게이트를 곱해 텔레파시 게이지를 만든다. 모두 가만히 서 있는 경우에는 자세가 비슷해도 점수가 낮게 나오도록 설계했다.

## AI MC와 음성

AI MC는 인트로, 라운드 결과, 최종 종료 구간에서 한국어 진행 멘트를 제공한다. LLM이 꺼져 있거나 실패하면 정적 멘트로 폴백하므로 게임은 계속 진행된다.

playing 구간의 실시간 코칭은 LLM 호출 없이 규칙 기반으로 생성한다. 포즈 추론과 게임 루프에 영향을 주지 않기 위한 구조다.

브라우저 음성은 `speech_id`로 중복 재생을 방지한다. edge-tts mp3 생성이 실패하거나 비활성화되면 브라우저 Web Speech 또는 화면 텍스트로 폴백한다.

## 설치

서버:

```bash
cd src/program_server
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pip check
```

카메라 워커:

```bash
cd src/program_camera_worker
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pip check
```

Python 의존성은 `src/program_server/requirements.txt`, `src/program_camera_worker/requirements.txt`에 `==` 버전 고정 형식으로 관리한다. 루트 `requirements.txt`는 두 파일을 참조하는 평가용 집계 파일이다.

## 설정

서버 주요 설정:

```dotenv
CAMERA_IDS=camera_01,camera_02,camera_03
LLM_ENABLED=false
EDGE_TTS_ENABLED=true
EDGE_TTS_VOICE=ko-KR-InJoonNeural
```

카메라 워커 주요 설정:

```dotenv
CAMERA_ID=camera_01
SERVER_URL=http://<SERVER_LAN_IP>:8000
FPS=10
POSE_ENABLED=true
POSE_MODEL_COMPLEXITY=0
POSE_INPUT_WIDTH=192
LOG_DIR=../../log
METRICS_LOG_ENABLED=true
```

오프라인 LAN 검증에서는 외부 네트워크 의존성을 끄는 구성을 권장한다.

```dotenv
LLM_ENABLED=false
TTS_ENABLED=false
EDGE_TTS_ENABLED=false
```

## 실행

서버:

```bash
cd src/program_server
. .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

카메라 워커:

```bash
cd src/program_camera_worker
. .venv/bin/activate
python -m app.main
```

브라우저:

```text
http://<SERVER_LAN_IP>:8000
http://<SERVER_LAN_IP>:8000/game
http://<SERVER_LAN_IP>:8000/stage
```

## 검증과 로그

요구사항 unittest:

```bash
python3 -m unittest discover -s tests -p 'test_R_*.py'
```

평가용 설치/기동 검증:

```bash
RECREATE_VENV=1 bash scripts/verify_devops.sh
```

주요 로그:

| 로그 | 내용 |
|---|---|
| `log/requirements-unittest.log` | R-01~R-27 unittest 결과 |
| `test-results/program_server/requirements/R-01-R-27-requirements-unittest.log` | 제출/평가용 unittest 원본 |
| `log/server-install.log` | 서버 의존성 설치 및 `pip check` |
| `log/camera-worker-install.log` | 카메라 워커 의존성 설치 및 `pip check` |
| `log/server-run.log` | 서버 실행 로그 |
| `log/server-health.log` | `/health` 확인 |
| `log/server-game-state.log` | `/api/game/state` 확인 |
| `log/camera-worker-camera_<N>.log` | 실제 카메라 워커 FPS, pose FPS, 업로드량, 실패 횟수 |
| `log/camera-worker-camera_<N>-metrics.jsonl` | 실제 측정 FPS와 지연시간 JSONL |

카메라 워커 로그에는 다음 값이 기록된다.

```text
frame_fps
pose_fps
avg_capture_ms
avg_pose_ms
avg_encode_ms
avg_frame_upload_ms
avg_pose_upload_ms
avg_frame_kb
upload_kb_s
failed_frames
failed_poses
```

## 오프라인 LAN 시연

R-26은 현장 시연으로 확인한다.

1. 공유기 WAN 또는 외부 인터넷 연결이 없는 상태를 보여준다.
2. 서버에서 외부 인터넷 ping 실패를 확인한다.
3. 서버 LAN IP를 확인한다.
4. 카메라 워커에서 서버 LAN IP로 통신 가능함을 확인한다.
5. 서버와 카메라 워커를 실행한다.
6. 대시보드에서 카메라 Online, keypoint count, `pose_fps`를 확인한다.
7. `/game`, `/stage`에서 60초 스프린트 1회를 종료 화면까지 진행한다.
8. LLM/edge-tts 비활성 상태에서도 정적 텍스트 또는 브라우저 폴백으로 게임이 중단되지 않음을 확인한다.

상세 절차는 `test-results/program_camera_worker/offline-lan/R-26-offline-lan-guide.md`에 있다.

## 제출 관련 파일

최종 제출 폴더는 `SW_Bootcamp_13기_최종제출/`이며, 요구사항 명세서와 평가 결과 HTML을 포함한다.

평가용 결과파일 ZIP에는 최소한 다음을 포함해야 한다.

- `src/program_server/`
- `src/program_camera_worker/`
- `tests/`
- `test-results/`
- `log/`
- `docs/requirements/`
- `README.md`
- `RUN.md`
- `requirements.txt`
- `src/program_server/requirements.txt`
- `src/program_camera_worker/requirements.txt`
- `.git/` 또는 `git_log.txt`

더 자세한 실행 재현 절차는 `RUN.md`를 기준으로 한다.
