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
- `LOG_INTERVAL_SECONDS`: FPS와 전송량 로그를 몇 초마다 찍을지 설정

예를 들어 `FPS=10`, `POSE_INFERENCE_INTERVAL=3`이면 카메라 화면은 초당 약 10프레임 전송하고, 포즈 추정은 초당 약 3회 실행한다.

## 속도 확인 로그

워커는 `LOG_INTERVAL_SECONDS`마다 다음 값을 출력한다.

```text
frame_fps: 실제 카메라 프레임 처리 FPS
pose_fps: 실제 포즈 추정 FPS
avg_capture_ms: 카메라에서 프레임을 읽는 평균 시간
avg_pose_ms: 포즈 추정 평균 시간
avg_encode_ms: JPEG 인코딩 평균 시간
avg_frame_upload_ms: 프레임 업로드 평균 시간
avg_pose_upload_ms: 포즈 결과 업로드 평균 시간
avg_frame_kb: 프레임 1장 평균 크기
upload_kb_s: 초당 업로드 전송량
failed_frames / failed_poses: 서버 전송 실패 횟수
```

`avg_pose_ms`가 크면 포즈 모델이 병목이고, `avg_frame_upload_ms`나 `upload_kb_s`가 높으면 네트워크/전송량이 병목일 가능성이 높다.
