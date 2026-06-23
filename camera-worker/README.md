# OnDeviceAI Camera Worker

카메라가 연결된 라즈베리파이에서 실행하는 클라이언트 코드다.

## 설치

```bash
cd camera-worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 실행

`.env`에서 `SERVER_URL`을 Web 서버 라즈베리파이 IP로 바꾼 뒤 실행한다.

```bash
python -m app.main
```

예:

```text
SERVER_URL=http://192.168.0.10:8000
CAMERA_ID=camera_01
CAMERA_INDEX=0
POSE_ENABLED=true
POSE_INFERENCE_INTERVAL=3
POSE_INPUT_WIDTH=256
```

포즈 추정은 MediaPipe Pose를 사용한다. 라즈베리파이 부담을 줄이기 위해 영상 전송 FPS와 포즈 추정 주기를 분리했다.

- `FPS`: 서버로 보내는 카메라 프레임 FPS
- `POSE_INFERENCE_INTERVAL`: 몇 프레임마다 한 번 포즈 추정을 할지 설정
- `POSE_INPUT_WIDTH`: 포즈 추정에 넣을 축소 이미지 너비
- `POSE_MODEL_COMPLEXITY=0`: 가장 가벼운 모델 설정

예를 들어 `FPS=10`, `POSE_INFERENCE_INTERVAL=3`이면 카메라 화면은 초당 약 10프레임 전송하고, 포즈 추정은 초당 약 3회 실행한다.
