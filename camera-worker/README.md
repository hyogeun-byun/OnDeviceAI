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

> **tflite-runtime 설치 참고**: 라즈베리파이용 휠이 공식 PyPI에 없는 경우  
> [piwheels](https://www.piwheels.org/project/tflite-runtime/) 또는  
> `pip install tensorflow` (느리지만 동일하게 동작)로 대체할 수 있다.

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

**MoveNet SinglePose Lightning TFLite int8** (`models/movenet-singlepose-lightning-tflite-int8.tflite`)을 사용한다.

- 입력: `[1, 192, 192, 3]`, int8 (quantized)
- 출력: `[1, 1, 17, 3]` → 각 키포인트 `[y, x, score]`, 값 범위 `[0, 1]`
- 키포인트 17개 (COCO 포맷):

| 인덱스 | 이름 | 인덱스 | 이름 |
|--------|------|--------|------|
| 0 | nose | 9 | left_wrist |
| 1 | left_eye | 10 | right_wrist |
| 2 | right_eye | 11 | left_hip |
| 3 | left_ear | 12 | right_hip |
| 4 | right_ear | 13 | left_knee |
| 5 | left_shoulder | 14 | right_knee |
| 6 | right_shoulder | 15 | left_ankle |
| 7 | left_elbow | 16 | right_ankle |
| 8 | right_elbow | | |

MediaPipe의 33개 키포인트와 달리 17개이며, 얼굴 세부 랜드마크(입술·눈썹 등)와 발끝·손가락이 없다. 서버 점수 계산(`pose_similarity.py`)에서 사용하는 8개 관절(양쪽 팔꿈치·어깨·고관절·무릎)은 모두 포함되어 있어 게임 동작에 영향이 없다.

모델 경로는 `.env`의 `POSE_MODEL_PATH`로 변경할 수 있으며, 기본값은 `models/movenet-singlepose-lightning-tflite-int8.tflite`다.

라즈베리파이 부담을 줄이기 위해 영상 전송 FPS와 포즈 추정 FPS를 분리했다.

- `FPS`: 서버로 보내는 카메라 프레임 FPS
- `POSE_NUM_THREADS`: TFLite 추론에 사용할 CPU 스레드 수 (기본 4)
- `POSE_DRAW_LANDMARKS`: 전송 영상에 스켈레톤을 오버레이할지 여부
- `LOG_INTERVAL_SECONDS`: FPS와 전송량 로그를 몇 초마다 찍을지 설정

keypoint 추론은 코드 상수 `KEYPOINT_INFERENCE_FPS = 5.0` 기준으로 초당 5회 실행한다. 워커 내부는 카메라 캡처, 프레임 전송, 포즈 추정 스레드로 분리되어 포즈 추정이 영상 전송을 최대한 막지 않도록 구성한다.

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
