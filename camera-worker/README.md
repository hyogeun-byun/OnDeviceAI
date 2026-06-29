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

> **MediaPipe 설치 참고**: 라즈베리파이 환경에 따라 휠 설치 시간이 길 수 있다.  
> 제출 기준 환경에서는 `mediapipe==0.10.18`을 고정해 재현성을 맞춘다.

## 실행

`.env`에서 `SERVER_URL`을 Web 서버 라즈베리파이 IP로 바꾼 뒤 실행한다.

```bash
python -m app.main
```

워커는 `SERVER_URL`을 기준으로 WebSocket 주소를 자동 생성한다. 예를 들어 `SERVER_URL=http://192.168.0.10:8000`이면 내부적으로 `ws://192.168.0.10:8000/api/cameras/camera_01/ws`에 연결한다.

예:

```text
SERVER_URL=http://192.168.0.10:8000
CAMERA_ID=camera_01
CAMERA_INDEX=0
POSE_ENABLED=true
POSE_NUM_THREADS=4
POSE_DRAW_LANDMARKS=true
```

## 포즈 추정 모델

**MediaPipe Pose Lite** (`model_complexity=0`)을 사용한다.

- 키포인트 33개 (얼굴·상체·하체·발끝 포함)
- 라즈베리파이 4/5 기준 평균 추론 시간: **~30ms**
- `KEYPOINT_INFERENCE_FPS = 10.0` (100ms 주기, 추론 여유 3배)

라즈베리파이 부담을 줄이기 위해 영상 전송 FPS와 포즈 추정 FPS를 분리했다.

- `FPS`: 서버로 보내는 카메라 프레임 FPS
- `POSE_INPUT_WIDTH`: 포즈 추정에 넣을 축소 이미지 너비 (기본 192px)
- `POSE_MODEL_COMPLEXITY=0`: Lite 버전 (0=Lite, 1=Full)
- `LOG_INTERVAL_SECONDS`: FPS와 전송량 로그를 몇 초마다 찍을지 설정

keypoint 추론은 코드 상수 `KEYPOINT_INFERENCE_FPS = 10.0` 기준으로 초당 10회 실행한다. 워커 내부는 카메라 캡처, 프레임 전송, 포즈 추정 스레드로 분리되어 포즈 추정이 영상 전송을 최대한 막지 않도록 구성한다.

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
