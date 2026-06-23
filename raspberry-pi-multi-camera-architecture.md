# 라즈베리파이 멀티 카메라 온디바이스 AI 프로젝트 구조

## 1. 현재 목표

라즈베리파이 4대와 카메라 4대가 있는 상태에서, 카메라 1대는 제외하고 카메라 3대만 사용한다.

- 라즈베리파이 1대: Web 서버 + LLM 전용
- 라즈베리파이 3대: 각자 카메라 1대씩 연결해서 카메라 영상 처리
- Web 전용 라즈베리파이에서 카메라 3대의 화면과 분석 결과를 확인

결론부터 말하면 가능하다. 다만 라즈베리파이에서 무거운 AI 모델을 동시에 돌리는 것은 한계가 있으므로, 처음에는 가벼운 영상 스트리밍과 간단한 분석부터 시작하고, 이후 모델을 ONNX/TFLite 같은 경량 추론 방식으로 최적화하는 것을 추천한다.

## 2. 전체 구성

```text
                              사용자 브라우저
                                   |
                                   v
                         [Pi-Server: Web + LLM]
                         - FastAPI 또는 Flask
                         - Web Dashboard
                         - 카메라 3대 화면 표시
                         - 분석 결과 저장/표시
                         - LLM 질의응답 또는 요약
                           ^       ^       ^
                           |       |       |
             --------------        |        --------------
             |                     |                     |
             v                     v                     v
 [Pi-Cam-01: Camera Worker] [Pi-Cam-02: Camera Worker] [Pi-Cam-03: Camera Worker]
 - 카메라 1대 연결        - 카메라 1대 연결        - 카메라 1대 연결
 - 프레임 캡처            - 프레임 캡처            - 프레임 캡처
 - AI/영상 연산           - AI/영상 연산           - AI/영상 연산
 - 결과 전송              - 결과 전송              - 결과 전송
```

## 3. 추천 역할 분리

### Pi-Server

Web과 LLM을 담당하는 중앙 서버 라즈베리파이다.

주요 역할:

- 카메라 노드 3대의 연결 상태 확인
- 카메라 영상 스트림 수신 또는 중계
- 분석 결과 수신
- 대시보드 제공
- LLM 실행 또는 LLM API 연결
- 사용자에게 카메라 3대 화면 표시

추천 기술:

- Python 3.10+
- FastAPI
- Uvicorn
- WebSocket
- HTML/CSS/JavaScript 또는 React
- SQLite
- llama.cpp, Ollama, 또는 경량 LLM 서버

### Pi-Cam-01, Pi-Cam-02, Pi-Cam-03

각각 카메라 1대를 담당하는 작업용 라즈베리파이다.

주요 역할:

- 카메라 프레임 캡처
- 필요한 영상 전처리
- 객체 검출, 포즈 추정, 이상 감지 등 카메라별 연산
- 처리된 프레임 또는 원본 프레임 전송
- 분석 결과를 Pi-Server로 전송

추천 기술:

- Python 3.10+
- OpenCV
- Picamera2 또는 libcamera
- ONNX Runtime 또는 TFLite Runtime
- HTTP API 또는 WebSocket Client

## 4. 권장 데이터 흐름

처음부터 완벽한 실시간 시스템을 만들기보다 단계별로 가는 것이 좋다.

### 1단계: 카메라 화면만 Web에 표시

각 카메라 라즈베리파이가 자기 카메라 영상을 MJPEG 또는 JPEG 프레임으로 Pi-Server에 보낸다.

```text
Pi-Cam-N -> 카메라 캡처 -> JPEG 압축 -> Pi-Server 전송 -> Web 표시
```

장점:

- 구현이 쉽다.
- 디버깅이 쉽다.
- AI 모델 없이도 전체 연결 구조를 먼저 검증할 수 있다.

### 2단계: 카메라 노드에서 간단한 연산 수행

예를 들어 움직임 감지, 사람 감지, 밝기 체크, 간단한 객체 감지 등을 각 Pi-Cam에서 실행한다.

```text
Pi-Cam-N -> 카메라 캡처 -> 영상 연산 -> 결과 JSON + 프레임 전송
```

### 3단계: 경량 AI 모델 추가

무거운 모델은 라즈베리파이에서 느릴 수 있으므로 다음 방식 중 하나를 사용한다.

- ONNX로 변환한 경량 모델
- TFLite 모델
- MobileNet 계열 모델
- YOLO nano 계열 모델
- MediaPipe 계열 모델

### 4단계: LLM 연동

LLM은 카메라 프레임 자체를 계속 처리하기보다는, 카메라 노드가 만든 분석 결과를 요약하거나 질의응답하는 용도로 쓰는 것이 현실적이다.

예시:

```text
카메라 분석 결과:
- camera_01: 사람이 1명 감지됨
- camera_02: 움직임 없음
- camera_03: 자세 이상 가능성 있음

사용자 질문:
"현재 이상 상황이 있어?"

LLM 응답:
"camera_03에서 자세 이상 가능성이 감지되었습니다. camera_01에는 사람이 1명 있습니다."
```

## 5. 추천 파일 구조

아래 구조는 처음 프로젝트를 시작하기 좋은 기본 형태다.

```text
OnDeviceAI/
├── README.md
├── docs/
│   ├── raspberry-pi-multi-camera-architecture.md
│   ├── git-commit-policy.md
│   ├── file-naming-policy.md
│   └── python/
│
├── server/
│   ├── README.md
│   ├── requirements.txt
│   ├── .env.example
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── camera_routes.py
│   │   │   ├── health_routes.py
│   │   │   └── llm_routes.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── camera_registry.py
│   │   │   ├── stream_manager.py
│   │   │   └── llm_service.py
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   └── database.py
│   │   └── web/
│   │       ├── static/
│   │       │   ├── css/
│   │       │   └── js/
│   │       └── templates/
│   │           └── index.html
│   └── scripts/
│       ├── run_server.sh
│       └── install_server.sh
│
├── camera-worker/
│   ├── README.md
│   ├── requirements.txt
│   ├── .env.example
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── camera/
│   │   │   ├── __init__.py
│   │   │   ├── camera_reader.py
│   │   │   └── frame_encoder.py
│   │   ├── inference/
│   │   │   ├── __init__.py
│   │   │   ├── model_runner.py
│   │   │   └── postprocess.py
│   │   ├── network/
│   │   │   ├── __init__.py
│   │   │   ├── server_client.py
│   │   │   └── stream_sender.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── logger.py
│   └── scripts/
│       ├── run_worker.sh
│       └── install_worker.sh
│
├── models/
│   ├── README.md
│   ├── detection/
│   └── pose/
│
├── config/
│   ├── server.example.yaml
│   └── camera-worker.example.yaml
│
└── tests/
    ├── server/
    └── camera-worker/
```

## 6. 각 폴더의 의미

### server/

Web 전용 라즈베리파이에 들어갈 코드다.

- Web 화면 제공
- 카메라 화면 3개 표시
- 카메라 노드 상태 관리
- 분석 결과 저장
- LLM 기능 제공

### camera-worker/

카메라가 연결된 라즈베리파이 3대에 동일하게 배포할 코드다.

라즈베리파이마다 설정값만 다르게 둔다.

예:

- Pi-Cam-01: `CAMERA_ID=camera_01`
- Pi-Cam-02: `CAMERA_ID=camera_02`
- Pi-Cam-03: `CAMERA_ID=camera_03`

### models/

AI 모델 파일을 보관하는 폴더다.

주의할 점:

- 큰 모델 파일은 Git에 바로 넣지 않는 것이 좋다.
- 모델 다운로드 스크립트를 따로 두는 것이 좋다.
- 라즈베리파이에서는 가벼운 모델부터 테스트한다.

### config/

서버와 카메라 노드의 설정 예시를 보관한다.

## 7. 네트워크 구성 예시

모든 라즈베리파이는 같은 공유기 또는 같은 LAN에 연결하는 것을 추천한다.

예시 IP:

```text
Pi-Server  : 192.168.0.10
Pi-Cam-01  : 192.168.0.11
Pi-Cam-02  : 192.168.0.12
Pi-Cam-03  : 192.168.0.13
```

카메라 워커는 서버 주소를 알고 있어야 한다.

```text
SERVER_URL=http://192.168.0.10:8000
CAMERA_ID=camera_01
```

## 8. 실행 순서

### 1단계: Pi-Server 준비

Web + LLM 담당 라즈베리파이에서 실행한다.

```bash
cd OnDeviceAI/server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

또는 FastAPI를 쓴다면 다음처럼 실행한다.

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

브라우저에서 접속한다.

```text
http://192.168.0.10:8000
```

### 2단계: Pi-Cam-01 준비

첫 번째 카메라 라즈베리파이에서 실행한다.

```bash
cd OnDeviceAI/camera-worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` 예시:

```text
CAMERA_ID=camera_01
SERVER_URL=http://192.168.0.10:8000
CAMERA_INDEX=0
```

실행:

```bash
python -m app.main
```

### 3단계: Pi-Cam-02 준비

두 번째 카메라 라즈베리파이에서 동일하게 실행하되 `CAMERA_ID`만 바꾼다.

```text
CAMERA_ID=camera_02
SERVER_URL=http://192.168.0.10:8000
CAMERA_INDEX=0
```

```bash
python -m app.main
```

### 4단계: Pi-Cam-03 준비

세 번째 카메라 라즈베리파이에서도 동일하게 실행한다.

```text
CAMERA_ID=camera_03
SERVER_URL=http://192.168.0.10:8000
CAMERA_INDEX=0
```

```bash
python -m app.main
```

## 9. 처음 구현할 최소 기능

처음부터 LLM, AI 모델, 실시간 최적화를 모두 넣기보다 아래 순서로 구현하는 것이 좋다.

1. Pi-Server에서 빈 Web 대시보드 띄우기
2. Pi-Cam 한 대에서 카메라 프레임 읽기
3. Pi-Cam 한 대의 화면을 Pi-Server Web에 표시하기
4. 카메라 3대로 확장하기
5. 각 카메라 연결 상태 표시하기
6. 간단한 분석 결과 JSON 보내기
7. AI 모델 붙이기
8. LLM이 분석 결과를 설명하게 만들기
9. 부팅 시 자동 실행 설정하기

## 10. 성능 관련 현실적인 기준

라즈베리파이 4에서 카메라 3대 전체를 한 장비가 처리하는 것은 부담이 크다. 하지만 카메라 3대의 연산을 라즈베리파이 3대에 분산하면 훨씬 현실적이다.

권장 시작값:

```text
해상도: 640x480
FPS: 10~15
전송 방식: MJPEG 또는 WebSocket JPEG
AI 추론: 1초에 1~5회부터 시작
화면 표시: 가능한 실시간에 가깝게
```

주의할 점:

- 30FPS로 AI 추론까지 하려면 라즈베리파이 4만으로는 어려울 수 있다.
- 카메라 화면은 15FPS로 표시하고, AI 분석은 2~5FPS로 따로 돌리는 구조가 현실적이다.
- LLM은 영상 프레임을 직접 계속 보게 하기보다 분석 결과 텍스트를 받아 설명하게 만드는 것이 좋다.
- 가능하면 유선 LAN을 사용한다.
- Wi-Fi만 사용할 경우 영상 끊김이 생길 수 있다.

## 11. 추천 통신 방식

처음에는 단순한 방식이 좋다.

### 쉬운 방식

```text
Pi-Cam -> HTTP POST로 JPEG 프레임 전송 -> Pi-Server -> Web 표시
Pi-Cam -> HTTP POST로 분석 JSON 전송 -> Pi-Server -> Web 표시
```

장점:

- 이해하기 쉽다.
- 디버깅이 쉽다.
- 처음 개발에 적합하다.

### 조금 더 실시간에 가까운 방식

```text
Pi-Cam -> WebSocket으로 프레임/결과 전송 -> Pi-Server -> WebSocket으로 브라우저 전달
```

장점:

- 실시간성이 좋다.
- 카메라 상태 관리가 쉽다.

### 나중에 고려할 방식

```text
RTSP / WebRTC / MQTT
```

처음부터 RTSP나 WebRTC로 시작하면 난이도가 올라가므로, 카메라와 Web이 잘 연결되는 것을 먼저 확인한 뒤 도입하는 것을 추천한다.

## 12. 자동 실행 구조

프로젝트가 안정화되면 라즈베리파이가 켜질 때 자동으로 실행되게 만든다.

권장 방식:

- `systemd` 서비스 등록
- 서버용 서비스 1개
- 카메라 워커용 서비스 1개

예시:

```text
ondevice-server.service
ondevice-camera-worker.service
```

## 13. 최종 목표 화면 예시

Web 대시보드는 아래처럼 구성하면 된다.

```text
----------------------------------------------------
| OnDeviceAI Dashboard                              |
----------------------------------------------------
| Camera 01           | Camera 02       | Camera 03 |
| [실시간 화면]       | [실시간 화면]   | [실시간 화면] |
| 상태: Online        | 상태: Online    | 상태: Online |
| 감지 결과: ...      | 감지 결과: ...  | 감지 결과: ... |
----------------------------------------------------
| LLM Summary                                      |
| 현재 camera_03에서 이상 가능성이 감지되었습니다. |
----------------------------------------------------
```

## 14. 다음에 만들면 좋은 파일

이 문서 다음 단계로는 실제 실행 가능한 최소 코드를 만드는 것이 좋다.

우선순위:

1. `server/app/main.py`
2. `server/app/web/templates/index.html`
3. `camera-worker/app/main.py`
4. `camera-worker/app/camera/camera_reader.py`
5. `camera-worker/app/network/server_client.py`
6. `server/requirements.txt`
7. `camera-worker/requirements.txt`

현재 최소 구현에서는 카메라 워커가 OpenCV로 프레임을 읽고, MediaPipe Pose를 사용해 keypoint를 추출한 뒤 서버로 전송한다. 라즈베리파이 부담을 줄이기 위해 `POSE_INFERENCE_INTERVAL`, `POSE_INPUT_WIDTH`, `POSE_MODEL_COMPLEXITY`로 추론 빈도와 입력 크기를 낮출 수 있게 구성한다.

## 15. 요약

현재 장비 구성으로 목표 프로젝트는 가능하다.

가장 현실적인 구조는 다음과 같다.

```text
라즈베리파이 1대: Web + LLM 중앙 서버
라즈베리파이 3대: 카메라 1대씩 연결해서 영상 처리
카메라 워커 3대: 처리 결과와 화면을 중앙 서버로 전송
Web 대시보드: 카메라 3대 화면과 분석 결과 표시
LLM: 분석 결과를 요약하고 사용자 질문에 답변
```

처음에는 카메라 1대 화면을 Web에 띄우는 것부터 시작하고, 그 다음 3대로 확장한 뒤 AI와 LLM을 붙이는 순서가 가장 안전하다.
